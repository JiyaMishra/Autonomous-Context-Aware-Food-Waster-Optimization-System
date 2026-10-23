from datetime import date
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.db.session import Base, engine, get_db
from backend.app.db import models  # noqa: F401
from backend.app.db.models import PlanAudit
from backend.app.schemas import (HealthResponse, ForecastRequest, ForecastResponse,
                                 PlanRequest, PlanResponse, DecisionFeedback)
from backend.app.data.pipeline import load_csv
from backend.app.forecasting import forecast_demand
from backend.app.optimizer import optimize_batches
from backend.app.decision import propose_plan

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "data" / "raw" / "meal_history.csv"

app = FastAPI(title=settings.app_name, version="0.1.0",
              description="Meal demand forecasting and kitchen decision-support API")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok", "service": "messwise-api"}


@app.get(f"{settings.api_v1_prefix}/summary")
def summary():
    frame = load_csv(DEFAULT_CSV)
    served = int(frame["served_portions"].sum())
    waste = int(frame["waste_portions"].sum())
    dish_waste = frame.groupby("dish", as_index=False)["waste_portions"].sum()
    dish_waste = dish_waste.sort_values("waste_portions", ascending=False).head(5)
    return {"records": int(len(frame)), "served_portions": served, "waste_portions": waste,
            "waste_rate": round(waste / served, 4) if served else 0,
            "top_waste_dishes": dish_waste.to_dict(orient="records")}


@app.get(f"{settings.api_v1_prefix}/history")
def history(limit: int = 100):
    if not 1 <= limit <= 1000:
        raise HTTPException(400, "limit must be between 1 and 1000")
    frame = load_csv(DEFAULT_CSV).tail(limit)
    return frame.astype(object).where(frame.notna(), None).to_dict(orient="records")


@app.post(f"{settings.api_v1_prefix}/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest):
    frame = load_csv(DEFAULT_CSV)
    result = forecast_demand(frame, request.date, request.meal, request.dish,
                             request.attendance, request.event_factor)
    return {"date": request.date, "meal": request.meal, "dish": request.dish, **result}


@app.post(f"{settings.api_v1_prefix}/plans", response_model=PlanResponse)
def create_plan(request: PlanRequest, db: Session = Depends(get_db)):
    try:
        plan = propose_plan(str(DEFAULT_CSV), request.date, request.meal, request.dish,
                            request.attendance, request.event_factor, request.extra_context,
                            request.batch_size, request.minimum_buffer_pct)
    except FileNotFoundError as exc:
        raise HTTPException(500, str(exc)) from exc
    audit = PlanAudit(date=request.date, meal=request.meal, dish=request.dish,
                      forecast_portions=plan["forecast_portions"],
                      recommended_portions=plan["recommended_portions"])
    db.add(audit)
    db.commit()
    db.refresh(audit)
    plan["explanation"] = plan["explanation"] + [f"Plan audit ID: {audit.id}."]
    return plan


@app.post(f"{settings.api_v1_prefix}/plans/{{plan_id}}/feedback")
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
    return [{"id": row.id, "date": row.date, "meal": row.meal, "dish": row.dish,
             "forecast_portions": row.forecast_portions,
             "recommended_portions": row.recommended_portions, "status": row.status}
            for row in records]
