import React, { useEffect, useState } from 'react';
import { fetchSatelliteFlood, refreshSatellite } from '../api';

export default function SatelliteFloodPanel({ onData }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const load = async () => { try { const result = await fetchSatelliteFlood(); setData(result); onData?.(result); setError(null); } catch (e) { setError(e.message); } finally { setLoading(false); } };
  useEffect(() => { load(); const id = setInterval(load, 60000); return () => clearInterval(id); }, []);
  const queue = async () => { setRefreshing(true); try { await refreshSatellite(); } catch (e) { setError(e.message); } finally { setRefreshing(false); } };
  return <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-4">
    <div className="flex items-center justify-between"><div><h3 className="font-bold text-sm text-slate-800">Satellite Flood Status</h3><p className="text-[11px] text-slate-400">Observed Sentinel-1 water extent, not a prediction</p></div><button onClick={queue} disabled={refreshing} className="text-xs px-2 py-1 rounded-lg bg-blue-50 text-blue-700 border border-blue-200">{refreshing ? 'Queued…' : 'Refresh'}</button></div>
    {loading && <p className="text-xs text-slate-400 mt-3">Loading…</p>}
    {error && <p className="text-xs text-rose-600 mt-3">{error}</p>}
    {data && <div className="grid grid-cols-3 gap-2 mt-3 text-xs"><div><p className="text-slate-400">Mode</p><p className={`font-bold ${data.mode === 'SAMPLE' ? 'text-amber-600' : 'text-emerald-600'}`}>{data.mode}</p></div><div><p className="text-slate-400">Flooded</p><p className="font-bold">{data.flooded_km2} km²</p></div><div><p className="text-slate-400">Age</p><p className="font-bold">{data.data_age_hours ?? '—'} h</p></div></div>}
    {data?.mode === 'SAMPLE' && <p className="text-[10px] text-amber-700 mt-2 font-semibold">SAMPLE badge: offline demonstration data.</p>}
  </div>;
}
