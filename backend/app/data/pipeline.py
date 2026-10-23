from pathlib import Path
import pandas as pd

REQUIRED_COLUMNS = {
    "date", "meal", "dish", "planned_portions", "served_portions",
    "waste_portions", "attendance",
}
NUMERIC_COLUMNS = ["planned_portions", "served_portions", "waste_portions", "attendance"]
ALLOWED_MEALS = {"breakfast", "lunch", "snacks", "dinner"}


class DataValidationError(ValueError):
    """Raised when an input CSV violates the documented data contract."""


def load_csv(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV not found: {file_path}")
    try:
        frame = pd.read_csv(file_path)
    except Exception as exc:
        raise DataValidationError(f"Could not parse CSV: {exc}") from exc
    return normalize_and_validate(frame)


def normalize_and_validate(frame: pd.DataFrame) -> pd.DataFrame:
    df = frame.copy()
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise DataValidationError(f"Missing required columns: {', '.join(missing)}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    if df["date"].isna().any():
        raise DataValidationError("Column 'date' contains invalid or empty dates.")

    for column in ("meal", "dish"):
        df[column] = df[column].astype("string").str.strip()
        if df[column].isna().any() or (df[column] == "").any():
            raise DataValidationError(f"Column '{column}' contains empty values.")

    df["meal"] = df["meal"].str.lower()
    invalid_meals = sorted(set(df["meal"].dropna()) - ALLOWED_MEALS)
    if invalid_meals:
        raise DataValidationError(f"Unsupported meal values: {', '.join(invalid_meals)}")

    for column in NUMERIC_COLUMNS:
        values = pd.to_numeric(df[column], errors="coerce")
        if values.isna().any() or (values < 0).any() or (values % 1 != 0).any():
            raise DataValidationError(f"Column '{column}' must contain non-negative integers.")
        df[column] = values.astype("int64")

    if (df["waste_portions"] > df["served_portions"]).any():
        raise DataValidationError("waste_portions cannot exceed served_portions.")

    if "event_factor" not in df:
        df["event_factor"] = 1.0
    df["event_factor"] = pd.to_numeric(df["event_factor"], errors="coerce").fillna(1.0)
    if (df["event_factor"] <= 0).any():
        raise DataValidationError("event_factor must be positive.")

    if "is_weekend" not in df:
        df["is_weekend"] = pd.to_datetime(df["date"]).dt.dayofweek >= 5
    else:
        df["is_weekend"] = df["is_weekend"].map(
            lambda value: value if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "y"}
        )

    if "weather" not in df:
        df["weather"] = None
    return df.sort_values(["date", "meal", "dish"]).reset_index(drop=True)


def profile_csv(path: str | Path) -> dict:
    df = load_csv(path)
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "date_min": str(df["date"].min()) if len(df) else None,
        "date_max": str(df["date"].max()) if len(df) else None,
        "unique_dishes": int(df["dish"].nunique()),
        "meals": sorted(df["meal"].unique().tolist()),
        "total_served_portions": int(df["served_portions"].sum()),
        "total_waste_portions": int(df["waste_portions"].sum()),
        "waste_rate": round(float(df["waste_portions"].sum() / df["served_portions"].sum()), 4)
        if df["served_portions"].sum() else 0.0,
        "null_counts": {str(key): int(value) for key, value in df.isna().sum().items()},
    }
