import React, { useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline, GeoJSON, CircleMarker, useMapEvents, useMap } from 'react-leaflet';
import L from 'leaflet';

// Custom Map Click Handler to capture coordinates for disaster simulation
function MapClickHandler({ onLocationSelect }) {
  useMapEvents({
    click(e) {
      if (onLocationSelect) {
        onLocationSelect(e.latlng.lat, e.latlng.lng);
      }
    },
  });
  return null;
}

function FitWarehouseBounds({ warehouses }) {
  const map = useMap();
  const hasFit = useRef(false);
  useEffect(() => {
    if (hasFit.current || !warehouses.length) return;
    const bounds = L.latLngBounds(warehouses.map((item) => [item.lat, item.lon]));
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [36, 36], maxZoom: 8 });
    hasFit.current = true;
  }, [map, warehouses]);
  return null;
}

function FitPreviewRoute({ route }) {
  const map = useMap();
  useEffect(() => {
    const coords = route?.geometry_coords;
    if (!coords?.length) return;
    const bounds = L.latLngBounds(coords.map(([lon, lat]) => [lat, lon]));
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [48, 48], maxZoom: 11 });
  }, [map, route]);
  return null;
}

function FocusSelectedRisk({ area }) {
  const map = useMap();
  useEffect(() => {
    if (!Number.isFinite(Number(area?.lat)) || !Number.isFinite(Number(area?.lon))) return;
    map.flyTo([Number(area.lat), Number(area.lon)], Math.max(map.getZoom(), 10), { duration: 0.6 });
  }, [area?.id, area?.lat, area?.lon, map]);
  return null;
}

