import math


def optimize_batches(forecast_portions: int, batch_size: int = 25,
                    minimum_buffer_pct: float = 0.05) -> dict:
    if forecast_portions < 0:
        raise ValueError("forecast_portions must be non-negative")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if not 0 <= minimum_buffer_pct <= 0.5:
        raise ValueError("minimum_buffer_pct must be between 0 and 0.5")

    target = math.ceil(forecast_portions * (1 + minimum_buffer_pct))
    batches = math.ceil(target / batch_size) if target else 0
    recommended = batches * batch_size
    return {
        "forecast_portions": forecast_portions,
        "recommended_portions": recommended,
        "batches": batches,
        "batch_size": batch_size,
        "expected_buffer_portions": max(0, recommended - forecast_portions),
        "explanation": [
            f"Forecast demand is {forecast_portions} portions.",
            f"A {minimum_buffer_pct:.0%} planning buffer was applied before rounding to full batches.",
            f"Rounded to {batches} batch(es) of {batch_size}; kitchen staff must review this proposal.",
        ],
    }
