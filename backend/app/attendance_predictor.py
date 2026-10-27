"""AI-driven attendance prediction using Gradient Boosted Trees.

Trains a lightweight model on historical (date, meal) → attendance data,
using weather, exam intensity, and calendar features. Automatically fetches
weather from Open-Meteo and exam intensity from the academic calendar when
those values are not provided by the caller.
"""
from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder

from backend.app.academic_calendar import get_exam_intensity
from backend.app.weather import get_weather

logger = logging.getLogger(__name__)

# Meals we train on — must match the allowed meals in the data pipeline.
KNOWN_MEALS = ["breakfast", "lunch", "snacks", "dinner"]

# Realistic default for total hostel capacity (August dataset attendance reaches 660).
DEFAULT_TOTAL_REGISTERED = 700


def _clean_val(val: any, default: float) -> float:
    """Safely convert value to float, replacing None, NaN, inf, or errors with default."""
    if val is None or pd.isna(val):
        return default
    try:
        f = float(val)
        return default if np.isnan(f) or np.isinf(f) else f
    except (ValueError, TypeError):
        return default


def _build_features(row: dict) -> list[float]:
    """Convert a single observation dict into a flat numeric feature vector.

    Feature order (13 features):
        [0]  day_of_week      (0=Mon … 6=Sun)
        [1]  is_weekend       (0 or 1)
        [2]  day_of_month     (1–31)
        [3]  week_of_month    (0–4)
        [4]  meal_breakfast   (one-hot)
        [5]  meal_lunch
        [6]  meal_snacks
        [7]  meal_dinner
        [8]  temperature_c
        [9]  rainfall_mm
        [10] exam_intensity
        [11] sin_day_of_week  (cyclical encoding)
        [12] cos_day_of_week
    """
    dow = int(_clean_val(row.get("day_of_week_num"), 0.0))
    is_wknd = _clean_val(row.get("is_weekend"), 0.0)
    dom = _clean_val(row.get("day_of_month"), 15.0)
    wom = _clean_val(row.get("week_of_month"), 2.0)

    meal = str(row.get("meal", "")).lower()
    meal_onehot = [
        1.0 if meal == "breakfast" else 0.0,
        1.0 if meal == "lunch" else 0.0,
        1.0 if meal == "snacks" else 0.0,
        1.0 if meal == "dinner" else 0.0,
    ]

    temp = _clean_val(row.get("temperature_c"), 28.0)
    rain = _clean_val(row.get("rainfall_mm"), 5.0)
    exam = _clean_val(row.get("exam_intensity"), 0.0)

    # Cyclical day-of-week encoding for weekly periodicity.
    sin_dow = float(np.sin(2 * np.pi * dow / 7))
    cos_dow = float(np.cos(2 * np.pi * dow / 7))

    return [float(dow), float(is_wknd), float(dom), float(wom)] + meal_onehot + [temp, rain, exam, sin_dow, cos_dow]


def _aggregate_to_meal_level(history: pd.DataFrame) -> pd.DataFrame:
    """Aggregate item-level history to (date, meal) → attendance level."""
    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"])

    # Each (date, meal) has a single attendance value; take the first.
    agg_cols = {"attendance": "first"}

    # Preserve context features if present.
    for col in ["temperature_c", "rainfall_mm", "exam_intensity", "is_weekend"]:
        if col in frame.columns:
            agg_cols[col] = "first"

    frame["date_val"] = frame["date"].dt.date
    grouped = frame.groupby(["date_val", "meal"], as_index=False).agg(agg_cols)
    grouped = grouped.rename(columns={"date_val": "date"})

    # Derive calendar features.
    dates = pd.to_datetime(grouped["date"])
    grouped["day_of_week_num"] = dates.dt.dayofweek
    grouped["day_of_month"] = dates.dt.day
    grouped["week_of_month"] = (dates.dt.day - 1) // 7

    if "is_weekend" not in grouped.columns:
        grouped["is_weekend"] = (dates.dt.dayofweek >= 5).astype(int)
    else:
        grouped["is_weekend"] = grouped["is_weekend"].astype(int)

    return grouped


