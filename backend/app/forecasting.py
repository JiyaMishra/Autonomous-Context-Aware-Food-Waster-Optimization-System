from datetime import date
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


def forecast_demand(history: pd.DataFrame, target_date: date, meal: str, dish: str,
                    attendance: int, event_factor: float = 1.0) -> dict:
    subset = history[(history["meal"].str.lower() == meal.lower()) &
                     (history["dish"].str.lower() == dish.lower())].copy()
    reasons: list[str] = []
    if subset.empty:
        # Transparent safe fallback: attendance is a proxy, not a learned relationship.
        estimate = max(0, int(round(attendance * 0.75 * event_factor)))
        reasons.append("No matching history; used the documented attendance-based fallback.")
        return {"predicted_portions": estimate, "method": "attendance_fallback",
                "confidence": "low", "explanation": reasons}

    subset["date"] = pd.to_datetime(subset["date"])
    recent = subset[subset["date"].dt.date < target_date].sort_values("date").tail(28)
    if recent.empty:
        estimate = max(0, int(round(attendance * 0.75 * event_factor)))
        reasons.append("No earlier observations for this meal and dish; used attendance fallback.")
        return {"predicted_portions": estimate, "method": "attendance_fallback",
                "confidence": "low", "explanation": reasons}

    observed = recent["served_portions"].astype(float)
    median = float(observed.median())
    attendance_median = float(recent["attendance"].median()) if recent["attendance"].median() > 0 else 0.0
    if attendance_median > 0 and attendance > 0:
        estimate = median * (attendance / attendance_median)
        method = "recent_median_scaled_by_attendance"
        reasons.append("Used the median of up to 28 earlier matching observations, scaled by attendance.")
    else:
        estimate = median
        method = "recent_median"
        reasons.append("Used the median of up to 28 earlier matching observations.")
    estimate *= event_factor
    return {"predicted_portions": max(0, int(round(estimate))), "method": method,
            "confidence": "medium" if len(recent) >= 14 else "low",
            "explanation": reasons + [f"Used {len(recent)} historical observations."]}


def evaluate_predictions(actual, predicted) -> dict:
    if len(actual) == 0 or len(actual) != len(predicted):
        raise ValueError("actual and predicted must have equal, non-empty lengths")
    actual_array = np.asarray(actual, dtype=float)
    predicted_array = np.asarray(predicted, dtype=float)
    mae = mean_absolute_error(actual_array, predicted_array)
    rmse = float(np.sqrt(mean_squared_error(actual_array, predicted_array)))
    denominator = float(np.abs(actual_array).sum())
    wape = float(np.abs(actual_array - predicted_array).sum() / denominator) if denominator else 0.0
    return {"mae": round(float(mae), 3), "rmse": round(rmse, 3), "wape": round(wape, 4)}
