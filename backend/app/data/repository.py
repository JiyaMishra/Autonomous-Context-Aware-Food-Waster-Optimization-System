from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from backend.app.data.pipeline import load_csv
from backend.app.db.models import MealHistory
from backend.app.db.session import Base, SessionLocal, engine

HISTORY_COLUMNS = [
    "date", "meal", "dish", "planned_portions", "served_portions",
    "waste_portions", "attendance", "is_weekend", "event_factor", "weather",
    "day_of_week", "menu_version", "synthetic_liking_score", "exam_intensity",
    "temperature_c", "rainfall_mm", "hostel_attendance_estimate",
    "historical_demand_rate", "expected_consumers",
    "recommended_preparation_portions", "prepared_portions", "waste_rate_pct",
    "quantity_unit_hint",
]
OPTIONAL_TEXT_FIELDS = ["weather", "day_of_week", "quantity_unit_hint"]
OPTIONAL_INT_FIELDS = [
    "menu_version", "hostel_attendance_estimate", "expected_consumers",
    "recommended_preparation_portions", "prepared_portions",
]
OPTIONAL_FLOAT_FIELDS = [
    "synthetic_liking_score", "exam_intensity", "temperature_c", "rainfall_mm",
    "historical_demand_rate", "waste_rate_pct",
]


def _optional_value(row, field, converter):
    value = getattr(row, field, None)
    if value is None or pd.isna(value):
        return None
    return converter(value)


def import_frame(db: Session, frame: pd.DataFrame) -> tuple[int, int]:
    """Insert each date/meal/dish key once; retain source context and units."""
    existing = {
        (row.date, row.meal.strip().lower(), row.dish.strip().lower())
        for row in db.query(MealHistory.date, MealHistory.meal, MealHistory.dish).all()
    }
    inserted = skipped = 0
    for row in frame.itertuples(index=False):
        key = (row.date, str(row.meal).strip().lower(), str(row.dish).strip().lower())
        if key in existing:
            skipped += 1
            continue
        payload = {
            "date": row.date,
            "meal": str(row.meal).strip().lower(),
            "dish": str(row.dish).strip(),
            "planned_portions": int(row.planned_portions),
            "served_portions": int(row.served_portions),
            "waste_portions": int(row.waste_portions),
            "attendance": int(row.attendance),
            "is_weekend": bool(row.is_weekend),
            "event_factor": float(row.event_factor),
        }
        for field in OPTIONAL_TEXT_FIELDS:
            payload[field] = _optional_value(row, field, str)
        for field in OPTIONAL_INT_FIELDS:
            payload[field] = _optional_value(row, field, int)
        for field in OPTIONAL_FLOAT_FIELDS:
            payload[field] = _optional_value(row, field, float)
        db.add(MealHistory(**payload))
        existing.add(key)
        inserted += 1
    db.commit()
    return inserted, skipped


def seed_database(csv_path: str | Path) -> None:
    """Seed the small synthetic fixture only when explicitly enabled by config."""
    Base.metadata.create_all(bind=engine)
    # Real operators should upload their approved menu-history dataset. This
    # prevents the app from mixing demo records with the user's source dataset.
    import os
    if os.getenv("MESSWISE_SEED_DEMO_DATA", "false").strip().lower() not in {"1", "true", "yes"}:
        return
    with SessionLocal() as db:
        if db.query(MealHistory).count() == 0:
            inserted, _ = import_frame(db, load_csv(csv_path))
            if inserted:
                print(f"MessWise: seeded {inserted} synthetic sample rows into the database.")


def history_frame(db: Session, limit: int | None = None) -> pd.DataFrame:
    query = db.query(MealHistory)
    if limit is not None:
        rows = list(reversed(
            query.order_by(None).order_by(
                MealHistory.date.desc(), MealHistory.meal.desc(), MealHistory.dish.desc()
            ).limit(limit).all()
        ))
    else:
        rows = query.order_by(
            MealHistory.date.asc(), MealHistory.meal.asc(), MealHistory.dish.asc()
        ).all()

    records = [{
        "date": row.date,
        "meal": row.meal,
        "dish": row.dish,
        "planned_portions": row.planned_portions,
        "served_portions": row.served_portions,
        "waste_portions": row.waste_portions,
        "attendance": row.attendance,
        "is_weekend": row.is_weekend,
        "event_factor": row.event_factor,
        "weather": row.weather,
        "day_of_week": row.day_of_week,
        "menu_version": row.menu_version,
        "synthetic_liking_score": row.synthetic_liking_score,
        "exam_intensity": row.exam_intensity,
        "temperature_c": row.temperature_c,
        "rainfall_mm": row.rainfall_mm,
        "hostel_attendance_estimate": row.hostel_attendance_estimate,
        "historical_demand_rate": row.historical_demand_rate,
        "expected_consumers": row.expected_consumers,
        "recommended_preparation_portions": row.recommended_preparation_portions,
        "prepared_portions": row.prepared_portions,
        "waste_rate_pct": row.waste_rate_pct,
        "quantity_unit_hint": row.quantity_unit_hint,
    } for row in rows]
    if not records:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    return pd.DataFrame.from_records(records, columns=HISTORY_COLUMNS)