function routeArrowIcon(coords, fraction) {
  const index = Math.max(1, Math.min(coords.length - 1, Math.floor((coords.length - 1) * fraction)));
  const [fromLon, fromLat] = coords[index - 1];
  const [toLon, toLat] = coords[index];
  const angle = Math.atan2(toLon - fromLon, toLat - fromLat) * (180 / Math.PI);
  return L.divIcon({
    className: 'route-direction-arrow',
    html: `<div style="transform: rotate(${angle}deg)">➤</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function shortPinName(name) {
  return String(name ?? '')
    .replace(/\b(Quick-Response|Relief Camp|Flood Shelter|Evacuation Center|Warehouse|Hub|Depot)\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim() || name;
}

function createMapPin({ name, icon, tone, moving = false, stack = 'center', offsetX = 0, offsetY = 0 }) {
  const movingClass = moving ? ' is-moving' : '';
  const transform = `translate(calc(-50% + ${offsetX}px), calc(-50% + ${offsetY}px))`;
  return L.divIcon({
    className: 'map-pin-wrap',
    html: `<div class="map-pin map-pin--${tone} map-pin--stack-${stack}${movingClass}" style="transform: ${transform}">
      <span class="map-pin-icon">${icon}</span>
      <span class="map-pin-label">${escapeHtml(name)}</span>
    </div>`,
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  });
}

const createWarehouseIcon = (name) =>
  createMapPin({ name: shortPinName(name), icon: '🏢', tone: 'warehouse', stack: 'top' });

const createCampIcon = (name) =>
  createMapPin({ name: shortPinName(name), icon: '⛺', tone: 'camp', stack: 'center' });

const createSelectedRiskIcon = () => L.divIcon({
  className: 'selected-risk-location-pin',
  html: '<svg width="42" height="52" viewBox="0 0 42 52" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><path d="M21 1C9.4 1 0 10.4 0 22c0 15.1 21 30 21 30s21-14.9 21-30C42 10.4 32.6 1 21 1Z" fill="#d93808" stroke="#fff" stroke-width="2"/><circle cx="21" cy="21" r="9" fill="#fff"/></svg>',
  iconSize: [42, 52],
  iconAnchor: [21, 51],
  popupAnchor: [0, -48],
});

function getTruckOffset(vehicles, vehicle) {
  const nearby = vehicles
    .filter((candidate) => {
      const latDelta = Number(candidate.lat) - Number(vehicle.lat);
      const lonDelta = Number(candidate.lon) - Number(vehicle.lon);
      return Math.hypot(latDelta, lonDelta) < 0.025;
    })
    .sort((a, b) => a.id - b.id);

  const index = Math.max(0, nearby.findIndex((candidate) => candidate.id === vehicle.id));
  const columns = Math.min(3, Math.max(1, nearby.length));
  const column = index % columns;
  const row = Math.floor(index / columns);

  return {
    offsetX: (column - (columns - 1) / 2) * 112,
    offsetY: 28 + row * 34,
  };
}

const createTruckIcon = (name, status, offset) =>
  createMapPin({
    name,
    icon: '🚚',
    tone: 'truck',
    stack: 'bottom',
    moving: status === 'IN_TRANSIT',
    ...offset,
  });

// Interactive Leaflet Map displaying live warehouses, camps, fleet trucks, danger zones, and active routes
export default function MapView({ warehouses = [], camps = [], vehicles = [], zones = [], orders = [], floodGeojson = null, selectedRiskArea = null, sites = [], oswcWarehouses = [], warehouseRiskRoute = null, showSatellite = true, showPrediction = true, showSites = true, onLocationSelect }) {
  // Center map around Odisha (Bhubaneswar - Cuttack - Puri - Paradeep corridor)
  const defaultCenter = [20.3, 85.8];

  return (
    <div className="relative z-0 isolate w-full h-full rounded-xl overflow-hidden border border-slate-800 shadow-2xl">
      <MapContainer
        center={defaultCenter}
        zoom={8}
        scrollWheelZoom={true}
        closePopupOnClick
        className="w-full h-full"
      >
        {/* OSM tiles — no API key. CSS inverts them so the dashboard stays dark. */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapClickHandler onLocationSelect={onLocationSelect} />
        <FitWarehouseBounds warehouses={oswcWarehouses} />
        <FitPreviewRoute route={warehouseRiskRoute} />
        <FocusSelectedRisk area={selectedRiskArea} />

        {showSatellite && floodGeojson && (
          <GeoJSON data={floodGeojson} pathOptions={{ color: '#2563eb', fillColor: '#3b82f6', fillOpacity: 0.28, weight: 2 }} />
        )}

        {showPrediction && selectedRiskArea && (() => {
          const risk = selectedRiskArea;
          const color = risk.level === 'CRITICAL' || risk.level === 'HIGH' ? '#dc2626'
            : risk.level === 'MODERATE' ? '#2563eb' : risk.level === 'LOW' ? '#16a34a' : '#64748b';
          const radiusKm = risk.level === 'CRITICAL' ? 8 : risk.level === 'HIGH' ? 6 : risk.level === 'MODERATE' ? 4 : 2.5;
          return <Circle center={[Number(risk.lat), Number(risk.lon)]} radius={radiusKm * 1000}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.14, opacity: 0.68, weight: 2 }}>
            <Popup><div className="text-slate-900 text-xs">
              <p className="font-bold">{risk.displayName || risk.name}</p>
              <p>Map priority: {risk.level}</p>
              {risk.glofas && <p>GloFAS: {risk.glofas.risk_level.replace('_', ' ')} · {risk.glofas.risk_pct}% index · discharge {risk.glofas.discharge_m3s ?? 'unavailable'} m³/s</p>}
              {risk.heuristicLevel && <p>Heuristic risk score: {risk.heuristicScore}/100 ({risk.heuristicLevel})</p>}
              {risk.explanation?.map((line) => <p key={line} className="mt-1">{line}</p>)}
              <p className="mt-1">Planning influence zone, not measured flood extent.</p>
            </div></Popup>
          </Circle>;
        })()}

        {showSites && sites.map((site) => (
          <Marker key={`site-${site.rank}-${site.lat}`} position={[site.lat, site.lon]} icon={L.divIcon({ className: 'site-rank-pin', html: `<div>${site.rank}</div>`, iconSize: [26, 26], iconAnchor: [13, 13] })}>
            <Popup><div className="text-slate-900 text-xs"><p className="font-bold">#{site.rank} {site.name}</p><p>Score: {site.score}/100</p><p className="mt-1">{site.reason}</p>{site.osm_link && <a href={site.osm_link} target="_blank" rel="noreferrer" className="text-blue-600">OpenStreetMap</a>}</div></Popup>
          </Marker>
        ))}

        {warehouseRiskRoute?.geometry_coords?.length > 1 && <>
          <Polyline
            positions={warehouseRiskRoute.geometry_coords.map(([lon, lat]) => [lat, lon])}
            pathOptions={{ color: '#0284c7', weight: 6, opacity: 0.95 }}
          >
            <Popup><div className="text-slate-900 text-xs"><strong>Supply route</strong><br />{warehouseRiskRoute.warehouse.zone_name} warehouse to {warehouseRiskRoute.risk.name}<br />{warehouseRiskRoute.distance_km} km · {warehouseRiskRoute.duration_min} min · {warehouseRiskRoute.routing}</div></Popup>
          </Polyline>
          <CircleMarker center={[warehouseRiskRoute.origin.lat, warehouseRiskRoute.origin.lon]} radius={9} pathOptions={{ color: '#047857', fillColor: '#10b981', fillOpacity: 1, weight: 3 }}>
            <Popup><strong>{warehouseRiskRoute.warehouse.zone_name} warehouse</strong><br />Route origin</Popup>
          </CircleMarker>
          <CircleMarker center={[warehouseRiskRoute.destination.lat, warehouseRiskRoute.destination.lon]} radius={10} pathOptions={{ color: '#b91c1c', fillColor: '#ef4444', fillOpacity: 1, weight: 3 }}>
            <Popup><strong>{warehouseRiskRoute.risk.name}</strong><br />{warehouseRiskRoute.risk.level} risk area · route destination</Popup>
          </CircleMarker>
        </>}

        {selectedRiskArea && <Marker
          position={[Number(selectedRiskArea.lat), Number(selectedRiskArea.lon)]}
          icon={createSelectedRiskIcon()}
          zIndexOffset={1500}
        >
          <Popup><div className="text-slate-900 text-xs"><strong>{selectedRiskArea.displayName || selectedRiskArea.name}</strong><br />Selected {selectedRiskArea.level} risk area · {selectedRiskArea.score}/100</div></Popup>
        </Marker>}

        {/* 1. Warehouses */}
        {warehouses.map((wh) => (
          <Marker key={`wh-${wh.id}`} position={[wh.lat, wh.lon]} icon={createWarehouseIcon(wh.name)} zIndexOffset={300}>
            <Popup className="custom-popup" autoClose closeOnClick>
              <div className="text-slate-900 p-1">
                <p className="font-bold text-sm text-blue-700">🏢 {wh.name}</p>
                <p className="text-xs text-slate-600">Reliability Score: {(wh.reliability * 100).toFixed(0)}%</p>
                <div className="mt-2 text-xs border-t pt-1 font-mono">
                  <p className="font-semibold text-slate-800">Inventory on hand:</p>
                  {wh.inventory?.map((inv) => (
                    <div key={inv.id} className="flex justify-between text-slate-600">
                      <span>{inv.item}:</span>
                      <span className="font-bold">{inv.quantity}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* OSWC warehouse locations are shown separately from dispatch inventory. */}
        {Object.values(oswcWarehouses.reduce((groups, item) => {
          const key = `${Number(item.lat).toFixed(6)},${Number(item.lon).toFixed(6)}`;
          (groups[key] ||= []).push(item);
          return groups;
        }, {})).map((group) => {
          const first = group[0];
          return <Marker key={`oswc-${first.serial_no}`} position={[first.lat, first.lon]}
            icon={L.divIcon({ className: 'oswc-warehouse-pin', html: `<div>W${group.map((item) => item.serial_no).join('/')}</div>`, iconSize: [38, 30], iconAnchor: [19, 15] })}
            zIndexOffset={450}>
            <Popup><div className="text-slate-900 text-xs max-w-64">
              <p className="font-bold text-emerald-800">OSWC warehouse reference location</p>
              {group.map((item) => <div key={item.serial_no} className="mt-2 border-t pt-2">
                <p className="font-semibold">Warehouse #{item.serial_no} · {item.zone_name}</p>
                {item.warehouse_incharge && <p>In-charge: {item.warehouse_incharge}</p>}
                <p>Total capacity: {Number(item.total_capacity_mt).toLocaleString()} MT · Vacant: {Number(item.vacant_space_mt).toLocaleString()} MT</p>
                <p className="text-slate-500">Location from supplied Google Maps link ({item.coordinate_status})</p>
                {item.google_maps_url && <a href={item.google_maps_url} target="_blank" rel="noreferrer" className="text-blue-700 underline">Verify in Google Maps</a>}
              </div>)}
              <p className="mt-2 text-amber-700">Reported capacity is reference information only; availability is not confirmed.</p>
            </div></Popup>
          </Marker>;
        })}

        {/* 2. Relief Camps */}
        {camps.map((camp) => (
          <Marker key={`camp-${camp.id}`} position={[camp.lat, camp.lon]} icon={createCampIcon(camp.name)} zIndexOffset={200}>
            <Popup className="custom-popup" autoClose closeOnClick>
              <div className="text-slate-900 p-1">
                <p className="font-bold text-sm text-amber-700">⛺ {camp.name}</p>
                <p className="text-xs text-slate-600">Population Sheltered: {camp.population} people</p>
                <p className="text-[11px] text-slate-500 mt-1">Coords: {camp.lat.toFixed(4)}, {camp.lon.toFixed(4)}</p>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* 3. Fleet Vehicles */}
        {false && vehicles.map((v) => (
          <Marker
            key={`v-${v.id}`}
            position={[v.lat, v.lon]}
            icon={createTruckIcon(v.name, v.status, getTruckOffset(vehicles, v))}
            // Keep truck chips above warehouse/camp markers when coordinates overlap.
            zIndexOffset={1000}
            riseOnHover
          >
            <Popup className="custom-popup" autoClose closeOnClick>
              <div className="text-slate-900 p-1">
                <p className="font-bold text-sm text-emerald-700">🚚 {v.name}</p>
                <p className="text-xs font-semibold">Status: <span className={v.status === 'IN_TRANSIT' ? 'text-emerald-600 font-bold' : 'text-slate-600'}>{v.status}</span></p>
                <p className="text-xs text-slate-600">Capacity: {v.capacity} units</p>
                {v.current_order_id && <p className="text-xs text-sky-700 font-mono mt-1">Carrying Order #{v.current_order_id}</p>}
              </div>
            </Popup>
          </Marker>
        ))}

        {/* 4. Active Danger / Flood Zones */}
        {zones.filter((z) => z.active && selectedRiskArea?.id === `zone-${z.id}`).map((zone) => (
          <Circle
            key={`zone-${zone.id}`}
            center={[zone.center_lat, zone.center_lon]}
            radius={zone.radius_km * 1000} // meters
            pathOptions={{
              color: '#f43f5e',
              fillColor: '#e11d48',
              fillOpacity: 0.3,
              weight: 2,
            }}
          >
            <Popup className="custom-popup">
              <div className="text-slate-900 p-1">
                <p className="font-bold text-sm text-rose-700">⚠️ {zone.name}</p>
                <p className="text-xs font-semibold text-slate-700">Severity: Level {zone.severity}/5</p>
                <p className="text-xs text-slate-600">Radius: {zone.radius_km} km</p>
                <p className="text-[11px] text-slate-500 uppercase font-mono mt-1">Source: {zone.source}</p>
              </div>
            </Popup>
          </Circle>
        ))}

        {/* 5. Active Order Routes */}
        {orders
          .filter((o) => o.status === 'IN_TRANSIT' || o.status === 'PENDING_APPROVAL')
          .map((order) => {
            if (!order.route_geojson) return null;
            try {
              const geo = JSON.parse(order.route_geojson);
              // GeoJSON is [lon, lat], Leaflet Polyline expects [lat, lon]
              const latLngs = (geo.coordinates || []).map((pt) => [pt[1], pt[0]]);
              const isRerouted = order.reroute_count > 0;

              return (
                <Polyline
                  key={`route-${order.id}`}
                  positions={latLngs}
                  pathOptions={{
                    color: isRerouted ? '#c084fc' : '#38bdf8',
                    weight: isRerouted ? 5 : 4,
                    dashArray: isRerouted ? '8, 8' : undefined,
                    opacity: 0.85,
                  }}
                >
                  <Popup className="custom-popup">
                    <div className="text-slate-900 p-1 text-xs">
                      <p className="font-bold text-sky-800">Order #{order.id}: {order.quantity} {order.item}</p>
                      <p>Distance: {order.distance_km} km | ETA: {order.eta_minutes} mins</p>
                      {isRerouted && <p className="text-purple-700 font-bold mt-1">⚡ Dynamically Rerouted ({order.reroute_count}x)</p>}
                    </div>
                  </Popup>
                </Polyline>
              );
            } catch (e) {
              return null;
            }
          })}
      </MapContainer>

      {/* Map Legend Overlay */}
      {false && <div className="absolute bottom-3 left-3 z-[1000] bg-white/90 backdrop-blur-md border border-slate-200 rounded-xl p-3 text-[11px] text-slate-700 space-y-1.5 shadow-md pointer-events-none">
        {showPrediction && <>
          <div className="font-bold text-slate-800">Heuristic risk score</div>
          <div className="flex items-center space-x-2"><span className="w-2.5 h-2.5 rounded-full bg-red-600 inline-block" /><span>High / Critical — prioritize first</span></div>
          <div className="flex items-center space-x-2"><span className="w-2.5 h-2.5 rounded-full bg-blue-600 inline-block" /><span>Moderate</span></div>
          <div className="flex items-center space-x-2"><span className="w-2.5 h-2.5 rounded-full bg-green-600 inline-block" /><span>Low</span></div>
          <div className="flex items-center space-x-2"><span className="w-2.5 h-2.5 rounded-full bg-slate-500 inline-block" /><span>Unknown — signals unavailable</span></div>
          <div className="max-w-52 text-[10px] text-slate-500">Planning zones are not flood boundaries. Sentinel-1 shows observed water; risk is heuristic.</div>
        </>}
        <div className="flex items-center space-x-2">
          <span>🏢</span> <span className="font-medium">Regional Warehouse</span>
        </div>
        <div className="flex items-center space-x-2">
          <span>⛺</span> <span className="font-medium">Relief Camp</span>
        </div>
        <div className="flex items-center space-x-2">
          {false && <><span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block shadow-sm"></span> <span className="font-medium">Delivery Truck</span></>}
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500 inline-block shadow-sm"></span> <span className="font-medium">Active Danger Zone</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-4 h-1 bg-sky-500 rounded-full inline-block"></span> <span className="font-medium">Safe Route</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-4 h-1 border-t-2 border-dashed border-purple-500 inline-block"></span> <span className="font-medium">Rerouted Path</span>
        </div>
      </div>}
    </div>
  );
}

