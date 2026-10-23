from fastapi.testclient import TestClient
from backend.app.main import app

client_context = TestClient(app)


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
