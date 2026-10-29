import json
from io import BytesIO, StringIO
from pathlib import Path

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.analytics import dish_waste_analytics, evaluate_history, meal_waste_analytics, waste_trends
from backend.app.assistant import answer_assistant_query
from backend.app.attendance_predictor import predict_attendance
from backend.app.core.config import settings
from backend.app.data.pipeline import DataValidationError, normalize_and_validate
from backend.app.data.repository import history_frame, import_frame, seed_database
from backend.app.db import models  # noqa: F401
from backend.app.db.models import PlanAudit
from backend.app.db.session import Base, engine, get_db
from backend.app.decision import propose_plan
from backend.app.forecasting import forecast_demand
from backend.app.schemas import (
    AttendancePredictionRequest, AttendancePredictionResponse,
    ChatRequest, ChatResponse, DecisionFeedback, ForecastRequest,
    ForecastResponse, HealthResponse, PlanRequest, PlanResponse,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "data" / "raw" / "messwise_full_august_2026_menu_dataset.csv"
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
    source_rates = (
        pd.to_numeric(frame["waste_rate_pct"], errors="coerce")
        if "waste_rate_pct" in frame.columns else pd.Series(float("nan"), index=frame.index)
    )
    prepared = (
        pd.to_numeric(frame["prepared_portions"], errors="coerce")
        if "prepared_portions" in frame.columns else pd.Series(float("nan"), index=frame.index)
    )
    prepared = prepared.fillna(pd.to_numeric(frame["planned_portions"], errors="coerce"))
    fallback_rates = pd.to_numeric(frame["waste_portions"], errors="coerce").div(
        prepared.replace(0, float("nan"))
    ) * 100
    row_rates = source_rates.fillna(fallback_rates).fillna(0)
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


@app.get(f"{settings.api_v1_prefix}/menu")
def menu_for_service_date(
    date: str = Query(..., description="Target service date YYYY-MM-DD"),
    meal: str = Query(..., min_length=1, max_length=32),
    db: Session = Depends(get_db),
):
    """Reuse the source month's day-of-month menu for any target month/year."""
    try:
        target = pd.Timestamp(date).date()
    except Exception as exc:
        raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc
    frame = history_frame(db)
    if frame.empty:
        return {"date": str(target), "meal": meal.lower(), "template_day": target.day, "items": []}
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    matched = frame[
        (frame["date"].dt.day == target.day) &
        (frame["meal"].astype(str).str.lower() == meal.lower())
    ].copy()
    if matched.empty:
        return {"date": str(target), "meal": meal.lower(), "template_day": target.day, "items": []}
    items = []
    for _, row in matched.sort_values("dish").iterrows():
        def value(field):
            val = row.get(field)
            return None if pd.isna(val) else val.item() if hasattr(val, "item") else val
        items.append({
            "dish": str(row["dish"]),
            "template_date": str(pd.Timestamp(row["date"]).date()),
            "served_portions": value("served_portions"),
            "prepared_portions": value("prepared_portions") or value("planned_portions"),
            "waste_portions": value("waste_portions"),
            "attendance": value("attendance"),
            "synthetic_liking_score": value("synthetic_liking_score"),
            "exam_intensity": value("exam_intensity"),
            "temperature_c": value("temperature_c"),
            "rainfall_mm": value("rainfall_mm"),
            "historical_demand_rate": value("historical_demand_rate"),
            "quantity_unit_hint": value("quantity_unit_hint"),
            "waste_rate_pct": value("waste_rate_pct"),
        })
    return {"date": str(target), "meal": meal.lower(), "template_day": target.day, "template_month": "August 2026", "items": items}


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


@app.get(f"{settings.api_v1_prefix}/analytics/meals")
def analytics_meals(db: Session = Depends(get_db)):
    return meal_waste_analytics(history_frame(db))


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


@app.post(f"{settings.api_v1_prefix}/predict-attendance", response_model=AttendancePredictionResponse)
def predict_attendance_endpoint(request: AttendancePredictionRequest, db: Session = Depends(get_db)):
    """AI-driven attendance prediction using weather, exam calendar, and ML model."""
    frame = history_frame(db)
    weather_override = None
    if request.temperature_c is not None:
        weather_override = {
            "temperature_c": request.temperature_c,
            "rainfall_mm": request.rainfall_mm or 0.0,
            "source": "user parameter adjustment",
        }
    prediction = predict_attendance(
        frame, request.date, request.meal,
        weather_override=weather_override,
        exam_override=request.exam_intensity,
        exam_label_override=request.exam_label,
        campus_situation=request.campus_situation,
        campus_factor=request.campus_factor,
        total_registered=request.total_registered,
    )
    return {"date": request.date, "meal": request.meal, **prediction}


@app.post(f"{settings.api_v1_prefix}/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest, db: Session = Depends(get_db)):
    frame = history_frame(db)
    # Auto-predict attendance if not provided by the user.
    auto_attendance = None
    attendance = request.attendance
    if attendance is None:
        weather_override = None
        if request.temperature_c is not None:
            weather_override = {
                "temperature_c": request.temperature_c,
                "rainfall_mm": request.rainfall_mm or 0.0,
                "source": "user parameter adjustment",
            }
        prediction = predict_attendance(
            frame, request.date, request.meal,
            weather_override=weather_override,
            exam_override=request.exam_intensity,
            exam_label_override=request.exam_label,
            campus_situation=request.campus_situation,
            campus_factor=request.campus_factor,
        )
        attendance = prediction["predicted_attendance"]
        auto_attendance = attendance
    result = forecast_demand(
        frame, request.date, request.meal, request.dish,
        attendance, request.event_factor,
        target_context={
            "synthetic_liking_score": request.synthetic_liking_score,
            "exam_intensity": request.exam_intensity,
            "temperature_c": request.temperature_c,
            "rainfall_mm": request.rainfall_mm,
            "historical_demand_rate": request.historical_demand_rate,
        },
    )
    return {
        "date": request.date, "meal": request.meal, "dish": request.dish,
        "auto_predicted_attendance": auto_attendance, **result,
    }


@app.post(f"{settings.api_v1_prefix}/plans", response_model=PlanResponse)
def create_plan(request: PlanRequest, db: Session = Depends(get_db)):
    frame = history_frame(db)
    # Auto-predict attendance if not provided by the user.
    auto_attendance = None
    attendance = request.attendance
    if attendance is None:
        weather_override = None
        if request.temperature_c is not None:
            weather_override = {
                "temperature_c": request.temperature_c,
                "rainfall_mm": request.rainfall_mm or 0.0,
                "source": "user parameter adjustment",
            }
        prediction = predict_attendance(
            frame, request.date, request.meal,
            weather_override=weather_override,
            exam_override=request.exam_intensity,
            exam_label_override=request.exam_label,
            campus_situation=request.campus_situation,
            campus_factor=request.campus_factor,
        )
        attendance = prediction["predicted_attendance"]
        auto_attendance = attendance
    plan = propose_plan(
        frame, request.date, request.meal, request.dish,
        attendance, request.event_factor, request.extra_context,
        request.batch_size, request.minimum_buffer_pct,
        context_features={
            "synthetic_liking_score": request.synthetic_liking_score,
            "exam_intensity": request.exam_intensity,
            "temperature_c": request.temperature_c,
            "rainfall_mm": request.rainfall_mm,
            "historical_demand_rate": request.historical_demand_rate,
        },
    )
    if auto_attendance is not None:
        plan["explanation"].insert(0, f"AI predicted attendance: {auto_attendance} students (predicted from weather, exam, and campus parameters).")
    plan["auto_predicted_attendance"] = auto_attendance
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


@app.delete(f"{settings.api_v1_prefix}/plans")
def clear_plans(db: Session = Depends(get_db)):
    deleted = db.query(PlanAudit).delete()
    db.commit()
    return {"message": f"Cleared {deleted} plan(s)."}


@app.post(f"{settings.api_v1_prefix}/assistant/chat", response_model=ChatResponse)
def assistant_chat(request: ChatRequest, db: Session = Depends(get_db)):
    """AI Assistant endpoint for answering kitchen operator questions with live dataset insights."""
    reply, suggestions = answer_assistant_query(db, request.message, request.context)
    return {"reply": reply, "suggestions": suggestions}


