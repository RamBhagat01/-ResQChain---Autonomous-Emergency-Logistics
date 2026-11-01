import React, { useEffect, useMemo, useState } from 'react';
import { Navigation, Route, AlertTriangle, ChevronDown, MapPin } from 'lucide-react';
import { fetchWarehouseRiskRoute } from '../api';

function distanceKm(a, b) {
  const toRad = (value) => (value * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const value = Math.sin(dLat / 2) ** 2
    + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

const monitoringLocalities = [
  { name: 'Bhubaneswar', lat: 20.2961, lon: 85.8245 },
  { name: 'Cuttack', lat: 20.4625, lon: 85.8828 },
  { name: 'Puri', lat: 19.8135, lon: 85.8312 },
  { name: 'Paradeep', lat: 20.316, lon: 86.6114 },
  { name: 'Kendrapara', lat: 20.5, lon: 86.42 },
  { name: 'Balasore', lat: 21.4934, lon: 86.9135 },
];

function describeZoneLocation(zone) {
  const closest = monitoringLocalities
    .map((locality) => ({ ...locality, distance_km: distanceKm(zone, locality) }))
    .sort((a, b) => a.distance_km - b.distance_km)[0];
  const genericName = /^flood zone(?:\s*\(severity\s*\d+\))?$/i.test(String(zone.name).trim());
  if (!genericName) return { name: zone.name, displayName: zone.name, zoneLabel: 'Active hazard zone' };
  return {
    name: `Near ${closest.name}`,
    displayName: `Near ${closest.name} — ${zone.name} (${Number(zone.center_lat).toFixed(3)}, ${Number(zone.center_lon).toFixed(3)})`,
    zoneLabel: 'Flood zone',
  };
}

function probabilityBadgeClass(level) {
  if (level === 'HIGH' || level === 'CRITICAL') return 'bg-red-50 text-red-700';
  if (level === 'MODERATE') return 'bg-blue-50 text-blue-700';
  if (level === 'LOW') return 'bg-green-50 text-green-700';
  return 'bg-slate-100 text-slate-600';
}

function glofasToRiskLevel(level) {
  if (level === 'HIGH_FLOOD') return 'CRITICAL';
  if (level === 'DANGER') return 'HIGH';
  if (level === 'WARNING') return 'MODERATE';
  if (level === 'NORMAL') return 'LOW';
  return 'UNKNOWN';
}

function riskLevelRank(level) {
  return { UNKNOWN: 0, LOW: 1, MODERATE: 2, HIGH: 3, CRITICAL: 4 }[level] ?? 0;
}

export default function RoutePlanner({ predictions = [], glofasRisks = [], zones = [], warehouses = [], onRouteChange, onRiskAreaChange }) {
  const [riskId, setRiskId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [routeInfo, setRouteInfo] = useState(null);
  const [riskMenuOpen, setRiskMenuOpen] = useState(false);

  const riskAreas = useMemo(() => {
    const areas = predictions
      .filter((item) => ['MODERATE', 'HIGH', 'CRITICAL'].includes(item.level))
      .map((item) => ({
        id: `risk-${item.name}-${item.lat}-${item.lon}`,
        name: item.name,
        displayName: item.name,
        zoneLabel: 'Forecast risk area',
        lat: Number(item.lat),
        lon: Number(item.lon),
        level: item.level,
        heuristicLevel: item.level,
        score: Number(item.score ?? 0),
        heuristicScore: Number(item.score ?? 0),
      }));

    glofasRisks.filter((point) => point.risk_level !== 'UNKNOWN'
      && Number.isFinite(Number(point.lat)) && Number.isFinite(Number(point.lon)))
      .forEach((point) => {
        const glofasLevel = glofasToRiskLevel(point.risk_level);
        const glofasScore = Number(point.risk_pct ?? 0);
        const existing = areas.find((area) => distanceKm(area, { lat: Number(point.lat), lon: Number(point.lon) }) < 2);
        if (existing) {
          existing.glofas = point;
          existing.name = point.name || existing.name;
          existing.level = riskLevelRank(glofasLevel) > riskLevelRank(existing.level) ? glofasLevel : existing.level;
          existing.score = Math.max(existing.heuristicScore, glofasScore);
          existing.zoneLabel = `GloFAS ${point.risk_level.replace('_', ' ')} · heuristic ${existing.heuristicLevel}`;
        } else {
          areas.push({
            id: `glofas-${point.name}-${point.lat}-${point.lon}`,
            name: point.name,
            displayName: point.name,
            zoneLabel: `GloFAS ${point.risk_level.replace('_', ' ')}`,
            lat: Number(point.lat),
            lon: Number(point.lon),
            level: glofasLevel,
            score: glofasScore,
            glofas: point,
            source: 'GloFAS',
          });
        }
      });

    zones.filter((zone) => zone.active).forEach((zone) => {
      const lat = Number(zone.center_lat);
      const lon = Number(zone.center_lon);
      const existing = areas.find((item) => distanceKm(item, { lat, lon }) < 2);
      if (!existing) {
        const location = describeZoneLocation({ ...zone, lat, lon });
        areas.push({
          id: `zone-${zone.id}`,
          ...location,
          lat,
          lon,
          level: zone.severity >= 5 ? 'CRITICAL' : zone.severity >= 4 ? 'HIGH' : 'MODERATE',
          score: zone.severity * 20,
        });
      }
    });

    return areas.sort((a, b) => b.score - a.score);
  }, [predictions, glofasRisks, zones]);

  const selectedRisk = riskAreas.find((item) => item.id === riskId) ?? riskAreas[0];

  useEffect(() => {
    onRiskAreaChange?.(selectedRisk ?? null);
  }, [selectedRisk, onRiskAreaChange]);

  const nearestWarehouses = useMemo(() => {
    if (!selectedRisk) return [];
    const sitesByCoordinate = new Map();
    warehouses.forEach((warehouse) => {
      const lat = Number(warehouse.lat);
      const lon = Number(warehouse.lon);
      if (!Number.isFinite(lat) || !Number.isFinite(lon)) return;
      const key = `${lat.toFixed(6)},${lon.toFixed(6)}`;
      if (!sitesByCoordinate.has(key)) sitesByCoordinate.set(key, { ...warehouse, lat, lon });
    });
    return [...sitesByCoordinate.values()]
      .map((warehouse) => ({ ...warehouse, distance_km: distanceKm(selectedRisk, warehouse) }))
      .sort((a, b) => a.distance_km - b.distance_km)
      .slice(0, 3);
  }, [selectedRisk, warehouses]);

  useEffect(() => {
    if (!riskAreas.some((item) => item.id === riskId)) setRiskId(riskAreas[0]?.id ?? '');
  }, [riskAreas, riskId]);

  useEffect(() => {
    if (!nearestWarehouses.some((item) => String(item.serial_no) === warehouseId)) {
      setWarehouseId(String(nearestWarehouses[0]?.serial_no ?? ''));
    }
  }, [nearestWarehouses, warehouseId]);

  const chooseRisk = (value) => {
    setRiskId(value);
    setRouteInfo(null);
    setError('');
    onRouteChange?.(null);
  };

  const chooseWarehouse = (value) => {
    setWarehouseId(value);
    setRouteInfo(null);
    setError('');
    onRouteChange?.(null);
  };

  const showRoute = async () => {
    const warehouse = nearestWarehouses.find((item) => String(item.serial_no) === warehouseId);
    if (!selectedRisk || !warehouse) return;
    setLoading(true);
    setError('');
    try {
      const result = await fetchWarehouseRiskRoute({
        origin_lat: warehouse.lat,
        origin_lon: warehouse.lon,
        dest_lat: selectedRisk.lat,
        dest_lon: selectedRisk.lon,
      });
      if (!result.available) throw new Error(result.message || 'OSRM road route is unavailable.');
      const preview = { ...result, warehouse, risk: selectedRisk };
      setRouteInfo(preview);
      onRouteChange?.(preview);
    } catch (err) {
      setError(err.message || 'Route service unavailable.');
      onRouteChange?.(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm" aria-label="Warehouse route planner">
      <div className="mb-3 flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-50"><Route size={16} className="text-sky-700" /></div>
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Emergency Supply Route</h3>
          <p className="text-xs text-slate-500">Choose a risk area to focus the map, then select one of its three nearest warehouse locations.</p>
        </div>
      </div>

      {riskAreas.length === 0 ? (
        <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">No moderate-or-higher predicted risks or active hazard zones are available to route to.</p>
      ) : warehouses.length === 0 ? (
        <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Warehouse locations are unavailable.</p>
      ) : (
        <>
          <div className="relative mb-3" onBlur={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget)) setRiskMenuOpen(false);
          }}>
            <span className="mb-1 block text-xs font-medium text-slate-600">Risk area</span>
            <button
              type="button"
              aria-haspopup="listbox"
              aria-expanded={riskMenuOpen}
              onClick={() => setRiskMenuOpen((open) => !open)}
              className="flex min-h-[54px] w-full items-center gap-3 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-left shadow-sm transition hover:border-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-200"
            >
              <MapPin size={19} className="shrink-0 text-slate-500" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-slate-800">{selectedRisk?.name ?? 'Choose a risk area'}</span>
                {selectedRisk && <span className="block text-xs text-slate-500">{selectedRisk.zoneLabel} · {selectedRisk.level} risk</span>}
              </span>
              {selectedRisk && <span className={`shrink-0 rounded-full px-3 py-1 text-sm font-semibold ${probabilityBadgeClass(selectedRisk.level)}`}>
                {selectedRisk.glofas ? `${Math.round(selectedRisk.glofas.risk_pct)}% GloFAS index` : `${Math.round(selectedRisk.score)}% Probability`}
              </span>}
              <ChevronDown size={17} className={`shrink-0 text-slate-500 transition-transform ${riskMenuOpen ? 'rotate-180' : ''}`} />
            </button>
            {riskMenuOpen && <div role="listbox" aria-label="Flood risk areas" className="absolute left-0 right-0 top-full z-[1200] mt-1 max-h-64 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl">
              {riskAreas.map((area) => (
                <button
                  key={area.id}
                  type="button"
                  role="option"
                  aria-selected={selectedRisk?.id === area.id}
                  onClick={() => {
                    chooseRisk(area.id);
                    setRiskMenuOpen(false);
                  }}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition ${selectedRisk?.id === area.id ? 'bg-slate-50' : 'hover:bg-slate-50'}`}
                >
                  <MapPin size={17} className="shrink-0 text-slate-500" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-slate-800">{area.name}</span>
                    <span className="block text-xs text-slate-500">{area.zoneLabel || 'Forecast risk area'} · {area.level} risk</span>
                  </span>
                  <span className={`shrink-0 rounded-full px-3 py-1 text-sm font-semibold ${probabilityBadgeClass(area.level)}`}>
                    {area.glofas ? `${Math.round(area.glofas.risk_pct)}% GloFAS index` : `${Math.round(area.score)}% Probability`}
                  </span>
                </button>
              ))}
            </div>}
          </div>

          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Nearest warehouse options</p>
          <div className="grid gap-2 sm:grid-cols-3">
            {nearestWarehouses.map((warehouse, index) => (
              <label key={warehouse.serial_no} className={`cursor-pointer rounded-xl border p-3 transition ${warehouseId === String(warehouse.serial_no) ? 'border-emerald-600 bg-emerald-50 ring-1 ring-emerald-500' : 'border-slate-200 hover:border-slate-400'}`}>
                <span className="flex items-start gap-2">
                  <input type="radio" name="route-warehouse" value={warehouse.serial_no} checked={warehouseId === String(warehouse.serial_no)} onChange={(event) => chooseWarehouse(event.target.value)} className="mt-0.5 accent-emerald-700" />
                  <span>
                    <span className="block text-sm font-semibold text-slate-800">{index + 1}. W{warehouse.serial_no} · {warehouse.zone_name} warehouse</span>
                    <span className="mt-0.5 block text-xs text-slate-500">{warehouse.distance_km.toFixed(1)} km straight-line</span>
                    <span className="block text-[11px] text-slate-400">Reported vacant: {Number(warehouse.vacant_space_mt).toLocaleString()} MT</span>
                  </span>
                </span>
              </label>
            ))}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button onClick={showRoute} disabled={loading || !selectedRisk || !warehouseId} className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800 disabled:cursor-not-allowed disabled:opacity-50">
              <Navigation size={15} className={loading ? 'animate-pulse' : ''} />{loading ? 'Finding route…' : 'Show transport route'}
            </button>
            {error && <span className="text-sm text-rose-700" role="alert">{error}</span>}
          </div>

          {routeInfo && <div className="mt-3 flex items-start gap-2 rounded-lg bg-sky-50 p-3 text-sm text-sky-900">
            <Navigation size={16} className="mt-0.5 shrink-0" />
            <p><strong>{routeInfo.warehouse.zone_name} warehouse → {routeInfo.risk.name}</strong><br />{routeInfo.distance_km} km · about {routeInfo.duration_min} min · {routeInfo.routing}. Verify road closures and warehouse availability before dispatch.</p>
          </div>}
          {routeInfo?.hazard_warning && <p className="mt-2 rounded-lg bg-rose-50 p-2 text-xs font-medium text-rose-800" role="alert">{routeInfo.hazard_warning}</p>}
          <p className="mt-2 flex items-start gap-1 text-[11px] text-amber-700"><AlertTriangle size={12} className="mt-0.5 shrink-0" />Nearest choices use straight-line distance; the displayed path follows OSRM road geometry. Stock and road access must be confirmed before dispatch.</p>
        </>
      )}
    </section>
  );
}
