from pathlib import Path

from fastapi.testclient import TestClient

from demandsense import api

DEMO_ARTIFACTS = Path(__file__).resolve().parents[3] / "artifacts" / "demo"


def test_health_and_missing_artifact_response(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "ARTIFACTS", tmp_path)
    client = TestClient(api.app)
    assert client.get("/api/health").json() == {"status": "ok", "artifacts_available": False}
    assert client.get("/api/metadata").json()["data_mode"] == "not configured"
    response = client.get("/api/products")
    assert response.status_code == 503
    assert "run the pipeline" in response.json()["detail"].lower()


def test_api_with_demo_artifacts(monkeypatch):
    monkeypatch.setattr(api, "ARTIFACTS", DEMO_ARTIFACTS)
    client = TestClient(api.app)

    # Health
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "artifacts_available": True}

    # Metadata & Quality
    meta = client.get("/api/metadata")
    assert meta.status_code == 200
    assert "synthetic" in meta.json()["data_mode"]

    quality = client.get("/api/dataset/quality")
    assert quality.status_code == 200
    assert quality.json()["accepted_positive_sales_rows"] > 0

    manifest = client.get("/api/dataset/manifest")
    assert manifest.status_code == 200

    summary = client.get("/api/dataset/summary")
    assert summary.status_code == 200
    assert summary.json()["products"] == 22

    # Products
    products = client.get("/api/products")
    assert products.status_code == 200
    items = products.json()["items"]
    assert len(items) == 22
    prod_id = items[0]["product_id"]

    prod_detail = client.get(f"/api/products/{prod_id}")
    assert prod_detail.status_code == 200
    assert prod_detail.json()["product_id"] == prod_id

    history = client.get(f"/api/products/{prod_id}/history")
    assert history.status_code == 200
    assert len(history.json()["items"]) > 0

    # Forecasts
    forecasts = client.get("/api/forecasts")
    assert forecasts.status_code == 200
    assert len(forecasts.json()["items"]) > 0

    prod_fc = client.get(f"/api/forecasts/{prod_id}")
    assert prod_fc.status_code == 200
    assert len(prod_fc.json()["items"]) == 4

    # Models & Metrics
    models = client.get("/api/models")
    assert models.status_code == 200
    assert len(models.json()) == 4

    metrics = client.get("/api/models/metrics")
    assert metrics.status_code == 200
    assert "LightGBM" in metrics.json()
    assert "comparison" in metrics.json()

    by_h = client.get("/api/models/metrics/by-horizon")
    assert by_h.status_code == 200
    assert len(by_h.json()["items"]) == 4

    by_p = client.get("/api/models/metrics/by-product")
    assert by_p.status_code == 200
    assert len(by_p.json()["items"]) == 22

    # Intervals & Importance
    coverage = client.get("/api/intervals/coverage")
    assert coverage.status_code == 200
    assert coverage.json()["count"] > 0

    imp = client.get("/api/features/importance")
    assert imp.status_code == 200
    assert len(imp.json()["items"]) > 0

    # Backtests
    backtests = client.get("/api/backtests")
    assert backtests.status_code == 200
    assert len(backtests.json()["items"]) > 0

    # Simulation
    sim = client.post(
        "/api/simulations/demand-shift",
        json={
            "product_id": prod_id,
            "adjustment_pct": 30.0,
            "window_weeks": 4,
            "shock_type": "sustained",
        },
    )
    assert sim.status_code == 200
    sim_data = sim.json()
    assert len(sim_data["items"]) == 4
    assert "out_of_range_features" in sim_data
