import React, { useState, useEffect } from 'react';
import { fetchFloodRisk } from '../api';
import { Droplets, RefreshCw, WifiOff, AlertTriangle } from 'lucide-react';

const RISK_CONFIG = {
  NORMAL:     { label: 'Normal',     bg: 'bg-green-100',  text: 'text-green-700',  bar: 'bg-green-500'  },
  WARNING:    { label: 'Warning',    bg: 'bg-amber-100',  text: 'text-amber-700',  bar: 'bg-amber-500'  },
  DANGER:     { label: 'Danger',     bg: 'bg-orange-100', text: 'text-orange-700', bar: 'bg-orange-500' },
  HIGH_FLOOD: { label: 'High Flood', bg: 'bg-red-100',    text: 'text-red-700',    bar: 'bg-red-500'    },
  UNKNOWN:    { label: 'Offline',    bg: 'bg-slate-100',  text: 'text-slate-500',  bar: 'bg-slate-300'  },
};

function RiskBadge({ level }) {
  const cfg = RISK_CONFIG[level] ?? RISK_CONFIG.UNKNOWN;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${cfg.bg} ${cfg.text}`}>
      {cfg.label}
    </span>
  );
}

function DischargeBar({ pct, level }) {
  const cfg = RISK_CONFIG[level] ?? RISK_CONFIG.UNKNOWN;
  return (
    <div className="w-full bg-gray-100 rounded-full h-1.5 mt-1.5">
      <div
        className={`h-1.5 rounded-full transition-all duration-700 ${cfg.bar}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function PointCard({ point }) {
  const discharge = point.discharge_m3s != null
    ? `${point.discharge_m3s.toLocaleString()} m³/s`
    : '—';
  const max = point.discharge_max_m3s != null
    ? `↑ ${point.discharge_max_m3s.toLocaleString()}`
    : '';

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-3 flex flex-col gap-1.5 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-gray-800 text-sm truncate">{point.name}</span>
        <RiskBadge level={point.risk_level} />
      </div>

      <div className="flex items-baseline gap-1.5">
        <span className="text-lg font-bold text-gray-900">{discharge}</span>
        {max && <span className="text-xs text-gray-400">{max}</span>}
      </div>

      <DischargeBar pct={point.risk_pct} level={point.risk_level} />

      {point.error && (
        <p className="text-xs text-slate-400 truncate" title={point.error}>Offline</p>
      )}
    </div>
  );
}

export default function FloodRiskPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [offline, setOffline] = useState(false);

  const load = async () => {
    try {
      const result = await fetchFloodRisk();
      setData(result);
      setLastUpdated(new Date());
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const highestRisk = data?.find(p => p.risk_level !== 'NORMAL' && p.risk_level !== 'UNKNOWN');
  const alertCount = data?.filter(p => ['DANGER', 'HIGH_FLOOD'].includes(p.risk_level)).length ?? 0;

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
            <Droplets size={16} className="text-blue-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-800 text-sm">GloFAS Flood Risk</h3>
            <p className="text-xs text-gray-400">
              {offline ? 'Offline' : lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Loading…'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {alertCount > 0 && (
            <span className="flex items-center gap-1 text-xs font-semibold text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
              <AlertTriangle size={11} />
              {alertCount} alert{alertCount > 1 ? 's' : ''}
            </span>
          )}
          <button
            onClick={load}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            title="Refresh"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Offline state */}
      {offline && (
        <div className="flex flex-col items-center justify-center py-6 gap-2 text-slate-400">
          <WifiOff size={24} />
          <p className="text-sm">GloFAS data unavailable</p>
          <p className="text-xs">Check internet connection</p>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !offline && (
        <div className="grid grid-cols-2 gap-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-gray-50 rounded-xl h-20 animate-pulse" />
          ))}
        </div>
      )}

      {/* Data grid */}
      {!loading && !offline && data && (
        <>
          <div className="grid grid-cols-2 gap-2">
            {data.map(point => (
              <PointCard key={point.name} point={point} />
            ))}
          </div>
          <p className="text-xs text-gray-300 text-right mt-2">
            Source: GloFAS · Open-Meteo · Live
          </p>
        </>
      )}
    </div>
  );
}

