# Sentinel-1 Flood Observation, Heuristic Risk and Warehouse Siting

## What this adds

ResQChain now has an optional Sentinel-1 RTC observation path, an explicit heuristic flood-risk score, satellite-context resource reasoning, and an OSM-based warehouse/staging recommendation service.

Sentinel-1 is radar imagery that observes current or recent water. It is not real-time and it does not predict floods. Its revisit interval is measured in days and results can be affected by urban layover, vegetation, terrain, wind/waves, speckle and scene availability.

The prediction endpoint is labelled `heuristic risk score`. It combines observed flood proximity, 72-hour rainfall, river discharge, low-lying exposure and flood-history proxies using configurable weights. It is transparent decision support, not a trained AI model.

## Modes

Set `SATELLITE_MODE=sample` for an offline-safe demo. The backend uses [sample_flood_odisha.geojson](../backend/app/data/sample_flood_odisha.geojson), and the API/UI must show `SAMPLE`.

Set `SATELLITE_MODE=live` to attempt Microsoft Planetary Computer STAC searches against `sentinel-1-rtc`. The live path processes one small AOI tile at a time, uses a recent scene and up to five same-orbit reference scenes, applies VV dB/change thresholds, light median filtering, blob cleanup and vectorization. Missing dependencies, unavailable scenes or network errors fall back to the sample result and report the fallback.

The scheduled refresh is separate from the ten-second swarm cycle and HTTP requests. It runs every `SATELLITE_REFRESH_HOURS` in an APScheduler worker and uses a process lock to prevent overlapping refreshes.

## API

- `GET /api/satellite/flood` returns polygons, flooded square kilometres, scene dates/IDs, data age, and `LIVE`/`SAMPLE` mode.
- `POST /api/satellite/refresh` queues a background refresh and returns immediately.
- `GET /api/flood-prediction` returns 0–100 scores, LOW/MODERATE/HIGH/CRITICAL levels and factor explanations.
- `GET /api/warehouse-sites?lat=&lon=&radius_km=&limit=` returns decision-support candidates and requires human verification.

## Warehouse siting

The siting service queries Overpass for warehouse, industrial, wholesale, marketplace, school, college and community-centre candidates. It excludes candidates inside known flood polygons, scores distance to hazards/camps and labels the result as decision support. OSM links are included when the candidate has an OSM identity. Responses can be unavailable if Overpass is unavailable; the service does not fabricate external locations. Seed hubs may be shown as clearly labelled project reference candidates when no OSM response is available.

Before using any recommendation, a human must verify ownership, legal permissions, access roads, structural suitability, current flood safety, utilities and availability.

## Manual official references

See [odisha_reference_sources.json](../backend/app/data/odisha_reference_sources.json) for OSDMA, India-WRIS, CWC and ISRO Bhuvan links. These are manual references, not live integrations.

## Limitations and follow-up

- Live raster dependencies are optional and can be large to install.
- The current live implementation is designed for small tiles; do not expand it to process the whole state in one raster request.
- Terrain/history enrichment is intentionally conservative in offline/sample mode and is labelled as heuristic.
- Overpass/Nominatim usage must retain timeouts, caching, custom User-Agent policy and rate limits before production use.
- A live refresh duration was not measured in this environment because the verified run used offline-safe sample mode; measure it on the target laptop after installing optional geospatial dependencies and enabling `SATELLITE_MODE=live`.
