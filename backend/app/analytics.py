"""Pure analytics helpers for waste trends and chronological forecast evaluation."""
import pandas as pd

from backend.app.forecasting import evaluate_predictions, forecast_demand


def waste_trends(history: pd.DataFrame) -> list[dict]:
    if history.empty:
        return []
    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    grouped = frame.groupby("date", as_index=False).agg(
        served_portions=("served_portions", "sum"),
        waste_portions=("waste_portions", "sum"),
    )
    grouped["waste_rate"] = grouped.apply(
        lambda row: round(float(row["waste_portions"] / row["served_portions"]), 4)
        if row["served_portions"] else 0.0,
        axis=1,
    )
    return grouped.to_dict(orient="records")


def dish_waste_analytics(history: pd.DataFrame) -> list[dict]:
    if history.empty:
        return []
    grouped = history.groupby("dish", as_index=False).agg(
        records=("dish", "size"),
        served_portions=("served_portions", "sum"),
        waste_portions=("waste_portions", "sum"),
    )
    grouped["waste_rate"] = grouped.apply(
        lambda row: round(float(row["waste_portions"] / row["served_portions"]), 4)
        if row["served_portions"] else 0.0,
        axis=1,
    )
    return grouped.sort_values(
        ["waste_portions", "waste_rate"], ascending=[False, False]
    ).to_dict(orient="records")


def evaluate_history(history: pd.DataFrame, minimum_observations: int = 5) -> dict:
    """Evaluate chronologically so each prediction sees only strictly earlier dates."""
    if history.empty:
        return {"observations": 0, "metrics": None, "methods": {}, "note": "No history is available."}
    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame.sort_values(["date", "meal", "dish"])
    actual: list[int] = []
    predicted: list[int] = []
    methods: dict[str, int] = {}
    rows = list(frame.itertuples(index=False))
    for row in rows:
        prior = frame[frame["date"] < row.date]
        if prior.empty:
            continue
        prediction = forecast_demand(
            prior, row.date, str(row.meal), str(row.dish),
            int(row.attendance), float(row.event_factor),
        )
        actual.append(int(row.served_portions))
        predicted.append(int(prediction["predicted_portions"]))
        method = str(prediction["method"])
        methods[method] = methods.get(method, 0) + 1
    if len(actual) < minimum_observations:
        return {
            "observations": len(actual), "metrics": None, "methods": methods,
            "note": f"At least {minimum_observations} evaluable historical rows are needed for metrics.",
        }
    return {
        "observations": len(actual),
        "metrics": evaluate_predictions(actual, predicted),
        "methods": methods,
        "note": "Chronological backtest: each prediction uses only observations dated earlier than its target date. This is a baseline evaluation, not a guarantee of future accuracy.",
    }
