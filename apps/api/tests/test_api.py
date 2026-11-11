from fastapi.testclient import TestClient

from demandsense import api


def test_health_and_missing_artifact_response(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "ARTIFACTS", tmp_path)
    client = TestClient(api.app)
    assert client.get("/api/health").json() == {"status": "ok", "artifacts_available": False}
    assert client.get("/api/metadata").json()["data_mode"] == "not configured"
    response = client.get("/api/products")
    assert response.status_code == 503
    assert "run the pipeline" in response.json()["detail"].lower()
