import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.data.repository import history_frame, seed_database
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

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
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
    if frame.empty:
        top_dishes = []
    else:
        top_dishes = (
            frame.groupby("dish", as_index=False)["waste_portions"].sum()
            .sort_values("waste_portions", ascending=False).head(5)
            .to_dict(orient="records")
        )
    return {
        "records": int(len(frame)),
        "served_portions": served,
        "waste_portions": waste,
        "waste_rate": round(waste / served, 4) if served else 0,
        "top_waste_dishes": top_dishes,
    }


@app.get(f"{settings.api_v1_prefix}/history")
def history(limit: int = 100, db: Session = Depends(get_db)):
    if not 1 <= limit <= 1000:
        raise HTTPException(400, "limit must be between 1 and 1000")
    frame = history_frame(db, limit=limit)
    frame = frame.astype(object).where(frame.notna(), None)
    return frame.to_dict(orient="records")


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
    audit.status = "approved" if feedback.approved else "rejected"
    audit.reviewer = feedback.reviewer
    audit.review_note = feedback.note
    db.commit()
    return {"id": audit.id, "status": audit.status, "reviewer": audit.reviewer}


@app.get(f"{settings.api_v1_prefix}/plans")
def list_plans(limit: int = 100, db: Session = Depends(get_db)):
    if not 1 <= limit <= 500:
        raise HTTPException(400, "limit must be between 1 and 500")
    records = db.query(PlanAudit).order_by(PlanAudit.id.desc()).limit(limit).all()
    return [
        {
            "id": row.id, "date": row.date, "meal": row.meal, "dish": row.dish,
            "forecast_portions": row.forecast_portions,
            "recommended_portions": row.recommended_portions,
            "batches": row.batches, "batch_size": row.batch_size,
            "expected_buffer_portions": row.expected_buffer_portions,
            "explanation": json.loads(row.explanation or "[]"),
            "status": row.status,
        }
        for row in records
    ]
