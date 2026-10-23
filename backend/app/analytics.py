"""Analytics designed for item-level meal data with heterogeneous physical units."""
import pandas as pd

from backend.app.forecasting import evaluate_predictions, forecast_demand


def _row_waste_pct(frame: pd.DataFrame) -> pd.Series:
    if "waste_rate_pct" in frame.columns:
        source = pd.to_numeric(frame["waste_rate_pct"], errors="coerce")
    else:
        source = pd.Series(float("nan"), index=frame.index)
    prepared = (
        pd.to_numeric(frame["prepared_portions"], errors="coerce")
        if "prepared_portions" in frame.columns
        else pd.Series(float("nan"), index=frame.index)
    )
    if "planned_portions" in frame.columns:
        prepared = prepared.fillna(pd.to_numeric(frame["planned_portions"], errors="coerce"))
    fallback = pd.to_numeric(frame["waste_portions"], errors="coerce").div(prepared.replace(0, float("nan"))) * 100
    return source.fillna(fallback).fillna(0).clip(lower=0)


def waste_trends(history: pd.DataFrame) -> list[dict]:
    if history.empty:
        return []
    frame = history.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    frame["row_waste_rate_pct"] = _row_waste_pct(frame)
    grouped = frame.groupby("date", as_index=False).agg(
        records=("dish", "size"),
        average_waste_rate_pct=("row_waste_rate_pct", "mean"),
    )
    grouped["waste_rate"] = (grouped["average_waste_rate_pct"] / 100).round(4)
    grouped["average_waste_rate_pct"] = grouped["average_waste_rate_pct"].round(2)
    # Do not sum portions across litres/kg, pieces, and servings.
    return grouped.to_dict(orient="records")


def dish_waste_analytics(history: pd.DataFrame) -> list[dict]:
    if history.empty:
        return []
    frame = history.copy()
    frame["row_waste_rate_pct"] = _row_waste_pct(frame)
    if "quantity_unit_hint" not in frame.columns:
        frame["quantity_unit_hint"] = None
    grouped = frame.groupby(["dish", "quantity_unit_hint"], dropna=False, as_index=False).agg(
        records=("dish", "size"),
        average_waste_rate_pct=("row_waste_rate_pct", "mean"),
        total_waste_in_item_unit=("waste_portions", "sum"),
    )
    grouped["average_waste_rate_pct"] = grouped["average_waste_rate_pct"].round(2)
    grouped["quantity_unit_hint"] = grouped["quantity_unit_hint"].fillna("unspecified unit")
    return grouped.sort_values(
        ["average_waste_rate_pct", "records"], ascending=[False, False]
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
