"""Weather data integration for automatic attendance prediction.

Uses the Open-Meteo API (free, no API key required) to fetch temperature
and rainfall for a target date. Falls back to historical averages when the
API is unavailable or the date is outside the forecast window.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

logger = logging.getLogger(__name__)

# Open-Meteo free API — no key needed.
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Default coordinates: VIT Vellore campus.
DEFAULT_LAT = 12.9692
DEFAULT_LON = 79.1559

# Open-Meteo forecast horizon (free tier supports ~16 days ahead).
_MAX_FORECAST_DAYS = 16


def _fetch_open_meteo(target_date: date, lat: float, lon: float) -> dict | None:
    """Call Open-Meteo for a single date. Returns None on any failure."""
    try:
        import httpx
    except ImportError:
        logger.warning("httpx is not installed; cannot call Open-Meteo API.")
        return None

    today = date.today()
    delta = (target_date - today).days

    if delta <= _MAX_FORECAST_DAYS:
        # Use forecast API for today and near-future dates.
        url = _FORECAST_URL
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_mean,precipitation_sum",
            "start_date": str(target_date),
            "end_date": str(target_date),
            "timezone": "Asia/Kolkata",
        }
    elif target_date < today:
        # Use archive API for past dates.
        url = _ARCHIVE_URL
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "temperature_2m_mean,precipitation_sum",
            "start_date": str(target_date),
            "end_date": str(target_date),
            "timezone": "Asia/Kolkata",
        }
    else:
        # Date is too far in the future for any API.
        return None

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        daily = data.get("daily", {})
        temps = daily.get("temperature_2m_mean", [None])
        precip = daily.get("precipitation_sum", [None])

        temp_value = temps[0] if temps else None
        rain_value = precip[0] if precip else None

        if temp_value is None and rain_value is None:
            return None

        return {
            "temperature_c": round(float(temp_value), 1) if temp_value is not None else None,
            "rainfall_mm": round(float(rain_value), 1) if rain_value is not None else None,
            "source": "open-meteo forecast" if delta >= 0 else "open-meteo archive",
        }
    except Exception as exc:
        logger.warning("Open-Meteo API call failed: %s", exc)
        return None


def _historical_weather_fallback(
    history: pd.DataFrame, target_date: date, meal: str,
) -> dict:
    """Compute average weather from historical data for similar dates.

    Matches by same day-of-week and meal to capture weekly patterns.
    Falls back to overall averages if no matching rows exist.
    """
    if history.empty:
        return {
            "temperature_c": 28.0,
            "rainfall_mm": 5.0,
            "source": "default (no history available)",
        }

    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")

    # Try to match same day-of-week and meal.
    target_dow = target_date.weekday()  # 0=Monday
    matched = frame[
        (frame["date"].dt.dayofweek == target_dow)
        & (frame["meal"].str.lower() == meal.lower())
    ]
    if matched.empty:
        matched = frame  # Broad fallback.

    temp = pd.to_numeric(matched.get("temperature_c"), errors="coerce").dropna()
    rain = pd.to_numeric(matched.get("rainfall_mm"), errors="coerce").dropna()

    return {
        "temperature_c": round(float(temp.mean()), 1) if len(temp) else 28.0,
        "rainfall_mm": round(float(rain.mean()), 1) if len(rain) else 5.0,
        "source": f"historical average ({len(temp)} matching records)",
    }


def get_weather(
    target_date: date,
    meal: str = "lunch",
    history: pd.DataFrame | None = None,
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
) -> dict:
    """Return weather conditions for a target date.

    Tries the Open-Meteo API first; falls back to historical dataset
    averages if the API is unavailable or the date is out of range.

    Returns
    -------
    dict
        {"temperature_c": float, "rainfall_mm": float, "source": str}
    """
    api_result = _fetch_open_meteo(target_date, lat, lon)
    if api_result is not None:
        return api_result

    # Fallback to historical averages.
    if history is not None:
        return _historical_weather_fallback(history, target_date, meal)

    return {
        "temperature_c": 28.0,
        "rainfall_mm": 5.0,
        "source": "default (API unavailable, no history)",
    }
