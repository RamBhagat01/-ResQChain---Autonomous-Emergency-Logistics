"""Cached, batched GloFAS/Open-Meteo readings for Odisha monitoring points."""

from datetime import datetime, timedelta, timezone
import logging
import threading
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)
FLOOD_API_URL = "https://flood-api.open-meteo.com/v1/flood"
CACHE_TTL = timedelta(minutes=15)
STALE_TTL = timedelta(hours=24)
RATE_LIMIT_COOLDOWN = timedelta(minutes=15)
_cache_lock = threading.Lock()
_cache: Dict[str, Dict] = {}
_cache_updated_at: Optional[datetime] = None
_retry_not_before: Optional[datetime] = None

THRESHOLDS = [("NORMAL", 0, 2000), ("WARNING", 2000, 3500),
              ("DANGER", 3500, 5000), ("HIGH_FLOOD", 5000, float("inf"))]
RISK_COLORS = {"NORMAL": "#22c55e", "WARNING": "#f59e0b", "DANGER": "#f97316",
               "HIGH_FLOOD": "#ef4444", "UNKNOWN": "#94a3b8"}
RISK_PCT = {"NORMAL": 15, "WARNING": 45, "DANGER": 75, "HIGH_FLOOD": 95, "UNKNOWN": 0}
RISK_SEVERITY = {"NORMAL": 1, "WARNING": 2, "DANGER": 4, "HIGH_FLOOD": 5, "UNKNOWN": 0}


def classify_discharge(discharge_m3s: float) -> str:
    for label, low, high in THRESHOLDS:
        if low <= discharge_m3s < high:
            return label
    return "UNKNOWN"


def _unknown(point: Dict, error: str, status: str = "UNAVAILABLE", retry_after_seconds: Optional[int] = None) -> Dict:
    return {"name": point["name"], "lat": point["lat"], "lon": point["lon"],
            "date": None, "discharge_m3s": None, "discharge_mean_m3s": None,
            "discharge_max_m3s": None, "risk_level": "UNKNOWN", "risk_pct": 0,
            "risk_color": RISK_COLORS["UNKNOWN"], "severity": 0,
            "source": "GloFAS / Open-Meteo", "status": status, "error": error,
            "retry_after_seconds": retry_after_seconds}


def _from_daily(point: Dict, data: Dict) -> Dict:
    daily = data.get("daily", {})
    discharges = daily.get("river_discharge") or []
    if not discharges or discharges[0] is None:
        return _unknown(point, "Open-Meteo returned no discharge observations")
    discharge = round(float(discharges[0]), 1)
    means = daily.get("river_discharge_mean") or []
    maxima = daily.get("river_discharge_max") or []
    level = classify_discharge(discharge)
    return {"name": point["name"], "lat": point["lat"], "lon": point["lon"],
            "date": (daily.get("time") or [None])[0], "discharge_m3s": discharge,
            "discharge_mean_m3s": round(float(means[0]), 1) if means and means[0] is not None else discharge,
            "discharge_max_m3s": round(float(maxima[0]), 1) if maxima and maxima[0] is not None else discharge,
            "risk_level": level, "risk_pct": RISK_PCT[level], "risk_color": RISK_COLORS[level],
            "severity": RISK_SEVERITY[level], "source": "GloFAS / Open-Meteo",
            "status": "LIVE", "error": None}


def _response_locations(payload) -> List[Dict]:
    # Open-Meteo returns an object for one coordinate and an ordered array for many.
    if isinstance(payload, list):
        return payload
    return [payload] if isinstance(payload, dict) else []


def _fetch_batch(points: List[Dict]) -> Dict[str, Dict]:
    params = {"latitude": ",".join(str(p["lat"]) for p in points),
              "longitude": ",".join(str(p["lon"]) for p in points),
              "daily": "river_discharge,river_discharge_mean,river_discharge_max",
              "forecast_days": 3}
    # One batched request replaces one request per monitoring location.
    with httpx.Client(timeout=httpx.Timeout(12.0, connect=5.0)) as client:
        response = client.get(FLOOD_API_URL, params=params)
        response.raise_for_status()
        locations = _response_locations(response.json())
    if len(locations) != len(points):
        raise ValueError(f"Expected {len(points)} locations, received {len(locations)}")
    now = datetime.now(timezone.utc).isoformat()
    result = {}
    for point, data in zip(points, locations):
        item = _from_daily(point, data)
        item["observed_at"] = now
        result[point["name"]] = item
    return result


def _snapshot(points: List[Dict], allow_stale: bool = True) -> List[Dict]:
    global _cache_updated_at, _retry_not_before
    now = datetime.now(timezone.utc)
    with _cache_lock:
        if _cache and _cache_updated_at and now - _cache_updated_at < CACHE_TTL:
            return [_cache.get(p["name"], _unknown(p, "No cached reading")) for p in points]
        if _retry_not_before and now < _retry_not_before:
            seconds = max(1, int((_retry_not_before - now).total_seconds()))
            return [_unknown(p, "GloFAS provider is temporarily rate-limiting requests.", "RATE_LIMITED", seconds)
                    for p in points]
        try:
            fresh = _fetch_batch(points)
            _cache.clear()
            _cache.update(fresh)
            _cache_updated_at = now
            _retry_not_before = None
            return [fresh.get(p["name"], _unknown(p, "No reading returned")) for p in points]
        except Exception as exc:
            logger.warning("Batched GloFAS request failed: %s", exc)
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            if status_code == 429:
                _retry_not_before = now + RATE_LIMIT_COOLDOWN
            if allow_stale and _cache and _cache_updated_at and now - _cache_updated_at < STALE_TTL:
                age_minutes = max(1, int((now - _cache_updated_at).total_seconds() / 60))
                fallback = []
                for point in points:
                    item = dict(_cache.get(point["name"], _unknown(point, str(exc))))
                    item.update(status="CACHED", error=f"Upstream unavailable; showing last successful reading ({age_minutes} min old).")
                    item["cache_age_minutes"] = age_minutes
                    fallback.append(item)
                return fallback
            if status_code == 429:
                return [_unknown(p, "GloFAS provider is temporarily rate-limiting requests.", "RATE_LIMITED",
                                 int(RATE_LIMIT_COOLDOWN.total_seconds())) for p in points]
            return [_unknown(p, str(exc)) for p in points]


def get_all_flood_risks(monitoring_points: List[Dict]) -> List[Dict]:
    """Return one batched snapshot, reusing fresh cache and serving stale cache on errors."""
    return sorted(_snapshot(monitoring_points), key=lambda x: x["severity"], reverse=True)


def get_cached_flood_risk(lat: float, lon: float, tolerance: float = 0.01) -> Optional[Dict]:
    """Find a recent cached monitoring reading near coordinates without another API call."""
    with _cache_lock:
        if not _cache or not _cache_updated_at or datetime.now(timezone.utc) - _cache_updated_at >= STALE_TTL:
            return None
        candidates = [item for item in _cache.values()
                      if abs(float(item["lat"]) - lat) <= tolerance and abs(float(item["lon"]) - lon) <= tolerance]
        if not candidates:
            return None
        return min(candidates, key=lambda item: (float(item["lat"]) - lat) ** 2 + (float(item["lon"]) - lon) ** 2)


def get_flood_risk(name: str, lat: float, lon: float) -> Dict:
    """Compatibility helper: use cache when available, otherwise fetch only this coordinate."""
    cached = get_cached_flood_risk(lat, lon)
    if cached:
        return {**cached, "name": name}
    return _snapshot([{"name": name, "lat": lat, "lon": lon}], allow_stale=False)[0]