def _train_model(training_data: pd.DataFrame) -> tuple[GradientBoostingRegressor, float]:
    """Train a GBT regressor on aggregated meal-level data.

    Returns the fitted model and its training RMSE for confidence estimation.
    """
    features = []
    targets = []

    for _, row in training_data.iterrows():
        att_raw = row.get("attendance")
        if att_raw is None or pd.isna(att_raw):
            continue
        try:
            att = float(att_raw)
            if np.isnan(att) or np.isinf(att):
                continue
        except (ValueError, TypeError):
            continue
        features.append(_build_features(row.to_dict()))
        targets.append(att)

    if len(targets) < 3:
        raise ValueError("Not enough valid attendance samples to train model.")

    X = np.array(features, dtype=float)
    y = np.array(targets, dtype=float)

    model = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        min_samples_leaf=2,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X, y)

    # Compute training RMSE for confidence assessment.
    predictions = model.predict(X)
    rmse = float(np.sqrt(np.mean((y - predictions) ** 2)))

    return model, rmse


def _confidence_label(rmse: float, n_training: int) -> str:
    """Heuristic confidence level based on training RMSE and sample size."""
    if n_training < 10:
        return "low"
    if rmse < 20 and n_training >= 20:
        return "high"
    if rmse < 40:
        return "medium"
    return "low"


def _describe_weather_effect(
    temp_c: float, rain_mm: float, avg_temp: float, avg_rain: float,
) -> str:
    """Generate a human-readable description of weather impact."""
    effects = []

    temp_diff = temp_c - avg_temp
    if abs(temp_diff) < 2:
        effects.append("Temperature is near average — minimal impact")
    elif temp_diff > 5:
        effects.append(f"Unusually hot ({temp_c:.0f}°C vs {avg_temp:.0f}°C avg) — may slightly reduce attendance")
    elif temp_diff < -5:
        effects.append(f"Unusually cool ({temp_c:.0f}°C vs {avg_temp:.0f}°C avg) — may slightly increase attendance")
    else:
        effects.append(f"Temperature {'above' if temp_diff > 0 else 'below'} average by {abs(temp_diff):.0f}°C")

    if rain_mm < 1:
        effects.append("No significant rain expected")
    elif rain_mm < 10:
        effects.append(f"Light rain ({rain_mm:.0f}mm) — minimal attendance impact")
    elif rain_mm < 30:
        effects.append(f"Moderate rain ({rain_mm:.0f}mm) — expect slight reduction (~3–5%)")
    else:
        effects.append(f"Heavy rain ({rain_mm:.0f}mm) — expect noticeable reduction (~5–10%)")

    return "; ".join(effects)


def _describe_day_effect(target_date: date, is_weekend: bool) -> str:
    """Describe the day-of-week pattern."""
    day_name = target_date.strftime("%A")
    if is_weekend:
        return f"{day_name} (weekend) — typically lower attendance than weekdays"
    return f"{day_name} (weekday) — typical attendance pattern"


