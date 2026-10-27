from datetime import date
import pandas as pd
from fastapi.testclient import TestClient

from backend.app.academic_calendar import get_exam_intensity
from backend.app.attendance_predictor import predict_attendance
from backend.app.main import app
from backend.app.weather import get_weather


def test_academic_calendar_exam_intensity():
    # Normal day in August 2026 (no exam)
    august_res = get_exam_intensity(date(2026, 8, 10))
    assert august_res["is_exam_period"] is False
    assert august_res["exam_intensity"] == 0.0

    # October 2026: Default is regular semester (no false CAT-2 assumption)
    october_res = get_exam_intensity(date(2026, 10, 27))
    assert october_res["is_exam_period"] is False
    assert october_res["exam_intensity"] == 0.0

    # During CAT-1 (2026-09-14 to 2026-09-24)
    cat1_res = get_exam_intensity(date(2026, 9, 18))
    assert cat1_res["is_exam_period"] is True
    assert cat1_res["exam_label"] == "CAT-1"
    assert cat1_res["exam_intensity"] == 0.7

    # During FAT (2026-11-23 to 2026-12-08)
    fat_res = get_exam_intensity(date(2026, 11, 28))
    assert fat_res["is_exam_period"] is True
    assert "FAT" in fat_res["exam_label"]
    assert fat_res["exam_intensity"] == 1.0


def test_weather_fallback_structure():
    mock_history = pd.DataFrame([
        {"date": "2026-08-01", "meal": "lunch", "temperature_c": 28.5, "rainfall_mm": 5.0, "attendance": 400},
        {"date": "2026-08-02", "meal": "lunch", "temperature_c": 29.0, "rainfall_mm": 2.0, "attendance": 410},
    ])
    w = get_weather(date(2026, 12, 1), "lunch", history=mock_history)
    assert "temperature_c" in w
    assert "rainfall_mm" in w
    assert "source" in w
    assert w["temperature_c"] is not None


def test_attendance_predictor_with_sample_data():
    dates = pd.date_range("2026-08-01", "2026-08-20")
    rows = []
    for d in dates:
        for m in ["breakfast", "lunch", "snacks", "dinner"]:
            rows.append({
                "date": str(d.date()),
                "meal": m,
                "attendance": 420 if m == "lunch" else 300,
                "temperature_c": 28.0,
                "rainfall_mm": 0.0,
                "exam_intensity": 0.0,
                "is_weekend": 1 if d.weekday() >= 5 else 0,
            })
    df = pd.DataFrame(rows)
    pred = predict_attendance(df, date(2026, 8, 25), "lunch", total_registered=500)
    assert 0 <= pred["predicted_attendance"] <= 500
    assert pred["predicted_attendance"] + pred["predicted_absent"] == 500
    assert pred["turnout_pct"] == round(pred["predicted_attendance"] / 500 * 100, 1)
    assert pred["confidence"] in ["high", "medium", "low"]
    assert "weather" in pred
    assert "exam" in pred


def test_api_predict_attendance_endpoint():
    with TestClient(app) as client:
        res = client.post("/api/v1/predict-attendance", json={
            "date": "2026-10-28",
            "meal": "lunch",
            "total_registered": 500,
        })
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["meal"] == "lunch"
        assert "predicted_attendance" in data
        assert "predicted_absent" in data
        assert "weather" in data
        assert "exam" in data
        # For October date without overrides, default is regular classes
        assert data["exam"]["intensity"] == 0.0


def test_api_predict_attendance_parameter_tuning():
    with TestClient(app) as client:
        # User tunes parameters: specifies CAT-2 exam and heavy rain
        res_exam = client.post("/api/v1/predict-attendance", json={
            "date": "2026-10-28",
            "meal": "lunch",
            "exam_intensity": 0.75,
            "exam_label": "CAT-2 Exams",
            "temperature_c": 22.0,
            "rainfall_mm": 35.0,
        })
        assert res_exam.status_code == 200
        data_exam = res_exam.json()
        assert data_exam["exam"]["intensity"] == 0.75
        assert data_exam["exam"]["label"] == "CAT-2 Exams"
        assert data_exam["weather"]["temperature_c"] == 22.0
        assert data_exam["weather"]["rainfall_mm"] == 35.0

        # User tunes parameters: specifies students went home (30% drop)
        res_home = client.post("/api/v1/predict-attendance", json={
            "date": "2026-10-28",
            "meal": "lunch",
            "campus_situation": "Students went home",
            "campus_factor": 0.7,
        })
        assert res_home.status_code == 200
        data_home = res_home.json()
        assert data_home["campus_situation"] == "Students went home"
        assert data_home["campus_factor"] == 0.7
        assert any("Students went home" in s for s in data_home["factors_summary"])


def test_api_forecast_and_plan_auto_predict_attendance():
    with TestClient(app) as client:
        # Forecast without providing attendance
        res_f = client.post("/api/v1/forecast", json={
            "date": "2026-10-28",
            "meal": "lunch",
            "dish": "dal tadka",
            # attendance omitted!
            "exam_intensity": 0.0,
        })
        assert res_f.status_code == 200, res_f.text
        f_data = res_f.json()
        assert f_data["auto_predicted_attendance"] is not None
        assert f_data["predicted_portions"] >= 0

        # Plan without providing attendance, but with contextual parameters
        res_p = client.post("/api/v1/plans", json={
            "date": "2026-10-28",
            "meal": "lunch",
            "dish": "dal tadka",
            "batch_size": 25,
            # attendance omitted!
            "campus_situation": "Long weekend",
            "campus_factor": 0.75,
        })
        assert res_p.status_code == 200, res_p.text
        p_data = res_p.json()
        assert p_data["auto_predicted_attendance"] is not None
        assert any("AI predicted attendance" in exp for exp in p_data["explanation"])
