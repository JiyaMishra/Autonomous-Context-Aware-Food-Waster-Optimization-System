import argparse
import json
from pathlib import Path

from backend.app.data.pipeline import load_csv, profile_csv
from backend.app.data.repository import import_frame
from backend.app.db.session import Base, SessionLocal, engine


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
        frame = load_csv(args.path)
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            inserted, skipped = import_frame(db, frame)
        print(f"Import complete: inserted={inserted}, skipped_existing={skipped}")


if __name__ == "__main__":
    main()
