from collections import defaultdict
from pathlib import Path
from backend.app.data.pipeline import load_csv


def summarize_history(path: str | Path) -> dict:
    frame = load_csv(path)
    waste_by_dish: dict[str, int] = defaultdict(int)
    served_by_dish: dict[str, int] = defaultdict(int)
    for row in frame.itertuples(index=False):
        waste_by_dish[str(row.dish)] += int(row.waste_portions)
        served_by_dish[str(row.dish)] += int(row.served_portions)
    top_waste = sorted(waste_by_dish.items(), key=lambda item: item[1], reverse=True)[:5]
    return {
        "rows": int(len(frame)),
        "total_served": int(frame["served_portions"].sum()),
        "total_waste": int(frame["waste_portions"].sum()),
        "waste_rate": round(float(frame["waste_portions"].sum() / frame["served_portions"].sum()), 4)
        if frame["served_portions"].sum() else 0.0,
        "waste_by_dish": [{"dish": dish, "waste_portions": value, "served_portions": served_by_dish[dish]}
                          for dish, value in top_waste],
    }
