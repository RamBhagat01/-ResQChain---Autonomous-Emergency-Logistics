import React, { useEffect, useMemo, useState } from 'react';
import { Navigation, Route, AlertTriangle } from 'lucide-react';
import { fetchWarehouseRiskRoute } from '../api';

function distanceKm(a, b) {
  const toRad = (value) => (value * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const value = Math.sin(dLat / 2) ** 2
    + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

export default function RoutePlanner({ predictions = [], zones = [], warehouses = [], onRouteChange }) {
  const [riskId, setRiskId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [routeInfo, setRouteInfo] = useState(null);

  const riskAreas = useMemo(() => {
    const areas = predictions
      .filter((item) => ['MODERATE', 'HIGH', 'CRITICAL'].includes(item.level))
      .map((item) => ({
        id: `risk-${item.name}-${item.lat}-${item.lon}`,
        name: item.name,
        lat: Number(item.lat),
        lon: Number(item.lon),
        level: item.level,
        score: Number(item.score ?? 0),
      }));

    zones.filter((zone) => zone.active).forEach((zone) => {
      const lat = Number(zone.center_lat);
      const lon = Number(zone.center_lon);
      const existing = areas.find((item) => distanceKm(item, { lat, lon }) < 2);
      if (!existing) areas.push({
        id: `zone-${zone.id}`,
        name: zone.name,
        lat,
        lon,
        level: zone.severity >= 5 ? 'CRITICAL' : zone.severity >= 4 ? 'HIGH' : 'MODERATE',
        score: zone.severity * 20,
      });
    });

    return areas.sort((a, b) => b.score - a.score);
  }, [predictions, zones]);

  const selectedRisk = riskAreas.find((item) => item.id === riskId) ?? riskAreas[0];

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
          <p className="text-xs text-slate-500">Choose a risk area and one of its three nearest warehouse locations.</p>
        </div>
      </div>

      {riskAreas.length === 0 ? (
        <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">No moderate-or-higher predicted risks or active hazard zones are available to route to.</p>
      ) : warehouses.length === 0 ? (
        <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Warehouse locations are unavailable.</p>
      ) : (
        <>
          <label className="mb-3 block text-xs font-medium text-slate-600">
            Risk area
            <select value={selectedRisk?.id ?? ''} onChange={(event) => chooseRisk(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800">
              {riskAreas.map((area) => <option key={area.id} value={area.id}>{area.name} · {area.level} ({area.score}/100)</option>)}
            </select>
          </label>

          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Nearest warehouse options</p>
          <div className="grid gap-2 sm:grid-cols-3">
            {nearestWarehouses.map((warehouse, index) => (
              <label key={warehouse.serial_no} className={`cursor-pointer rounded-xl border p-3 transition ${warehouseId === String(warehouse.serial_no) ? 'border-emerald-600 bg-emerald-50 ring-1 ring-emerald-500' : 'border-slate-200 hover:border-slate-400'}`}>
                <span className="flex items-start gap-2">
                  <input type="radio" name="route-warehouse" value={warehouse.serial_no} checked={warehouseId === String(warehouse.serial_no)} onChange={(event) => chooseWarehouse(event.target.value)} className="mt-0.5 accent-emerald-700" />
                  <span>
                    <span className="block text-sm font-semibold text-slate-800">{index + 1}. {warehouse.zone_name} warehouse</span>
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
