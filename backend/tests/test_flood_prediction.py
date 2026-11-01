from app.services import flood_prediction


def test_heuristic_risk_score_levels(monkeypatch):
    monkeypatch.setattr(flood_prediction, "_satellite_score", lambda *args: (90.0, 0.0, True))
    monkeypatch.setattr(flood_prediction, "_rain_score", lambda *args: (90.0, 120.0))
    monkeypatch.setattr(flood_prediction, "_river_score", lambda *args: 90.0)
    critical = flood_prediction.score_point({"name": "Delta", "lat": 20.4, "lon": 86.2}, {"polygons": {"features": []}, "mode": "LIVE"})
    assert critical["level"] == "CRITICAL"
    assert critical["score"] == 90
    assert len(critical["available_signals"]) == 3

    monkeypatch.setattr(flood_prediction, "_satellite_score", lambda *args: (20.0, 30.0, True))
    monkeypatch.setattr(flood_prediction, "_rain_score", lambda *args: (20.0, 30.0))
    monkeypatch.setattr(flood_prediction, "_river_score", lambda *args: 20.0)
    low = flood_prediction.score_point({"name": "Coast", "lat": 19.8, "lon": 85.8}, {"polygons": {"features": []}, "mode": "LIVE"})
    assert low["level"] == "LOW"


def test_unavailable_signals_are_not_misreported_as_low_risk(monkeypatch):
    monkeypatch.setattr(flood_prediction, "_satellite_score", lambda *args: (None, None, False))
    monkeypatch.setattr(flood_prediction, "_rain_score", lambda *args: (None, None))
    monkeypatch.setattr(flood_prediction, "_river_score", lambda *args: None)
    result = flood_prediction.score_point({"name": "Offline", "lat": 20.4, "lon": 86.2}, {"polygons": {"features": []}, "mode": "UNKNOWN"})
    assert result["level"] == "UNKNOWN"
    assert result["score"] == 0
    assert not result["available_signals"]
