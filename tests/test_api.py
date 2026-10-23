from fastapi.testclient import TestClient
from backend.app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_summary_and_history_endpoints_share_database():
    with TestClient(app) as client:
        summary = client.get("/api/v1/summary")
        history = client.get("/api/v1/history?limit=12")
        assert summary.status_code == 200
        assert history.status_code == 200
        assert summary.json()["records"] >= len(history.json()) > 0
        payload = summary.json()
        assert payload["served_portions"] >= payload["waste_portions"]
        # Limited history should contain the latest rows, not the oldest rows.
        assert max(row["date"] for row in history.json()) == "2026-10-18"


def test_forecast_plan_and_human_review_flow():
    with TestClient(app) as client:
        forecast = client.post("/api/v1/forecast", json={
            "date": "2026-10-25", "meal": "lunch", "dish": "dal tadka",
            "attendance": 150, "event_factor": 1.0,
        })
        assert forecast.status_code == 200, forecast.text
        assert forecast.json()["predicted_portions"] >= 0

        created = client.post("/api/v1/plans", json={
            "date": "2026-10-25", "meal": "lunch", "dish": "dal tadka",
            "attendance": 150, "event_factor": 1.0, "batch_size": 20,
            "minimum_buffer_pct": 0.05, "extra_context": ["campus event"],
        })
        assert created.status_code == 200, created.text
        plan = created.json()
        assert plan["id"] > 0
        assert plan["status"] == "pending_review"
        assert plan["approval_required"] is True
        assert plan["recommended_portions"] % plan["batch_size"] == 0

        review = client.post(f"/api/v1/plans/{plan['id']}/feedback", json={
            "approved": True, "reviewer": "test_operator", "note": "Batch size checked",
        })
        assert review.status_code == 200, review.text
        assert review.json()["status"] == "approved"

        records = client.get("/api/v1/plans?limit=10")
        assert records.status_code == 200
        saved = next(item for item in records.json() if item["id"] == plan["id"])
        assert saved["status"] == "approved"
        assert saved["recommended_portions"] == plan["recommended_portions"]
