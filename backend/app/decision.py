from datetime import date
from pathlib import Path

import pandas as pd

from backend.app.data.pipeline import load_csv
from backend.app.forecasting import forecast_demand
from backend.app.optimizer import optimize_batches


def propose_plan(history: pd.DataFrame | str | Path, target_date: date, meal: str, dish: str,
                 attendance: int, event_factor: float = 1.0,
                 extra_context: list[str] | None = None, batch_size: int = 25,
                 minimum_buffer_pct: float = 0.05, context_features: dict | None = None) -> dict:
    frame = load_csv(history) if isinstance(history, (str, Path)) else history.copy()
    forecast = forecast_demand(frame, target_date, meal, dish, attendance, event_factor, context_features)
    plan = optimize_batches(forecast["predicted_portions"], batch_size, minimum_buffer_pct)
    context = [item.strip() for item in (extra_context or []) if item.strip()]
    explanation = forecast["explanation"] + plan["explanation"]
    if context:
        explanation.append("Operator context recorded for review: " + "; ".join(context))
        explanation.append("Context notes are not automatically converted into numeric adjustments.")
    return {
        "date": target_date, "meal": meal, "dish": dish,
        "forecast_portions": forecast["predicted_portions"],
        **plan, "confidence": forecast["confidence"], "method": forecast["method"],
        "status": "pending_review", "approval_required": True, "explanation": explanation,
    }
