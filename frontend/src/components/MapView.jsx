import React from 'react';
import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline, useMapEvents } from 'react-leaflet';
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
export default function MapView({ warehouses = [], camps = [], vehicles = [], zones = [], orders = [], onLocationSelect }) {
  // Center map around Odisha (Bhubaneswar - Cuttack - Puri - Paradeep corridor)
  const defaultCenter = [20.3, 85.8];

  return (
    <div className="w-full h-full relative rounded-xl overflow-hidden border border-slate-800 shadow-2xl">
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
        {vehicles.map((v) => (
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
        {zones.filter((z) => z.active).map((zone) => (
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
      <div className="absolute bottom-3 left-3 z-[1000] bg-white/90 backdrop-blur-md border border-slate-200 rounded-xl p-3 text-[11px] text-slate-700 space-y-1.5 shadow-md pointer-events-none">
        <div className="flex items-center space-x-2">
          <span>🏢</span> <span className="font-medium">Regional Warehouse</span>
        </div>
        <div className="flex items-center space-x-2">
          <span>⛺</span> <span className="font-medium">Relief Camp</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block shadow-sm"></span> <span className="font-medium">Delivery Truck</span>
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
      </div>
    </div>
  );
}

