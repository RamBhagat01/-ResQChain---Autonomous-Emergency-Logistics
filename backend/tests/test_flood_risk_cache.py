from datetime import datetime, timedelta, timezone

from app.services import flood_risk


POINTS = [
    {"name": "Cuttack", "lat": 20.46, "lon": 85.88},
    {"name": "Puri", "lat": 19.81, "lon": 85.83},
]


def setup_function():
    flood_risk._cache.clear()
    flood_risk._cache_updated_at = None
    flood_risk._retry_not_before = None


def test_batch_uses_one_upstream_call_and_fresh_cache(monkeypatch):
    calls = []

    def fake_fetch(points):
        calls.append(points)
        return {p["name"]: {"name": p["name"], "lat": p["lat"], "lon": p["lon"],
                "discharge_m3s": 1000, "severity": 1, "risk_level": "NORMAL", "status": "LIVE"}
                for p in points}

    monkeypatch.setattr(flood_risk, "_fetch_batch", fake_fetch)
    first = flood_risk.get_all_flood_risks(POINTS)
    second = flood_risk.get_all_flood_risks(POINTS)
    assert len(calls) == 1
    assert len(first) == len(second) == 2


def test_batch_parser_accepts_open_meteo_location_array():
    parsed = flood_risk._response_locations([{"daily": {}}, {"daily": {}}])
    assert len(parsed) == 2
    assert all("daily" in item for item in parsed)


def test_upstream_failure_uses_labeled_stale_snapshot(monkeypatch):
    flood_risk._cache.update({p["name"]: {**p, "discharge_m3s": 2200, "severity": 2,
        "risk_level": "WARNING", "status": "LIVE", "error": None} for p in POINTS})
    flood_risk._cache_updated_at = datetime.now(timezone.utc) - timedelta(minutes=20)
    monkeypatch.setattr(flood_risk, "_fetch_batch", lambda _points: (_ for _ in ()).throw(RuntimeError("429 rate limit")))
    result = flood_risk.get_all_flood_risks(POINTS)
    assert all(item["status"] == "CACHED" for item in result)
    assert all(item["discharge_m3s"] == 2200 for item in result)
    assert all("last successful" in item["error"] for item in result)


def test_no_cache_and_failed_upstream_is_unavailable(monkeypatch):
    monkeypatch.setattr(flood_risk, "_fetch_batch", lambda _points: (_ for _ in ()).throw(RuntimeError("offline")))
    result = flood_risk.get_all_flood_risks(POINTS)
    assert all(item["status"] == "UNAVAILABLE" for item in result)
    assert all(item["discharge_m3s"] is None for item in result)


def test_rate_limit_cooldown_does_not_repeat_upstream_request(monkeypatch):
    flood_risk._retry_not_before = datetime.now(timezone.utc) + timedelta(minutes=5)
    calls = []
    monkeypatch.setattr(flood_risk, "_fetch_batch", lambda _points: calls.append(True))
    result = flood_risk.get_all_flood_risks(POINTS)
    assert calls == []
    assert all(item["status"] == "RATE_LIMITED" for item in result)
    assert all(item["retry_after_seconds"] > 0 for item in result)
