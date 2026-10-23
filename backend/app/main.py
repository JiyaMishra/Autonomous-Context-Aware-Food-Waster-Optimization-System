import json
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.analytics import dish_waste_analytics, evaluate_history, waste_trends
from backend.app.core.config import settings
from backend.app.data.pipeline import DataValidationError, normalize_and_validate
from backend.app.data.repository import history_frame, import_frame, seed_database
from backend.app.db import models  # noqa: F401
from backend.app.db.models import PlanAudit
from backend.app.db.session import Base, engine, get_db
from backend.app.decision import propose_plan
from backend.app.forecasting import forecast_demand
from backend.app.schemas import (
    DecisionFeedback, ForecastRequest, ForecastResponse, HealthResponse,
    PlanRequest, PlanResponse,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "data" / "raw" / "meal_history.csv"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="Meal demand forecasting and kitchen decision-support API",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    seed_database(DEFAULT_CSV)


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "service": "messwise-api"}


@app.get(f"{settings.api_v1_prefix}/summary")
def summary(db: Session = Depends(get_db)):
    frame = history_frame(db)
    served = int(frame["served_portions"].sum()) if not frame.empty else 0
    waste = int(frame["waste_portions"].sum()) if not frame.empty else 0
    top_dishes = (
        frame.groupby("dish", as_index=False)["waste_portions"].sum()
        .sort_values("waste_portions", ascending=False).head(5).to_dict(orient="records")
        if not frame.empty else []
    )
    return {
        "records": int(len(frame)), "served_portions": served, "waste_portions": waste,
        "waste_rate": round(waste / served, 4) if served else 0,
        "top_waste_dishes": top_dishes,
    }


@app.get(f"{settings.api_v1_prefix}/history")
def history(limit: int = Query(default=100, ge=1, le=1000), db: Session = Depends(get_db)):
    frame = history_frame(db, limit=limit)
    frame = frame.astype(object).where(frame.notna(), None)
    return frame.to_dict(orient="records")


@app.get(f"{settings.api_v1_prefix}/analytics/trends")
def analytics_trends(db: Session = Depends(get_db)):
    return waste_trends(history_frame(db))


@app.get(f"{settings.api_v1_prefix}/analytics/dishes")
def analytics_dishes(db: Session = Depends(get_db)):
    return dish_waste_analytics(history_frame(db))


@app.get(f"{settings.api_v1_prefix}/evaluation")
def evaluation(db: Session = Depends(get_db)):
    return evaluate_history(history_frame(db))


@app.post(f"{settings.api_v1_prefix}/data/upload")
async def upload_history(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or Path(file.filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Upload a .csv file.")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="CSV must be 5 MB or smaller.")
    try:
        parsed = pd.read_csv(BytesIO(raw))
        validated = normalize_and_validate(parsed)
    except DataValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read CSV: {exc}") from exc
    inserted, skipped = import_frame(db, validated)
    return {
        "filename": Path(file.filename).name,
        "rows_received": int(len(validated)),
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "message": "Validated rows imported. Existing date/meal/dish keys were not overwritten.",
    }


@app.get(f"{settings.api_v1_prefix}/data/export")
def export_history(db: Session = Depends(get_db)):
    frame = history_frame(db)
    buffer = StringIO()
    frame.to_csv(buffer, index=False)
    return Response(
        content=buffer.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="messwise-history.csv"'},
    )


@app.post(f"{settings.api_v1_prefix}/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest, db: Session = Depends(get_db)):
    frame = history_frame(db)
    result = forecast_demand(
        frame, request.date, request.meal, request.dish,
        request.attendance, request.event_factor,
    )
    return {"date": request.date, "meal": request.meal, "dish": request.dish, **result}


@app.post(f"{settings.api_v1_prefix}/plans", response_model=PlanResponse)
def create_plan(request: PlanRequest, db: Session = Depends(get_db)):
    plan = propose_plan(
        history_frame(db), request.date, request.meal, request.dish,
        request.attendance, request.event_factor, request.extra_context,
        request.batch_size, request.minimum_buffer_pct,
    )
    audit = PlanAudit(
        date=request.date, meal=request.meal, dish=request.dish,
        forecast_portions=plan["forecast_portions"],
        recommended_portions=plan["recommended_portions"],
        batches=plan["batches"], batch_size=plan["batch_size"],
        expected_buffer_portions=plan["expected_buffer_portions"],
        explanation=json.dumps(plan["explanation"]),
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    plan["id"] = audit.id
    plan["explanation"] = plan["explanation"] + [f"Plan audit ID: {audit.id}."]
    return plan


@app.post(settings.api_v1_prefix + "/plans/{plan_id}/feedback")
def review_plan(plan_id: int, feedback: DecisionFeedback, db: Session = Depends(get_db)):
    audit = db.get(PlanAudit, plan_id)
    if audit is None:
        raise HTTPException(404, "Plan not found")
    if audit.status != "pending_review":
        raise HTTPException(409, f"Plan has already been reviewed as {audit.status}.")
    audit.status = "approved" if feedback.approved else "rejected"
    audit.reviewer = feedback.reviewer
    audit.review_note = feedback.note
    db.commit()
    return {"id": audit.id, "status": audit.status, "reviewer": audit.reviewer}


@app.get(f"{settings.api_v1_prefix}/plans")
def list_plans(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    records = db.query(PlanAudit).order_by(PlanAudit.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id, "date": row.date, "meal": row.meal, "dish": row.dish,
            "forecast_portions": row.forecast_portions,
            "recommended_portions": row.recommended_portions,
            "batches": row.batches, "batch_size": row.batch_size,
            "expected_buffer_portions": row.expected_buffer_portions,
            "explanation": json.loads(row.explanation or "[]"),
            "status": row.status, "reviewer": row.reviewer, "review_note": row.review_note,
        }
        for row in records
    ]
