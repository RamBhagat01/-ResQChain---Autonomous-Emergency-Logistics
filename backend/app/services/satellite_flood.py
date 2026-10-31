"""Sentinel-1 flood observation with a deterministic offline SAMPLE mode.

Sentinel-1 observes current/recent water; it is not a prediction model and is not
real-time. The live path is intentionally guarded so a missing optional geospatial
dependency or network failure returns cached/sample data instead of breaking the app.
"""
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.config import settings

logger = logging.getLogger(__name__)
refresh_lock = threading.Lock()
SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_flood_odisha.geojson"

ODISHA_TILES = [
    ("bhubaneswar", 85.70, 20.12, 86.00, 20.45),
    ("cuttack", 85.78, 20.28, 86.10, 20.62),
    ("puri", 85.65, 19.65, 86.02, 20.00),
    ("paradeep", 86.35, 20.15, 86.80, 20.55),
    ("kendrapara", 86.20, 20.30, 86.65, 20.70),
    ("balasore", 86.55, 21.25, 87.15, 21.70),
]


def threshold_flood_mask(flood_db, baseline_db, permanent_water_pct=None, slope_degrees=None):
    """Apply transparent VV/change thresholds and optional JRC/DEM masks.

    Arrays are kept as a small pure function so the masking rule can be tested
    without downloading satellite data.
    """
    import numpy as np
    mask = (np.asarray(flood_db) < settings.SATELLITE_VV_THRESHOLD_DB) & ((np.asarray(flood_db) - np.asarray(baseline_db)) < settings.SATELLITE_VV_DROP_DB)
    if permanent_water_pct is not None:
        mask &= np.asarray(permanent_water_pct) <= 80
    if slope_degrees is not None:
        mask &= np.asarray(slope_degrees) <= 5
    return mask


def _sample_geojson() -> Dict[str, Any]:
    with SAMPLE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _feature_area_km2(feature: Dict[str, Any]) -> float:
    try:
        from shapely.geometry import shape
        # Local equirectangular approximation is sufficient for a small Odisha tile.
        geom = shape(feature["geometry"])
        centroid_lat = geom.centroid.y
        scale = 111.32 * 111.32 * max(0.1, abs(__import__("math").cos(__import__("math").radians(centroid_lat))))
        return float(geom.area * scale)
    except Exception:
        return 0.0


def _sample_result() -> Dict[str, Any]:
    geojson = _sample_geojson()
    area = round(sum(_feature_area_km2(f) for f in geojson.get("features", [])), 2)
    acquired = datetime.now(timezone.utc) - timedelta(hours=6)
    return {
        "polygons": geojson,
        "flooded_km2": area,
        "scene_dates": [acquired.date().isoformat()],
        "scene_ids": ["sample-s1-odisha"],
        "data_age_hours": 6.0,
        "mode": "SAMPLE",
        "status": "sample",
        "message": "SAMPLE data is shown; Sentinel-1 is observational and this is not a live scene.",
    }


def _db_to_result(rows: Iterable[Any]) -> Dict[str, Any]:
    rows = list(rows)
    if not rows:
        return _sample_result()
    latest = max(rows, key=lambda r: r.processed_at or datetime.min.replace(tzinfo=timezone.utc))
    try:
        geojson = json.loads(latest.geojson)
    except Exception:
        geojson = {"type": "FeatureCollection", "features": []}
    dates = [r.acquired_at.date().isoformat() for r in rows if r.acquired_at]
    ids = []
    for row in rows:
        ids.extend(json.loads(row.scene_ids or "[]"))
    return {"polygons": geojson, "flooded_km2": latest.flooded_km2 or 0.0,
            "scene_dates": sorted(set(dates)), "scene_ids": sorted(set(ids)),
            "data_age_hours": latest.data_age_hours, "mode": latest.mode,
            "status": "ok", "message": None}


