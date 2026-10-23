from datetime import date
import pandas as pd
import pytest
from backend.app.forecasting import forecast_demand, evaluate_predictions


def test_fallback_forecast_without_history():
    frame = pd.DataFrame(columns=["meal", "dish", "date", "served_portions", "attendance"])
    result = forecast_demand(frame, date(2026, 10, 24), "lunch", "dal", 100)
    assert result["predicted_portions"] == 75
    assert result["confidence"] == "low"


def test_evaluation_metrics():
    result = evaluate_predictions([10, 20, 30], [12, 18, 30])
    assert result["mae"] == pytest.approx(1.333, abs=0.001)
    assert result["rmse"] == pytest.approx(1.633, abs=0.001)
    assert result["wape"] == pytest.approx(0.0667, abs=0.001)


def test_metrics_reject_empty_input():
    with pytest.raises(ValueError):
        evaluate_predictions([], [])
