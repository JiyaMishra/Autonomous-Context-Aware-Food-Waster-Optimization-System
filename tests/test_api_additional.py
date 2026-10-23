from fastapi.testclient import TestClient

from backend.app.main import app


def test_analytics_and_evaluation_endpoints():
    with TestClient(app) as client:
        trends = client.get("/api/v1/analytics/trends")
        dishes = client.get("/api/v1/analytics/dishes")
        meals = client.get("/api/v1/analytics/meals")
        evaluation = client.get("/api/v1/evaluation")
        assert trends.status_code == 200
        assert dishes.status_code == 200
        assert meals.status_code == 200
        assert evaluation.status_code == 200
        assert trends.json()
        assert dishes.json()
        assert meals.json()
        assert "observations" in evaluation.json()
        assert "note" in evaluation.json()


def test_csv_upload_validates_and_skips_duplicate_keys():
    with TestClient(app) as client:
        csv_data = (
            "date,meal,dish,planned_portions,served_portions,waste_portions,attendance\n"
            "2026-10-17,lunch,phase11-upload-test,20,18,2,20\n"
        )
        first = client.post(
            "/api/v1/data/upload",
            files={"file": ("history.csv", csv_data, "text/csv")},
        )
        assert first.status_code == 200, first.text
        assert first.json()["rows_received"] == 1
        assert first.json()["inserted"] + first.json()["skipped_duplicates"] == 1

        second = client.post(
            "/api/v1/data/upload",
            files={"file": ("history.csv", csv_data, "text/csv")},
        )
        assert second.status_code == 200, second.text
        assert second.json()["inserted"] == 0
        assert second.json()["skipped_duplicates"] == 1


def test_csv_upload_rejects_invalid_file_and_export_is_csv():
    with TestClient(app) as client:
        invalid = client.post(
            "/api/v1/data/upload",
            files={"file": ("history.csv", "date,dish\nnot-a-date,dal\n", "text/csv")},
        )
        assert invalid.status_code == 422
        exported = client.get("/api/v1/data/export")
        assert exported.status_code == 200
        assert "text/csv" in exported.headers["content-type"]
        assert "served_portions" in exported.text
