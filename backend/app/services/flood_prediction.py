"""Transparent, non-ML flood heuristic used for early warning and planning."""
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from shapely.geometry import Point, shape

from app.config import settings
from app.services.geo import haversine_km


def _level(score: Optional[float]) -> str:
    if score is None:
        return "UNKNOWN"
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 35:
        return "MODERATE"
    return "LOW"


def _flood_features(result: Dict[str, Any]) -> List[Any]:
    try:
        return [shape(feature["geometry"]) for feature in result.get("polygons", {}).get("features", [])
                if feature.get("geometry")]
    except Exception:
        return []


def _rain_score(lat: float, lon: float) -> Tuple[Optional[float], Optional[float]]:
    """Return a normalized 72-hour forecast score and rainfall mm, or unavailable."""
    try:
        response = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "hourly": "precipitation",
                    "forecast_days": 3, "timezone": "UTC"}, timeout=5,
        )
        response.raise_for_status()
        hourly = response.json().get("hourly", {}).get("precipitation")
        if not hourly:
            return None, None
        rain = sum(float(value or 0) for value in hourly[:72])
        return min(100.0, max(0.0, rain / 150.0 * 100.0)), rain
    except Exception:
        return None, None


def _river_score(lat: float, lon: float) -> Optional[float]:
    try:
        # Prediction runs across many locations: only use the shared GloFAS
        # snapshot here, never fan out one network request per scored point.
        from app.services.flood_risk import get_cached_flood_risk
        point = get_cached_flood_risk(lat, lon)
        if point is None:
            return None
        discharge = point.get("discharge_m3s")
        if discharge is None or point.get("risk_level") == "UNKNOWN":
            return None
        return min(100.0, max(0.0, (float(discharge) - 1000.0) / 5000.0 * 100.0))
    except Exception:
        return None


def _satellite_score(lat: float, lon: float, features: List[Any]) -> Tuple[Optional[float], Optional[float], bool]:
    if not features:
        return None, None, False
    point = Point(lon, lat)
    nearest_km = None
    for geometry in features:
        from shapely.ops import nearest_points
        nearest = nearest_points(geometry, point)[0]
        distance_km = haversine_km(lat, lon, nearest.y, nearest.x)
        nearest_km = distance_km if nearest_km is None else min(nearest_km, distance_km)
        if geometry.intersects(point):
            return 100.0, 0.0, True
    return max(0.0, 75.0 - (nearest_km or 0.0) * 8.0), nearest_km, True


def score_point(point: Dict[str, Any], satellite_result: Dict[str, Any]) -> Dict[str, Any]:
    lat, lon = float(point["lat"]), float(point["lon"])
    features = _flood_features(satellite_result)
    satellite_score, nearest_km, satellite_available = _satellite_score(lat, lon, features)
    rain_score, rain_mm = _rain_score(lat, lon)
    river_score = _river_score(lat, lon)

    # Elevation and JRC occurrence are not currently queried by the prediction service.
    # Exclude those weights until actual readings are available; never substitute geographic guesses.
    factors = [
        ("Sentinel-1 observed-water proximity", satellite_score, settings.RISK_WEIGHT_SATELLITE),
        ("72-hour rainfall forecast", rain_score, settings.RISK_WEIGHT_RAIN),
        ("River discharge", river_score, settings.RISK_WEIGHT_RIVER),
    ]
    available = [(name, value, weight) for name, value, weight in factors if value is not None and weight > 0]
    total_weight = sum(weight for _, _, weight in available)
    score = round(sum(value * weight for _, value, weight in available) / total_weight, 1) if total_weight else None
    level = _level(score)

    explanation = []
    if satellite_available:
        explanation.append(f"Sentinel-1 observed-water proximity: {satellite_score:.0f}/100; " +
                           ("point intersects an observed polygon" if nearest_km == 0 else f"nearest polygon {nearest_km:.1f} km away"))
        if satellite_result.get("mode") == "SAMPLE":
            explanation.append("Satellite input is SAMPLE demonstration data, not a live observation.")
    else:
        explanation.append("Sentinel-1 observed-water proximity: unavailable")
    explanation.append(f"72-hour rainfall forecast: {rain_score:.0f}/100 ({rain_mm:.1f} mm)" if rain_score is not None
                       else "72-hour rainfall forecast: unavailable")
    explanation.append(f"River discharge factor: {river_score:.0f}/100" if river_score is not None
                       else "River discharge factor: unavailable")
    explanation.append("Terrain/elevation exposure: unavailable (not currently connected to an elevation source).")
    explanation.append("Flood-history exposure: unavailable (JRC occurrence is not currently connected to this score).")
    explanation.append("Score is a weighted heuristic over available signals; it is not a trained model or a flood forecast.")

    return {
        "name": point["name"], "lat": lat, "lon": lon,
        "score": score if score is not None else 0.0, "level": level,
        "explanation": explanation,
        "affected_population": int(point.get("population", 0) * max(0.0, (score or 0.0) / 100.0)),
        "source": "heuristic risk score", "available_signals": [name for name, _, _ in available],
        "data_mode": satellite_result.get("mode", "UNKNOWN"),
    }


def compute_scores(points: Iterable[Dict[str, Any]], satellite_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [score_point(point, satellite_result) for point in points]
