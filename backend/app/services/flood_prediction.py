"""Transparent, non-ML flood heuristic used for early warning and planning."""
import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

import httpx

from app.config import settings
from app.services.geo import haversine_km


def _level(score: float) -> str:
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 35:
        return "MODERATE"
    return "LOW"


def _flood_features(result: Dict[str, Any]) -> List[Any]:
    try:
        from shapely.geometry import shape
        return [shape(f["geometry"]) for f in result.get("polygons", {}).get("features", [])]
    except Exception:
        return []


def _rain_score(lat: float, lon: float) -> float:
    try:
        data = httpx.get("https://api.open-meteo.com/v1/forecast", params={"latitude": lat, "longitude": lon,
            "hourly": "precipitation", "forecast_days": 3, "timezone": "UTC"}, timeout=4).json()
        rain = sum(float(v or 0) for v in data.get("hourly", {}).get("precipitation", [])[:72])
        return min(100.0, rain / 150.0 * 100.0), rain
    except Exception:
        return 0.0, None


def _river_score(lat: float, lon: float) -> float:
    try:
        from app.services.flood_risk import get_flood_risk
        point = get_flood_risk("risk-point", lat, lon)
        discharge = point.get("discharge_m3s")
        return min(100.0, max(0.0, (float(discharge) - 1000) / 5000 * 100)) if discharge is not None else 0.0
    except Exception:
        return 0.0


def score_point(point: Dict[str, Any], satellite_result: Dict[str, Any]) -> Dict[str, Any]:
    lat, lon = float(point["lat"]), float(point["lon"])
    features = _flood_features(satellite_result)
    observed = 0.0
    nearest_km = None
    if features:
        distances = []
        for geom in features:
            distances.append(haversine_km(lat, lon, geom.centroid.y, geom.centroid.x))
            if geom.contains(__import__("shapely").geometry.Point(lon, lat)):
                observed = 100.0
        nearest_km = min(distances) if distances else None
        if observed == 0 and nearest_km is not None:
            observed = max(0.0, 75.0 - nearest_km * 8.0)
    rain_score, rain_mm = _rain_score(lat, lon)
    river_score = _river_score(lat, lon)
    # Low-lying exposure is a planning proxy; exact elevation is optional and never fabricated.
    terrain_score = 60.0 if lat < 20.7 else 30.0
    history_score = 55.0 if 20.1 < lat < 20.7 and 86.2 < lon < 86.8 else 25.0
    score = round(min(100.0, observed * settings.RISK_WEIGHT_SATELLITE + rain_score * settings.RISK_WEIGHT_RAIN +
        river_score * settings.RISK_WEIGHT_RIVER + terrain_score * settings.RISK_WEIGHT_TERRAIN + history_score * settings.RISK_WEIGHT_HISTORY), 1)
    level = _level(score)
    explanation = [
        f"Sentinel-1 observed-water factor: {observed:.0f}/100" + (f"; nearest observed polygon {nearest_km:.1f} km away" if nearest_km is not None else "; no observed polygon nearby"),
        f"72-hour rainfall factor: {rain_score:.0f}/100" + (f" ({rain_mm:.1f} mm forecast)" if rain_mm is not None else " (unavailable)"),
        f"River discharge factor: {river_score:.0f}/100",
        f"Low-lying terrain exposure factor: {terrain_score:.0f}/100 (planning heuristic)",
        f"JRC/history exposure factor: {history_score:.0f}/100 (planning heuristic)",
    ]
    return {"name": point["name"], "lat": lat, "lon": lon, "score": score, "level": level,
            "explanation": explanation, "affected_population": int(point.get("population", 0) * max(0.0, score / 100.0)),
            "source": "heuristic risk score"}


def compute_scores(points: Iterable[Dict[str, Any]], satellite_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [score_point(point, satellite_result) for point in points]
