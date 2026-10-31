"""OSM-based warehouse/staging recommendations; decision support only."""
import time
from typing import Any, Dict, List, Optional
import httpx

from app.services.geo import haversine_km
from app.config import settings

_cache: Dict[str, tuple[float, Any]] = {}


def _cached(key: str):
    entry = _cache.get(key)
    return entry[1] if entry and time.time() - entry[0] < 86400 else None


def _overpass(lat: float, lon: float, radius_km: float) -> List[Dict[str, Any]]:
    key = f"overpass:{round(lat,3)}:{round(lon,3)}:{round(radius_km,1)}"
    cached = _cached(key)
    if cached is not None:
        return cached
    query = f"""[out:json][timeout:20];(nwr(around:{radius_km*1000},{lat},{lon})[building=warehouse];nwr(around:{radius_km*1000},{lat},{lon})[landuse=industrial];nwr(around:{radius_km*1000},{lat},{lon})[shop=wholesale];nwr(around:{radius_km*1000},{lat},{lon})[amenity=marketplace];nwr(around:{radius_km*1000},{lat},{lon})[amenity~'school|college|community_centre'];);out center tags;"""
    try:
        data = httpx.post("https://overpass-api.de/api/interpreter", data=query, timeout=25).json()
        sites = []
        for item in data.get("elements", []):
            tags = item.get("tags", {})
            center = item.get("center", item)
            if center.get("lat") is None:
                continue
            sites.append({"name": tags.get("name", "Unnamed OSM candidate"), "lat": center["lat"], "lon": center["lon"],
                "address": ", ".join(filter(None, [tags.get("addr:street"), tags.get("addr:city")])),
                "osm_id": f"{item.get('type','node')}/{item.get('id')}", "tags": tags})
        _cache[key] = (time.time(), sites)
        return sites
    except Exception:
        return []


def recommend_sites(lat: float, lon: float, radius_km: float, limit: int, flood_result: Dict[str, Any], zones: List[Any], camps: List[Any]) -> Dict[str, Any]:
    sites = [] if settings.SATELLITE_MODE == "sample" else _overpass(lat, lon, radius_km)
    if not sites:
        # These are existing project seed hubs, not fabricated OSM results; label clearly.
        sites = [{"name": "Bhubaneswar Central Hub (seed reference)", "lat": 20.2961, "lon": 85.8245, "address": "Bhubaneswar, Odisha", "osm_id": None, "tags": {}},
                 {"name": "Cuttack Mahanadi Depot (seed reference)", "lat": 20.4625, "lon": 85.8828, "address": "Cuttack, Odisha", "osm_id": None, "tags": {}}]
    try:
        from shapely.geometry import Point, shape
        flood_geoms = [shape(f["geometry"]) for f in flood_result.get("polygons", {}).get("features", [])]
    except Exception:
        flood_geoms = []
    ranked = []
    for site in sites:
        point = Point(site["lon"], site["lat"]) if 'Point' in locals() else None
        if point is not None and any(g.contains(point) for g in flood_geoms):
            continue
        hazard_distance = min([haversine_km(site["lat"], site["lon"], z.center_lat, z.center_lon) for z in zones] or [25.0])
        travel = min([haversine_km(site["lat"], site["lon"], c.lat, c.lon) for c in camps] or [25.0])
        score = max(0.0, min(100.0, 55 + min(25, hazard_distance * 2) - min(25, travel / 2)))
        reason = f"Decision support: {score:.0f}/100; {hazard_distance:.1f} km from nearest active hazard and {travel:.1f} km from nearest camp. Human must verify ownership, access and availability."
        ranked.append({"name": site["name"], "address": site.get("address") or None, "lat": site["lat"], "lon": site["lon"],
            "osm_link": f"https://www.openstreetmap.org/{site['osm_id']}" if site.get("osm_id") else None,
            "score": round(score, 1), "reason": reason, "status": "decision support"})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    for idx, site in enumerate(ranked[:limit], 1):
        site["rank"] = idx
    return {"status": "ok" if ranked else "unavailable", "decision_support": True, "human_verification_required": True,
            "sites": ranked[:limit], "message": "These are decision-support candidates; verify ownership, access, flood safety and availability manually."}
