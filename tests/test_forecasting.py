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



def test_context_features_blend_with_similar_earlier_observations():
    history = pd.DataFrame([
        {
            "date": date(2026, 8, day), "meal": "breakfast", "dish": "Aloo Paratha",
            "served_portions": 300 + day, "attendance": 400 + day,
            "synthetic_liking_score": 0.70 + day / 1000,
            "exam_intensity": 0.3, "temperature_c": 28.0,
            "rainfall_mm": 10.0, "historical_demand_rate": 0.75,
        }
        for day in range(1, 7)
    ])
    result = forecast_demand(
        history, date(2026, 8, 7), "breakfast", "Aloo Paratha", 420,
        target_context={
            "synthetic_liking_score": 0.71,
            "exam_intensity": 0.3,
            "temperature_c": 28.0,
            "rainfall_mm": 10.0,
            "historical_demand_rate": 0.75,
        },
    )
    assert result["method"] == "attendance_baseline_blended_with_context_analogs"
    assert result["predicted_portions"] > 0
    assert any("context-similar" in line for line in result["explanation"])
