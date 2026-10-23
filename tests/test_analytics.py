from datetime import date
import pandas as pd

from backend.app.analytics import dish_waste_analytics, evaluate_history, waste_trends


def sample_history():
    return pd.DataFrame([
        {"date": date(2026, 1, day), "meal": "lunch", "dish": "dal", "planned_portions": 20,
         "served_portions": 18 + day, "waste_portions": day % 4, "attendance": 25,
         "is_weekend": False, "event_factor": 1.0, "weather": None}
        for day in range(1, 9)
    ])


def test_waste_trends_returns_daily_totals_and_rates():
    rows = waste_trends(sample_history())
    assert len(rows) == 8
    assert rows[0]["date"] == "2026-01-01"
    assert rows[0]["records"] == 1
    assert rows[0]["average_waste_rate_pct"] > 0
    assert rows[0]["waste_rate"] > 0


def test_dish_analytics_calculates_rate():
    rows = dish_waste_analytics(sample_history())
    assert rows[0]["dish"] == "dal"
    assert rows[0]["records"] == 8
    assert 0 <= rows[0]["average_waste_rate_pct"] <= 100


def test_backtest_reports_metrics_with_enough_history():
    result = evaluate_history(sample_history(), minimum_observations=3)
    assert result["observations"] == 7
    assert result["metrics"] is not None
    assert set(result["metrics"]) == {"mae", "rmse", "wape"}


def test_backtest_explains_insufficient_history():
    result = evaluate_history(sample_history().head(2), minimum_observations=5)
    assert result["metrics"] is None
    assert "needed" in result["note"]
