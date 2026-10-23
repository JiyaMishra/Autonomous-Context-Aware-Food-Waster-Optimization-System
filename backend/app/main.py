import json
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
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
    if frame.empty:
        return {
            "records": 0, "unique_dishes": 0, "service_days": 0,
            "waste_rate": 0.0, "average_waste_rate_pct": 0.0,
            "top_waste_dishes": [], "unit_breakdown": [],
        }
    dish_metrics = dish_waste_analytics(frame)
    if "waste_rate_pct" in frame.columns:
        row_rates = pd.to_numeric(frame["waste_rate_pct"], errors="coerce")
    else:
        prepared = pd.to_numeric(frame["prepared_portions"], errors="coerce").fillna(
            pd.to_numeric(frame["planned_portions"], errors="coerce")
        )
        row_rates = pd.to_numeric(frame["waste_portions"], errors="coerce").div(prepared.replace(0, float("nan"))) * 100
    row_rates = row_rates.fillna(0)
    unit_col = frame["quantity_unit_hint"].fillna("unspecified unit") if "quantity_unit_hint" in frame.columns else pd.Series(["unspecified unit"] * len(frame))
    unit_breakdown = []
    for unit, indices in frame.groupby(unit_col).groups.items():
        values = row_rates.loc[list(indices)]
        unit_breakdown.append({
            "unit": str(unit),
            "records": int(len(values)),
            "average_waste_rate_pct": round(float(values.mean()), 2) if len(values) else 0.0,
        })
    dates = pd.to_datetime(frame["date"]).dt.date.nunique()
    average_rate = round(float(row_rates.mean()), 2)
    return {
        "records": int(len(frame)),
        "unique_dishes": int(frame["dish"].nunique()),
        "service_days": int(dates),
        "waste_rate": round(average_rate / 100, 4),
        "average_waste_rate_pct": average_rate,
        "top_waste_dishes": dish_metrics[:5],
        "unit_breakdown": unit_breakdown,
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
async def upload_history(file: UploadFile = File(...), replace_existing: bool = Form(default=False), db: Session = Depends(get_db)):
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
    if replace_existing:
        db.query(models.MealHistory).delete(synchronize_session=False)
        db.flush()
    inserted, skipped = import_frame(db, validated)
    return {
        "filename": Path(file.filename).name,
        "rows_received": int(len(validated)),
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "replaced_existing": replace_existing,
        "message": (
            "Existing history was replaced with this validated dataset."
            if replace_existing else
            "Validated rows imported. Existing date/meal/dish keys were not overwritten."
        ),
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
        target_context={
            "synthetic_liking_score": request.synthetic_liking_score,
            "exam_intensity": request.exam_intensity,
            "temperature_c": request.temperature_c,
            "rainfall_mm": request.rainfall_mm,
            "historical_demand_rate": request.historical_demand_rate,
        },
    )
    return {"date": request.date, "meal": request.meal, "dish": request.dish, **result}


@app.post(f"{settings.api_v1_prefix}/plans", response_model=PlanResponse)
def create_plan(request: PlanRequest, db: Session = Depends(get_db)):
    plan = propose_plan(
        history_frame(db), request.date, request.meal, request.dish,
        request.attendance, request.event_factor, request.extra_context,
        request.batch_size, request.minimum_buffer_pct,
        context_features={
            "synthetic_liking_score": request.synthetic_liking_score,
            "exam_intensity": request.exam_intensity,
            "temperature_c": request.temperature_c,
            "rainfall_mm": request.rainfall_mm,
            "historical_demand_rate": request.historical_demand_rate,
        },
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