def predict_attendance(
    history: pd.DataFrame,
    target_date: date,
    meal: str,
    weather_override: dict | None = None,
    exam_override: float | None = None,
    exam_label_override: str | None = None,
    campus_situation: str | None = None,
    campus_factor: float = 1.0,
    total_registered: int | None = None,
) -> dict:
    """Predict the expected attendance for a (date, meal) combination.

    The model trains on-the-fly from the stored history using GBT.
    Weather is fetched from Open-Meteo or supplied by user parameter override.
    Exam intensity defaults to normal (0.0) or user parameter override.
    Campus situation adjustments (e.g. students went home, fest) scale the prediction.
    """
    total_reg = total_registered or DEFAULT_TOTAL_REGISTERED
    c_factor = float(campus_factor) if campus_factor is not None else 1.0

    # ── 1. Get weather ───────────────────────────────────────────────
    if weather_override and weather_override.get("temperature_c") is not None:
        weather = {
            "temperature_c": float(weather_override["temperature_c"]),
            "rainfall_mm": float(weather_override.get("rainfall_mm", 0.0)),
            "source": weather_override.get("source", "user parameter adjustment"),
        }
    else:
        weather = get_weather(target_date, meal, history)

    # ── 2. Get exam intensity ────────────────────────────────────────
    if exam_override is not None:
        intensity = float(exam_override)
        if intensity == 0.0:
            label = exam_label_override or "No exams (normal schedule)"
            desc = "Regular semester classes — normal dining attendance pattern"
            is_period = False
        else:
            label = exam_label_override or f"Exam Period ({int(intensity * 100)}% intensity)"
            desc = f"{label} ({int(intensity * 100)}% intensity): estimated {int(intensity * 20)}% reduction in dining turnout"
            is_period = True
        exam_info = {
            "exam_intensity": intensity,
            "exam_label": label,
            "is_exam_period": is_period,
            "is_ramp_up": False,
            "days_until_exam": None,
            "effect_description": desc,
        }
    else:
        exam_info = get_exam_intensity(target_date)

    # ── 3. Prepare training data ─────────────────────────────────────
    training_data = _aggregate_to_meal_level(history)

    if len(training_data) < 3:
        # Too few records to train; use a simple heuristic.
        fallback = _heuristic_attendance(
            history, meal, target_date, weather, exam_info, total_reg,
            campus_situation=campus_situation, campus_factor=c_factor,
        )
        return fallback

    # ── 4. Train and predict ─────────────────────────────────────────
    try:
        model, rmse = _train_model(training_data)
        n_training = len(training_data)

        # Build feature vector for the target date.
        is_weekend = target_date.weekday() >= 5
        target_features = _build_features({
            "day_of_week_num": target_date.weekday(),
            "is_weekend": int(is_weekend),
            "day_of_month": target_date.day,
            "week_of_month": (target_date.day - 1) // 7,
            "meal": meal.lower(),
            "temperature_c": weather["temperature_c"],
            "rainfall_mm": weather["rainfall_mm"],
            "exam_intensity": exam_info["exam_intensity"],
        })

        raw_pred = model.predict([target_features])[0]
        # Apply campus situational factor (e.g. students went home, fest)
        scaled_pred = raw_pred * c_factor
        predicted_attendance = max(0, min(int(round(scaled_pred)), total_reg))
    except Exception as exc:
        logger.warning("ML training or prediction failed (%s); using heuristic fallback.", exc)
        return _heuristic_attendance(
            history, meal, target_date, weather, exam_info, total_reg,
            campus_situation=campus_situation, campus_factor=c_factor,
        )

    # ── 5. Compute averages for comparison / explanation ──────────────
    avg_temp = float(
        pd.to_numeric(history.get("temperature_c"), errors="coerce").dropna().mean()
    ) if "temperature_c" in history.columns and not history.empty else 28.0
    avg_rain = float(
        pd.to_numeric(history.get("rainfall_mm"), errors="coerce").dropna().mean()
    ) if "rainfall_mm" in history.columns and not history.empty else 5.0

    turnout_pct = round(predicted_attendance / total_reg * 100, 1) if total_reg > 0 else 0

    # ── 6. Build explanatory factors ─────────────────────────────────
    weather_effect = _describe_weather_effect(
        weather["temperature_c"], weather["rainfall_mm"], avg_temp, avg_rain,
    )
    exam_effect = exam_info["effect_description"]
    day_effect = _describe_day_effect(target_date, is_weekend)

    factors_summary = [
        f"{target_date.strftime('%A')} {meal} typically sees ~{turnout_pct}% turnout",
        weather_effect,
        exam_effect,
    ]
    if campus_situation and abs(c_factor - 1.0) > 0.01:
        change_pct = int((c_factor - 1.0) * 100)
        factors_summary.append(f"Campus situation ({campus_situation}): {change_pct:+d}% turnout adjustment")

    confidence = _confidence_label(rmse, n_training)

    return {
        "predicted_attendance": predicted_attendance,
        "predicted_absent": max(0, total_reg - predicted_attendance),
        "total_registered": total_reg,
        "turnout_pct": turnout_pct,
        "weather": weather,
        "exam": {
            "intensity": exam_info["exam_intensity"],
            "label": exam_info.get("exam_label"),
            "is_exam_period": exam_info["is_exam_period"],
            "is_ramp_up": exam_info.get("is_ramp_up", False),
            "effect": exam_effect,
        },
        "campus_situation": campus_situation,
        "campus_factor": c_factor,
        "confidence": confidence,
        "method": "gradient_boosted_regression",
        "training_samples": n_training,
        "training_rmse": round(rmse, 1),
        "factors": {
            "weather_effect": weather_effect,
            "exam_effect": exam_effect,
            "day_effect": day_effect,
            "campus_effect": f"{campus_situation or 'Normal'} (factor: {c_factor})",
        },
        "factors_summary": factors_summary,
        "parameters_used": {
            "exam_intensity": exam_info["exam_intensity"],
            "exam_label": exam_info.get("exam_label"),
            "temperature_c": weather.get("temperature_c"),
            "rainfall_mm": weather.get("rainfall_mm"),
            "campus_situation": campus_situation,
            "campus_factor": c_factor,
        },
    }


