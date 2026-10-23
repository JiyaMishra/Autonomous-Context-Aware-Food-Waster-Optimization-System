import argparse
import json
from pathlib import Path

import pandas as pd
from backend.app.data.pipeline import load_csv, profile_csv
from backend.app.db.models import MealHistory
from backend.app.db.session import Base, SessionLocal, engine


def import_csv(path: Path) -> None:
    frame = load_csv(path)
    Base.metadata.create_all(bind=engine)
    inserted = 0
    skipped = 0
    with SessionLocal() as db:
        existing = {
            (row.date, row.meal, row.dish)
            for row in db.query(MealHistory.date, MealHistory.meal, MealHistory.dish).all()
        }
        for row in frame.itertuples(index=False):
            key = (row.date, str(row.meal), str(row.dish))
            if key in existing:
                skipped += 1
                continue
            weather = None if pd.isna(row.weather) else str(row.weather)
            db.add(MealHistory(
                date=row.date, meal=str(row.meal), dish=str(row.dish),
                planned_portions=int(row.planned_portions),
                served_portions=int(row.served_portions),
                waste_portions=int(row.waste_portions), attendance=int(row.attendance),
                is_weekend=bool(row.is_weekend), event_factor=float(row.event_factor),
                weather=weather,
            ))
            existing.add(key)
            inserted += 1
        db.commit()
    print(f"Import complete: inserted={inserted}, skipped_existing={skipped}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MessWise CSV data tools")
    parser.add_argument("command", choices=["validate", "profile", "import"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        frame = load_csv(args.path)
        print(f"VALID: {len(frame)} rows; columns={len(frame.columns)}")
    elif args.command == "profile":
        print(json.dumps(profile_csv(args.path), indent=2))
    else:
        import_csv(args.path)


if __name__ == "__main__":
    main()
