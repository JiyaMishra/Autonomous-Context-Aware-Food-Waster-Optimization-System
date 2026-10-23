from pathlib import Path
import pandas as pd

REQUIRED_COLUMNS = {
    "date", "meal", "dish", "planned_portions", "served_portions",
    "waste_portions", "attendance",
}
NUMERIC_COLUMNS = ["planned_portions", "served_portions", "waste_portions", "attendance"]
OPTIONAL_NUMERIC_COLUMNS = [
    "menu_version", "synthetic_liking_score", "exam_intensity", "temperature_c",
    "rainfall_mm", "historical_demand_rate", "expected_consumers",
    "recommended_preparation_portions", "prepared_portions", "waste_rate_pct",
]
OPTIONAL_COLUMNS = OPTIONAL_NUMERIC_COLUMNS + ["quantity_unit_hint"]
ALLOWED_MEALS = {"breakfast", "lunch", "snacks", "dinner"}

# The August 2026 dataset is item-level data. Convert its names explicitly while
# retaining its contextual features for analytics and forecasting.
SOURCE_DATASET_COLUMNS = {
    "date", "meal", "food_item", "hostel_attendance_estimate",
    "recommended_preparation_portions", "prepared_portions",
    "consumed_portions", "leftover_portions",
}


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
    # Accept the supplied August menu dataset without asking the user to rename
    # its columns manually. "Consumed" remains distinct from "prepared".
    if SOURCE_DATASET_COLUMNS.issubset(df.columns):
        df = df.rename(columns={
            "food_item": "dish",
            "recommended_preparation_portions": "planned_portions",
            "consumed_portions": "served_portions",
            "leftover_portions": "waste_portions",
            "hostel_attendance_estimate": "attendance",
        })
        df["recommended_preparation_portions"] = df["planned_portions"]
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise DataValidationError(
            "Missing required columns: " + ", ".join(missing)
            + ". For the August menu dataset, keep the original food_item, "
            "prepared_portions, consumed_portions and leftover_portions columns."
        )

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

    for column in OPTIONAL_NUMERIC_COLUMNS:
        if column not in df:
            df[column] = None
        else:
            values = pd.to_numeric(df[column], errors="coerce")
            # Optional columns can be absent/blank, but nonblank nonnumeric input
            # should not silently turn into a missing value.
            original_nonblank = df[column].notna() & (df[column].astype(str).str.strip() != "")
            if (values.isna() & original_nonblank).any():
                raise DataValidationError(f"Column '{column}' must contain numeric values.")
            df[column] = values

    if "event_factor" not in df:
        df["event_factor"] = 1.0
    df["event_factor"] = pd.to_numeric(df["event_factor"], errors="coerce").fillna(1.0)
    if df["event_factor"].isna().any() or (df["event_factor"] <= 0).any():
        raise DataValidationError("event_factor must be positive.")

    if "is_weekend" not in df:
        df["is_weekend"] = pd.to_datetime(df["date"]).dt.dayofweek >= 5
    else:
        df["is_weekend"] = df["is_weekend"].map(
            lambda value: value if isinstance(value, bool)
            else str(value).strip().lower() in {"1", "true", "yes", "y"}
        )

    if "weather" not in df:
        df["weather"] = None
    if "quantity_unit_hint" not in df:
        df["quantity_unit_hint"] = None

    # Preserve actual prepared quantity and source waste percentage when present.
    if "prepared_portions" not in df:
        df["prepared_portions"] = None
    if "recommended_preparation_portions" not in df:
        df["recommended_preparation_portions"] = None

    return df.sort_values(["date", "meal", "dish"]).reset_index(drop=True)


def profile_csv(path: str | Path) -> dict:
    df = load_csv(path)
    prepared = df["prepared_portions"].fillna(df["planned_portions"]).sum()
    consumed = df["served_portions"].sum()
    waste = df["waste_portions"].sum()
    return {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "date_min": str(df["date"].min()) if len(df) else None,
        "date_max": str(df["date"].max()) if len(df) else None,
        "unique_dishes": int(df["dish"].nunique()),
        "meals": sorted(df["meal"].unique().tolist()),
        "total_prepared_portions": int(prepared),
        "total_consumed_portions": int(consumed),
        "total_waste_portions": int(waste),
        "waste_rate": round(float(waste / prepared), 4) if prepared else 0.0,
        "null_counts": {str(key): int(value) for key, value in df.isna().sum().items()},
    }