def _heuristic_attendance(
    history: pd.DataFrame,
    meal: str,
    target_date: date,
    weather: dict,
    exam_info: dict,
    total_registered: int,
    campus_situation: str | None = None,
    campus_factor: float = 1.0,
) -> dict:
    """Simple rule-based fallback when there's not enough data to train."""
    c_factor = float(campus_factor) if campus_factor is not None else 1.0

    # Use historical average for the same meal if available.
    frame = history.copy()
    if not frame.empty:
        meal_rows = frame[frame["meal"].str.lower() == meal.lower()]
        if not meal_rows.empty:
            base = float(pd.to_numeric(meal_rows["attendance"], errors="coerce").median())
        else:
            base = float(pd.to_numeric(frame["attendance"], errors="coerce").median())
    else:
        # No data at all — rough estimate.
        base_rates = {"breakfast": 0.7, "lunch": 0.85, "snacks": 0.55, "dinner": 0.80}
        base = total_registered * base_rates.get(meal.lower(), 0.75)

    # Adjust for exam intensity.
    exam_reduction = exam_info["exam_intensity"] * 0.15  # Up to 15% reduction.
    # Adjust for rain.
    rain_mm = weather.get("rainfall_mm", 0) or 0
    rain_reduction = min(0.10, rain_mm / 300)  # Up to 10% for very heavy rain.
    # Weekend adjustment.
    is_weekend = target_date.weekday() >= 5
    weekend_factor = 0.85 if is_weekend else 1.0

    predicted = int(round(base * (1 - exam_reduction) * (1 - rain_reduction) * weekend_factor * c_factor))
    predicted = max(0, min(predicted, total_registered))

    factors_summary = [
        f"Heuristic estimate (insufficient training data)",
        f"Based on historical {meal} median attendance of {base:.0f}",
        exam_info["effect_description"],
    ]
    if campus_situation and abs(c_factor - 1.0) > 0.01:
        change_pct = int((c_factor - 1.0) * 100)
        factors_summary.append(f"Campus situation ({campus_situation}): {change_pct:+d}% turnout adjustment")

    return {
        "predicted_attendance": predicted,
        "predicted_absent": max(0, total_registered - predicted),
        "total_registered": total_registered,
        "turnout_pct": round(predicted / total_registered * 100, 1) if total_registered > 0 else 0,
        "weather": weather,
        "exam": {
            "intensity": exam_info["exam_intensity"],
            "label": exam_info.get("exam_label"),
            "is_exam_period": exam_info["is_exam_period"],
            "is_ramp_up": exam_info.get("is_ramp_up", False),
            "effect": exam_info["effect_description"],
        },
        "campus_situation": campus_situation,
        "campus_factor": c_factor,
        "confidence": "low",
        "method": "heuristic_fallback",
        "training_samples": 0,
        "training_rmse": None,
        "factors": {
            "weather_effect": f"Rain: {rain_mm:.0f}mm, Temp: {weather.get('temperature_c', 28)}°C",
            "exam_effect": exam_info["effect_description"],
            "day_effect": _describe_day_effect(target_date, is_weekend),
            "campus_effect": f"{campus_situation or 'Normal'} (factor: {c_factor})",
        },
        "factors_summary": factors_summary,
        "parameters_used": {
            "exam_intensity": exam_info["exam_intensity"],
            "exam_label": exam_info.get("exam_label"),
            "temperature_c": weather.get("temperature_c"),
            "rainfall_mm": weather.get("rainfall_mm"),
            "campus_situation": campus_situation,
            "campus_factor": c_factor,
        },
    }
