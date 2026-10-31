import React, { useState } from 'react';
import { Flame, RefreshCcw, Trash2, ArrowUpRight, Zap, Radio, Info } from 'lucide-react';

// Control panel allowing the hackathon presenter to trigger disaster scenarios and manage the swarm
export default function ControlPanel({
  selectedCoords,
  zones = [],
  autoDispatch,
  onSimulateFlood,
  onGrowZone,
  onClearZones,
  onResetDemo,
  onRunCycle,
  onToggleAutoDispatch,
}) {
  // Preset disaster target locations in Odisha (cyclone & Mahanadi flood delta)
  const presets = [
    { name: 'Mahanadi Basin', lat: 20.4625, lon: 85.8828 },
    { name: 'Puri Cyclone', lat: 19.8135, lon: 85.8312 },
    { name: 'Paradeep Delta', lat: 20.3160, lon: 86.6114 },
  ];

  const [lat, setLat] = useState(selectedCoords?.lat || 20.4625);
  const [lon, setLon] = useState(selectedCoords?.lon || 85.8828);
  const [radiusKm, setRadiusKm] = useState(3.5);
  const [severity, setSeverity] = useState(4);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState('Mahanadi Basin');

  // Sync coords if user clicked on map
  React.useEffect(() => {
    if (selectedCoords) {
      setLat(Number(selectedCoords.lat.toFixed(4)));
      setLon(Number(selectedCoords.lon.toFixed(4)));
    }
  }, [selectedCoords]);

  const handleFloodSubmit = async (e) => {
    e?.preventDefault();
    setIsLoading(true);
    try {
      await onSimulateFlood({
        name: `Flood Zone (Severity ${severity})`,
        lat: Number(lat),
        lon: Number(lon),
        radius_km: Number(radiusKm),
        severity: Number(severity),
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleGrowActive = async () => {
    const activeZone = zones.find((z) => z.active);
    if (!activeZone) return;
    setIsLoading(true);
    try {
      await onGrowZone({ zone_id: activeZone.id, extra_km: 2.0 });
    } finally {
      setIsLoading(false);
    }
  };

  const activeZone = zones.find((z) => z.active);

  return (
    <div className="w-full p-5 space-y-4 text-slate-800">
      {/* Top Header & Autonomous Mode Toggle */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div className="flex items-center space-x-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
            <Zap className="w-4 h-4" />
          </span>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">Swarm Controls</h3>
            <p className="text-[11px] text-slate-500">Configure emergency & trigger swarm</p>
          </div>
        </div>

        {/* Auto Dispatch Toggle */}
        <label className="flex items-center space-x-2 cursor-pointer text-xs">
          <span className="text-slate-600 font-medium">Auto-dispatch</span>
          <div
            onClick={() => onToggleAutoDispatch(!autoDispatch)}
            role="switch"
            aria-checked={autoDispatch}
            className={`w-9 h-5 flex items-center rounded-full p-0.5 transition-colors ${
              autoDispatch ? 'bg-emerald-500' : 'bg-slate-300'
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow transform transition-transform ${
                autoDispatch ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </div>
        </label>
      </div>

      {/* Preset Buttons */}
      <div>
        <p className="text-xs text-slate-900 font-bold uppercase tracking-wide">1. Choose a flood location</p>
        <p className="text-[11px] text-slate-500 mt-0.5 mb-2">Pick a preset or click directly on the map.</p>
        <div className="grid grid-cols-3 gap-2">
          {presets.map((p, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setLat(p.lat);
                setLon(p.lon);
                setSelectedPreset(p.name);
              }}
              className={`px-2 py-2 rounded-lg border text-xs font-medium transition text-center truncate ${
                selectedPreset === p.name
                  ? 'bg-blue-100 border-blue-500 text-blue-950 shadow-sm ring-1 ring-blue-300'
                  : 'bg-slate-50 hover:bg-blue-50/60 border-slate-200 text-slate-700'
              }`}
            >
              📍 {p.name}
            </button>
          ))}
        </div>
      </div>

      {/* Sliders for Radius and Severity */}
      <div className="space-y-4 text-xs">
        <div>
          <div className="flex justify-between text-slate-600 mb-1">
            <span className="font-semibold flex items-center gap-1.5">
              2. Flood area size
              <span className="relative group inline-flex">
                <Info className="w-3.5 h-3.5 text-slate-400 hover:text-blue-600 cursor-help" />
                <span className="pointer-events-none absolute left-5 top-1/2 z-20 hidden w-52 -translate-y-1/2 rounded-md bg-slate-900 px-2.5 py-2 text-[11px] font-normal leading-snug text-white shadow-lg group-hover:block">
                  Controls how large the simulated flood area will be on the map.
                </span>
              </span>
            </span>
            <span className="font-mono text-blue-700 font-bold">{radiusKm} km</span>
          </div>
          <input
            type="range"
            min="1.0"
            max="5.0"
            step="0.5"
            value={radiusKm}
            onChange={(e) => setRadiusKm(e.target.value)}
            className="w-full accent-rose-500"
          />
        </div>
        <div>
          <div className="flex justify-between text-slate-600 mb-1">
            <span className="font-semibold flex items-center gap-1.5">
              3. Emergency severity
              <span className="relative group inline-flex">
                <Info className="w-3.5 h-3.5 text-slate-400 hover:text-blue-600 cursor-help" />
                <span className="pointer-events-none absolute left-5 top-1/2 z-20 hidden w-56 -translate-y-1/2 rounded-md bg-slate-900 px-2.5 py-2 text-[11px] font-normal leading-snug text-white shadow-lg group-hover:block">
                  Sets the urgency from Level 1 (low impact) to Level 5 (critical emergency).
                </span>
              </span>
            </span>
            <span className="font-mono text-rose-600 font-bold">Level {severity}/5</span>
          </div>
          <input
            type="range"
            min="1"
            max="5"
            step="1"
            value={severity}
            onChange={(e) => setSeverity(e.target.value)}
            className="w-full accent-rose-500"
          />
        </div>
      </div>

      {/* Primary Action Buttons */}
      <div>
        <p className="text-xs text-slate-900 font-bold uppercase tracking-wide mb-2">4. Start the response</p>
        <div className="grid grid-cols-2 gap-2">
        <button
          onClick={handleFloodSubmit}
          disabled={isLoading}
          className="px-3 py-2.5 bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white rounded-lg font-bold text-xs shadow-md transition flex items-center justify-center space-x-1.5 disabled:opacity-60"
        >
          <Flame className="w-4 h-4" />
          <span>Simulate Flood</span>
        </button>

        <button
          onClick={handleGrowActive}
          disabled={!activeZone || isLoading}
          className={`px-3 py-2 rounded-lg font-bold text-xs shadow-lg transition flex items-center justify-center space-x-1.5 ${
            activeZone
              ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
              : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
          }`}
          title="Enlarge active danger zone by +2km to trigger dynamic rerouting"
        >
          <ArrowUpRight className="w-4 h-4" />
          <span>Grow Zone (+2km)</span>
        </button>
        </div>
      </div>

      {/* Utility Actions */}
      <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-200">
        <button
          onClick={onRunCycle}
          className="px-2 py-2 bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-700 rounded-lg text-xs font-medium transition flex items-center justify-center space-x-1"
          title="Manually trigger an immediate swarm cycle"
        >
          <Radio className="w-3.5 h-3.5" />
          <span>Run Cycle</span>
        </button>

        <button
          onClick={onClearZones}
          className="px-2 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-700 rounded-lg text-xs font-medium transition flex items-center justify-center space-x-1 cursor-pointer"
          title="Deactivate simulated danger zones"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span>Clear Zones</span>
        </button>

        <button
          onClick={onResetDemo}
          className="px-2 py-2 bg-slate-50 hover:bg-slate-100 border border-slate-200 text-slate-700 rounded-lg text-xs font-medium transition flex items-center justify-center space-x-1"
          title="Reset database to initial state"
        >
          <RefreshCcw className="w-3.5 h-3.5" />
          <span>Reset Demo</span>
        </button>
      </div>
    </div>
  );
}

