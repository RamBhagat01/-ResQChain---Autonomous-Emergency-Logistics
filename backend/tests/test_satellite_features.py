import json

from fastapi.testclient import TestClient

from app.main import app
from app.services.satellite_flood import detect_flood, threshold_flood_mask


def test_sample_satellite_detection_is_explicit():
    result = detect_flood((86.2, 20.2, 86.7, 20.7))
    assert result["mode"] == "SAMPLE"
    assert result["polygons"]["features"]
    assert all(feature["properties"]["source"] == "SAMPLE" for feature in result["polygons"]["features"])


def test_threshold_mask_removes_permanent_water_and_steep_slope():
    mask = threshold_flood_mask([-20, -20, -20], [-15, -15, -15], [0, 90, 0], [2, 2, 8])
    assert mask.tolist() == [True, False, False]


def test_new_endpoints_are_available(monkeypatch):
    client = TestClient(app)
    satellite = client.get("/api/satellite/flood")
    assert satellite.status_code == 200
    assert satellite.json()["mode"] in {"SAMPLE", "LIVE"}

    monkeypatch.setattr("app.services.warehouse_siting._overpass", lambda *args: [{"name": "Mock OSM Warehouse", "lat": 20.46, "lon": 85.88, "address": "Mock", "osm_id": "node/1", "tags": {}}])
    sites = client.get("/api/warehouse-sites?lat=20.46&lon=85.88&radius_km=5&limit=2")
    assert sites.status_code == 200
    assert sites.json()["decision_support"] is True
    assert sites.json()["human_verification_required"] is True

