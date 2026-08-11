from fastapi.testclient import TestClient

from app.main import app


def test_authenticated_onboarding_and_tenant_scoped_incident():
    with TestClient(app) as client:
        session = client.get("/api/v1/auth/session")
        assert session.status_code == 200
        env = client.post("/api/v1/environments", json={"name": "Production", "slug": "production"})
        assert env.status_code == 201
        env_id = env.json()["id"]
        key = client.post("/api/v1/ingestion-keys", json={"environment_id": env_id, "name": "collector"})
        assert key.status_code == 201
        assert key.json()["secret"].startswith("cly_ing_")
        end = 1_800_000_000_000
        incident = client.post("/api/v1/incidents", json={"environment_id": env_id, "title": "Latency spike", "services": ["api"], "window_start": end - 900_000, "window_end": end, "summary": "manual window"})
        assert incident.status_code == 201
        assert client.get(f"/api/v1/incidents/{incident.json()['id']}").status_code == 200


def test_rejects_oversized_incident_window():
    with TestClient(app) as client:
        envs = client.get("/api/v1/environments").json()
        if not envs:
            envs = [client.post("/api/v1/environments", json={"name": "Production", "slug": "production"}).json()]
        response = client.post("/api/v1/incidents", json={"environment_id": envs[0]["id"], "title": "Too wide", "services": [], "window_start": 0, "window_end": 3_600_001, "summary": ""})
        assert response.status_code == 422
