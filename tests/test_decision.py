from datetime import date
from pathlib import Path
from backend.app.decision import propose_plan

CSV = Path(__file__).resolve().parents[1] / "data" / "raw" / "meal_history.csv"


def test_plan_is_explainable_and_requires_review():
    result = propose_plan(
        str(CSV), date(2026, 10, 25), "lunch", "dal tadka", 100,
        extra_context=["rain forecast", "sports event"], batch_size=20,
    )
    assert result["status"] == "pending_review"
    assert result["approval_required"] is True
    assert result["recommended_portions"] % 20 == 0
    assert any("Operator context recorded" in line for line in result["explanation"])
