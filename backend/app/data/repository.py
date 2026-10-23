from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from backend.app.data.pipeline import load_csv
from backend.app.db.models import MealHistory
from backend.app.db.session import Base, SessionLocal, engine

HISTORY_COLUMNS = [
    "date", "meal", "dish", "planned_portions", "served_portions",
    "waste_portions", "attendance", "is_weekend", "event_factor", "weather",
]


def import_frame(db: Session, frame: pd.DataFrame) -> tuple[int, int]:
    """Insert date/meal/dish keys once; do not silently overwrite operator data."""
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
        weather = None if pd.isna(row.weather) else str(row.weather)
        db.add(MealHistory(
            date=row.date,
            meal=str(row.meal).strip().lower(),
            dish=str(row.dish).strip(),
            planned_portions=int(row.planned_portions),
            served_portions=int(row.served_portions),
            waste_portions=int(row.waste_portions),
            attendance=int(row.attendance),
            is_weekend=bool(row.is_weekend),
            event_factor=float(row.event_factor),
            weather=weather,
        ))
        existing.add(key)
        inserted += 1
    db.commit()
    return inserted, skipped


def seed_database(csv_path: str | Path) -> None:
    """Seed an empty database from the bundled sample, without duplicating rows."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(MealHistory).count() == 0:
            inserted, _ = import_frame(db, load_csv(csv_path))
            if inserted:
                print(f"MessWise: seeded {inserted} synthetic sample rows into the database.")


def history_frame(db: Session, limit: int | None = None) -> pd.DataFrame:
    query = db.query(MealHistory).order_by(
        MealHistory.date.asc(), MealHistory.meal.asc(), MealHistory.dish.asc()
    )
    if limit is not None:
        query = query.order_by(
            MealHistory.date.desc(), MealHistory.meal.desc(), MealHistory.dish.desc()
        ).limit(limit)
        rows = list(reversed(query.all()))
    else:
        rows = query.all()

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
    } for row in rows]
    if not records:
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    return pd.DataFrame.from_records(records, columns=HISTORY_COLUMNS)
