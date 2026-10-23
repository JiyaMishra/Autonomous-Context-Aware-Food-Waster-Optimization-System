import pandas as pd
import pytest
from backend.app.data.pipeline import DataValidationError, normalize_and_validate


def sample():
    return pd.DataFrame([{
        "date": "2026-10-20", "meal": "Lunch", "dish": "Dal",
        "planned_portions": 100, "served_portions": 90, "waste_portions": 8,
        "attendance": 85,
    }])


def test_normalize_csv_contract():
    result = normalize_and_validate(sample())
    assert result.loc[0, "meal"] == "lunch"
    assert bool(result.loc[0, "is_weekend"]) is False
    assert float(result.loc[0, "event_factor"]) == 1.0


def test_reject_waste_above_served():
    frame = sample()
    frame.loc[0, "waste_portions"] = 99
    with pytest.raises(DataValidationError, match="cannot exceed"):
        normalize_and_validate(frame)


def test_reject_missing_column():
    with pytest.raises(DataValidationError, match="Missing required columns"):
        normalize_and_validate(sample().drop(columns=["attendance"]))