def _live_detect(aoi_bbox, event_window_days=12, reference_days=90) -> Dict[str, Any]:
    """Attempt a small STAC tile using Planetary Computer and stackstac.

    The heavy raster/vector path is optional. The same threshold helpers are kept
    separate so they can be tested with synthetic arrays without network access.
    """
    try:
        import numpy as np
        import planetary_computer
        from pystac_client import Client
        import stackstac
        from scipy.ndimage import median_filter, label
        from rasterio.features import shapes
        from shapely.geometry import shape, mapping
    except ImportError as exc:
        raise RuntimeError(f"live satellite dependencies unavailable: {exc}") from exc

    now = datetime.now(timezone.utc)
    catalog = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1", modifier=planetary_computer.sign_inplace)
    event = catalog.search(collections=["sentinel-1-rtc"], bbox=aoi_bbox,
                           datetime=f"{(now - timedelta(days=event_window_days)).isoformat()}/{now.isoformat()}",
                           query={"sar:polarizations": {"contains": "VV"}})
    items = list(event.items())
    if not items:
        raise RuntimeError("no Sentinel-1 RTC scenes found for tile")
    items.sort(key=lambda i: i.datetime or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    newest = items[0]
    orbit = newest.properties.get("sat:orbit_state")
    refs = catalog.search(collections=["sentinel-1-rtc"], bbox=aoi_bbox,
                          datetime=f"{(now - timedelta(days=reference_days)).isoformat()}/{(now - timedelta(days=event_window_days)).isoformat()}",
                          query={"sat:orbit_state": orbit} if orbit else None)
    ref_items = list(refs.items())[:5]
    if not ref_items:
        raise RuntimeError("no same-orbit Sentinel-1 dry baseline scenes found")
    def vv(item):
        key = "vv" if "vv" in item.assets else next((k for k in item.assets if "vv" in k.lower()), None)
        if not key:
            raise RuntimeError("scene has no VV asset")
        return stackstac.stack([item], assets=[key], bounds_latlon=aoi_bbox,
                                resolution=settings.SATELLITE_TARGET_RESOLUTION_M, snap_bounds=False).isel(time=0, band=0).compute().values
    flood = vv(newest)
    baseline = np.median(np.stack([vv(item) for item in ref_items]), axis=0)
    flood_db = 10 * np.log10(np.maximum(flood, 1e-8))
    baseline_db = 10 * np.log10(np.maximum(baseline, 1e-8))
    mask = threshold_flood_mask(flood_db, baseline_db)
    mask = median_filter(mask.astype(np.uint8), size=3) > 0
    labels, count = label(mask)
    clean = np.zeros_like(mask, dtype=bool)
    min_pixels = max(1, int(settings.SATELLITE_MIN_BLOB_AREA_KM2 * 1_000_000 / (settings.SATELLITE_TARGET_RESOLUTION_M ** 2)))
    for idx in range(1, count + 1):
        pixels = int((labels == idx).sum())
        if pixels >= min_pixels:
            clean[labels == idx] = True
    # Polygonize in the raster CRS and simplify lightly.
    transform = stackstac.stack([newest], assets=[next(k for k in newest.assets if "vv" in k.lower())], bounds_latlon=aoi_bbox, resolution=settings.SATELLITE_TARGET_RESOLUTION_M).attrs.get("transform")
    features = []
    for geom, value in shapes(clean.astype("uint8"), mask=clean, transform=transform):
        polygon = shape(geom).simplify(settings.SATELLITE_TARGET_RESOLUTION_M * 0.5)
        features.append({"type": "Feature", "properties": {"source": "SENTINEL1", "scene_id": newest.id}, "geometry": mapping(polygon)})
    acquired = newest.datetime or now
    geojson = {"type": "FeatureCollection", "features": features}
    return {"polygons": geojson, "flooded_km2": round(sum(_feature_area_km2(f) for f in features), 2),
            "scene_dates": [acquired.date().isoformat()], "scene_ids": [newest.id],
            "data_age_hours": round((now - acquired).total_seconds() / 3600, 1), "mode": "LIVE", "status": "ok", "message": None}


def detect_flood(aoi_bbox, event_window_days=12, reference_days=90) -> Dict[str, Any]:
    """Detect observed flood water for one small AOI tile, never the entire state."""
    if settings.SATELLITE_MODE == "sample":
        return _sample_result()
    try:
        return _live_detect(aoi_bbox, event_window_days, reference_days)
    except Exception as exc:
        logger.warning("Sentinel-1 processing failed: %s", exc)
        return _sample_result() | {"status": "fallback", "message": f"Live processing unavailable: {exc}; SAMPLE fallback used."}


def refresh_satellite_cache(session_factory) -> None:
    """Process tiles in a scheduler worker and persist each tile independently."""
    if not refresh_lock.acquire(blocking=False):
        logger.info("Satellite refresh already running; skipping overlapping job")
        return
    try:
        from app.models import SatelliteFloodObservation
        db = session_factory()
        try:
            for tile, min_lon, min_lat, max_lon, max_lat in ODISHA_TILES:
                result = detect_flood((min_lon, min_lat, max_lon, max_lat), settings.SATELLITE_EVENT_WINDOW_DAYS, settings.SATELLITE_REFERENCE_DAYS)
                now = datetime.now(timezone.utc)
                acquired = now - timedelta(hours=result.get("data_age_hours") or 0)
                db.add(SatelliteFloodObservation(tile=tile, scene_ids=json.dumps(result["scene_ids"]), acquired_at=acquired,
                    processed_at=now, flooded_km2=result["flooded_km2"], geojson=json.dumps(result["polygons"]),
                    mode=result["mode"], data_age_hours=result.get("data_age_hours")))
            db.commit()
        finally:
            db.close()
    finally:
        refresh_lock.release()


def latest_result(db) -> Dict[str, Any]:
    from app.models import SatelliteFloodObservation
    return _db_to_result(db.query(SatelliteFloodObservation).order_by(SatelliteFloodObservation.processed_at.desc()).limit(20).all())
