import pandas as pd

from backend.app.data.pipeline import normalize_and_validate


def test_august_menu_dataset_is_accepted_and_source_fields_are_preserved():
    source = pd.DataFrame([{
        "date": "2026-08-01",
        "day_of_week": "Saturday",
        "menu_version": 1,
        "meal": "Breakfast",
        "food_item": "Aloo Paratha",
        "synthetic_liking_score": 0.827,
        "exam_intensity": 0.35,
        "temperature_c": 27.8,
        "rainfall_mm": 11.9,
        "is_weekend": 1,
        "hostel_attendance_estimate": 403,
        "historical_demand_rate": 0.765,
        "expected_consumers": 308,
        "recommended_preparation_portions": 324,
        "prepared_portions": 329,
        "consumed_portions": 319,
        "leftover_portions": 10,
        "waste_rate_pct": 3.04,
        "quantity_unit_hint": "pieces_or_servings",
    }])
    row = normalize_and_validate(source).iloc[0]
    assert row["dish"] == "Aloo Paratha"
    assert row["meal"] == "breakfast"
    assert row["planned_portions"] == 324
    assert row["prepared_portions"] == 329
    assert row["served_portions"] == 319
    assert row["waste_portions"] == 10
    assert row["attendance"] == 403
    assert row["hostel_attendance_estimate"] == 403
    assert row["expected_consumers"] == 308
    assert row["quantity_unit_hint"] == "pieces_or_servings"
    assert row["temperature_c"] == 27.8
