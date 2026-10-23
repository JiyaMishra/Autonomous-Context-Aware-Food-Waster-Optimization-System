from datetime import date
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

CONTEXT_SCALES = {
    "synthetic_liking_score": 1.0,
    "exam_intensity": 1.0,
    "temperature_c": 10.0,
    "rainfall_mm": 30.0,
    "historical_demand_rate": 1.0,
}


def _context_adjusted_estimate(recent: pd.DataFrame, target_context: dict) -> tuple[float | None, int]:
    """Find earlier same-dish rows with the most similar observed context."""
    usable = {
        name: float(value)
        for name, value in (target_context or {}).items()
        if name in CONTEXT_SCALES and value is not None and name in recent.columns
    }
    if not usable:
        return None, 0
    distances = []
    for _, row in recent.iterrows():
        deltas = []
        for name, target in usable.items():
            value = pd.to_numeric(pd.Series([row.get(name)]), errors="coerce").iloc[0]
            if pd.notna(value):
                deltas.append(abs(float(value) - target) / CONTEXT_SCALES[name])
        distances.append(float(np.mean(deltas)) if deltas else float("inf"))
    ranked = recent.copy()
    ranked["_context_distance"] = distances
    ranked = ranked[np.isfinite(ranked["_context_distance"])].sort_values("_context_distance").head(8)
    if ranked.empty:
        return None, 0
    # A context analogue is scaled to the requested service attendance too.
    median_demand = float(ranked["served_portions"].median())
    median_attendance = float(pd.to_numeric(ranked["attendance"], errors="coerce").median())
    target_attendance = float(pd.to_numeric(pd.Series([ranked.iloc[0].get("attendance")]), errors="coerce").iloc[0])
    # Scaling is done by the caller when its target attendance is known.
    return median_demand, int(len(ranked))


def forecast_demand(history: pd.DataFrame, target_date: date, meal: str, dish: str,
                    attendance: int, event_factor: float = 1.0,
                    target_context: dict | None = None) -> dict:
    subset = history[(history["meal"].str.lower() == meal.lower()) &
                     (history["dish"].str.lower() == dish.lower())].copy()
    reasons: list[str] = []
    if subset.empty:
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

    context_estimate, context_rows = _context_adjusted_estimate(recent, target_context or {})
    if context_estimate is not None:
        context_attendance_median = float(recent["attendance"].median()) if recent["attendance"].median() > 0 else 0.0
        if context_attendance_median > 0 and attendance > 0:
            context_estimate *= attendance / context_attendance_median
        estimate = 0.7 * estimate + 0.3 * context_estimate
        method = "attendance_baseline_blended_with_context_analogs"
        reasons.append(
            f"Blended 70% attendance-scaled baseline with 30% of {context_rows} earlier, context-similar records."
        )
    else:
        reasons.append("No target context features supplied; contextual matching was not applied.")

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
