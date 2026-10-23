import argparse
import json
from pathlib import Path
from backend.app.data.pipeline import load_csv, profile_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="MessWise CSV data tools")
    parser.add_argument("command", choices=["validate", "profile"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    if args.command == "validate":
        frame = load_csv(args.path)
        print(f"VALID: {len(frame)} rows; columns={len(frame.columns)}")
    else:
        print(json.dumps(profile_csv(args.path), indent=2))


if __name__ == "__main__":
    main()
