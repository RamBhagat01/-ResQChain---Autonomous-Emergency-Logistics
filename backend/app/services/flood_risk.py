"""
GloFAS Flood Risk Service (via Open-Meteo Flood API)
Fetches real-time river discharge data for Odisha monitoring points
and classifies flood risk using CWC Mahanadi basin thresholds.
No API key required — Open-Meteo is fully free and open.
"""

import httpx
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

FLOOD_API_URL = "https://flood-api.open-meteo.com/v1/flood"

# CWC (Central Water Commission) thresholds for Mahanadi basin (m³/s)
THRESHOLDS = [
    ("NORMAL",     0,      2000),
    ("WARNING",    2000,   3500),
    ("DANGER",     3500,   5000),
    ("HIGH_FLOOD", 5000,   float("inf")),
]

RISK_COLORS = {
    "NORMAL":     "#22c55e",   # green
    "WARNING":    "#f59e0b",   # amber
    "DANGER":     "#f97316",   # orange
    "HIGH_FLOOD": "#ef4444",   # red
    "UNKNOWN":    "#94a3b8",   # slate
}

RISK_PCT = {
    "NORMAL":     15,
    "WARNING":    45,
    "DANGER":     75,
    "HIGH_FLOOD": 95,
    "UNKNOWN":    0,
}

RISK_SEVERITY = {
    "NORMAL":     1,
    "WARNING":    2,
    "DANGER":     4,
    "HIGH_FLOOD": 5,
    "UNKNOWN":    0,
}


def classify_discharge(discharge_m3s: float) -> str:
    """Convert a river discharge value (m³/s) to a risk label."""
    for label, low, high in THRESHOLDS:
        if low <= discharge_m3s < high:
            return label
    return "UNKNOWN"


def get_flood_risk(name: str, lat: float, lon: float) -> Dict:
    """
    Query Open-Meteo GloFAS flood API for a single monitoring point.
    Returns a dict with discharge, risk level, color, percentage, and severity.
    Falls back gracefully to UNKNOWN on network errors.
    """
    try:
        resp = httpx.get(
            FLOOD_API_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "river_discharge,river_discharge_mean,river_discharge_max",
                "forecast_days": 3,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()

        daily = data.get("daily", {})
        discharges = daily.get("river_discharge", [])
        discharge_means = daily.get("river_discharge_mean", [])
        discharge_maxes = daily.get("river_discharge_max", [])
        times = daily.get("time", [])

        if not discharges:
            raise ValueError("Empty discharge data")

        # Use today's discharge (index 0)
        discharge = round(float(discharges[0]), 1)
        discharge_mean = round(float(discharge_means[0]), 1) if discharge_means else discharge
        discharge_max = round(float(discharge_maxes[0]), 1) if discharge_maxes else discharge
        today = times[0] if times else "N/A"

        risk_level = classify_discharge(discharge)

        return {
            "name": name,
            "lat": lat,
            "lon": lon,
            "date": today,
            "discharge_m3s": discharge,
            "discharge_mean_m3s": discharge_mean,
            "discharge_max_m3s": discharge_max,
            "risk_level": risk_level,
            "risk_pct": RISK_PCT[risk_level],
            "risk_color": RISK_COLORS[risk_level],
            "severity": RISK_SEVERITY[risk_level],
            "source": "GloFAS / Open-Meteo",
            "error": None,
        }

    except Exception as exc:
        logger.warning("GloFAS fetch failed for %s (%s, %s): %s", name, lat, lon, exc)
        return {
            "name": name,
            "lat": lat,
            "lon": lon,
            "date": None,
            "discharge_m3s": None,
            "discharge_mean_m3s": None,
            "discharge_max_m3s": None,
            "risk_level": "UNKNOWN",
            "risk_pct": 0,
            "risk_color": RISK_COLORS["UNKNOWN"],
            "severity": 0,
            "source": "GloFAS / Open-Meteo",
            "error": str(exc),
        }


def get_all_flood_risks(monitoring_points: List[Dict]) -> List[Dict]:
    """Fetch flood risk for all monitoring points and return sorted by severity (desc)."""
    results = [get_flood_risk(p["name"], p["lat"], p["lon"]) for p in monitoring_points]
    return sorted(results, key=lambda x: x["severity"], reverse=True)

