import React, { useEffect, useState } from 'react';
import { fetchWarehouseSites } from '../api';

export default function WarehouseSitesPanel({ onSites }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { fetchWarehouseSites({ lat: 20.4625, lon: 85.8828, radius_km: 40, limit: 5 }).then((result) => { setData(result); onSites?.(result.sites || []); }).catch((e) => setError(e.message)); }, []);
  return <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-4"><div className="flex items-center justify-between"><div><h3 className="font-bold text-sm text-slate-800">Recommended Warehouse Sites</h3><p className="text-[11px] text-slate-400">Decision support — human verification required</p></div><span className="text-[10px] px-2 py-1 rounded-full bg-violet-50 text-violet-700">SUPPORT</span></div>{error && <p className="text-xs text-slate-400 mt-3">Sites unavailable: {error}</p>}{data?.sites?.map((site) => <div key={`${site.rank}-${site.lat}`} className="mt-2 p-2 rounded-lg bg-slate-50 border border-slate-100"><div className="flex justify-between gap-2"><p className="text-xs font-semibold text-slate-800">#{site.rank} {site.name}</p><p className="text-xs font-bold text-violet-700">{site.score}/100</p></div><p className="text-[10px] text-slate-500 mt-1">{site.reason}</p></div>)}</div>;
}
