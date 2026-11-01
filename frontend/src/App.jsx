import React, { useState, useEffect } from 'react';
import {
  fetchState,
  simulateFlood,
  simulateGrow,
  simulateClear,
  simulateReset,
  approveOrder,
  cancelOrder,
  setAutoDispatch,
  runCycleNow,
  fetchRoutingStatus,
  fetchFloodPrediction,
  fetchOSWCWarehouses,
} from './api';

import MapView from './components/MapView';
import KpiCards from './components/KpiCards';
import AgentLog from './components/AgentLog';
import OrdersTable from './components/OrdersTable';
import ControlPanel from './components/ControlPanel';
import FloodRiskPanel from './components/FloodRiskPanel';
import SatelliteFloodPanel from './components/SatelliteFloodPanel';
import WarehouseSitesPanel from './components/WarehouseSitesPanel';
import RoutePlanner from './components/RoutePlanner';
import { Wifi, WifiOff, Zap, Info, X, ShieldAlert } from 'lucide-react';

export default function App() {
  const [state, setState] = useState(null);
  const [selectedCoords, setSelectedCoords] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [showAboutModal, setShowAboutModal] = useState(false);
  const [activeTab, setActiveTab] = useState('orders'); // 'orders' | 'log'
  const [routingStatus, setRoutingStatus] = useState(null);
  const [satellite, setSatellite] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [sites, setSites] = useState([]);
  const [oswcWarehouses, setOswcWarehouses] = useState({ warehouses: [], total_rows: 0, located_count: 0, unlocated_count: 0 });
  const [warehouseRiskRoute, setWarehouseRiskRoute] = useState(null);

  const loadState = async () => {
    try {
      const data = await fetchState();
      setState(data);
      setErrorMsg(null);
    } catch (err) {
      setErrorMsg(err.message);
    }
  };

  useEffect(() => {
    loadState();
    const stateInterval = setInterval(loadState, 3000);
    return () => clearInterval(stateInterval);
  }, []);

  useEffect(() => { fetchFloodPrediction().then(setPredictions).catch(() => setPredictions([])); const id = setInterval(() => fetchFloodPrediction().then(setPredictions).catch(() => {}), 60000); return () => clearInterval(id); }, []);

  useEffect(() => { fetchOSWCWarehouses().then(setOswcWarehouses).catch(() => {}); }, []);

  useEffect(() => {
    const loadRoutingStatus = async () => {
      try {
        setRoutingStatus(await fetchRoutingStatus());
      } catch {
        setRoutingStatus({ available: false, reason: 'The routing status endpoint could not be reached.' });
      }
    };
    loadRoutingStatus();
    const routingInterval = setInterval(loadRoutingStatus, 15000);
    return () => clearInterval(routingInterval);
  }, []);

  const handleSimulateFlood = async (payload) => { await simulateFlood(payload); await loadState(); };
  const handleGrowZone = async (payload) => { await simulateGrow(payload); await loadState(); };
  const handleClearZones = async () => { await simulateClear(); await loadState(); };
  const handleResetDemo = async () => { await simulateReset(); await loadState(); };
  const handleRunCycle = async () => {
    setIsRefreshing(true);
    try { await runCycleNow(); await loadState(); } finally { setIsRefreshing(false); }
  };
  const handleApproveOrder = async (id) => { await approveOrder(id); await loadState(); };
  const handleCancelOrder = async (id) => { await cancelOrder(id); await loadState(); };
  const handleToggleAutoDispatch = async (v) => { await setAutoDispatch(v); await loadState(); };
  const handleMapLocationSelect = (lat, lon) => setSelectedCoords({ lat, lon });

  const pendingCount = (state?.orders || []).filter(o => o.status === 'PENDING_APPROVAL').length;
  const hasError = !!errorMsg;
  const isAiMode = state && !state.kpis?.fallback_mode;

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: '#a7a6a6', fontFamily: 'Inter, sans-serif' }}>

      {/* ── NAVBAR ─────────────────────────────────────────────────── */}
      <header style={{ backgroundColor: '#ffffff', borderBottom: '3px solid #000000ff' }}
        className="sticky top-0 z-[2000] isolate px-6 py-3 flex items-center justify-between shadow-sm">

        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center text-white font-black text-sm border-[2px] border-black"
            style={{ background: 'linear-gradient(135deg, #c6bcbcff, #e3dadaff)' }}>
            🚨
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base" style={{ color: '#222' }}>ResQChain</span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-[5px] text-white"
                style={{ background: '#ff5a5f' }}>SWARM</span>
            </div>
            <p className="text-xs" style={{ color: '#767676' }}>Autonomous Emergency Logistics</p>
          </div>
        </div>

        {/* Nav Right */}
        <div className="flex items-center gap-2">
          {/* Live Loop */}
          <div className="hidden sm:flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-[9px] text-bold"
            style={{ backgroundColor: '#f0fdf4', color: '#027d2fff', border: '2px solid #000201ff' }}>
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
                style={{ backgroundColor: '#000000ff' }} />
              <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: '#16a34a' }} />
            </span>
            <span className="font-medium">Live · 10s cycle</span>
          </div>

          {/* AI / Fallback badge */}
          {state && (
            <div className="hidden sm:flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-[9px]"
              style={isAiMode
                ? { backgroundColor: '#eff6ff', color: '#2563eb', border: '2px solid #000000ff' }
                : { backgroundColor: '#fffbeb', color: '#d97706', border: '2px solid #000000ff' }}>
              <Zap className="w-3 h-3" />
              <span className="font-medium">{isAiMode ? 'Gemini AI' : 'Heuristic Mode'}</span>
            </div>
          )}

          {/* Connection */}
          <div className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-[9px]"
            style={hasError
              ? { backgroundColor: '#fef2f2', color: '#dc2626', border: '2px solid #000000ff' }
              : { backgroundColor: '#f0fdf4', color: '#16a34a', border: '2px solid #000000ff' }}>
            {hasError ? <WifiOff className="w-3 h-3" /> : <Wifi className="w-3 h-3" />}
            <span className="font-medium">{hasError ? 'Offline' : 'Connected'}</span>
          </div>

          {/* OSRM road-routing status with hover explanation */}
          {routingStatus && (
            <div className="relative group hidden md:flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-[9px]"
              style={routingStatus.available
                ? { backgroundColor: '#f0fdf4', color: '#15803d', border: '2px solid #000000ff' }
                : { backgroundColor: '#fff7ed', color: '#c2410c', border: '2px solid #000000ff' }}>
              <span className={`h-2 w-2 rounded-full ${routingStatus.available ? 'bg-green-500' : 'bg-orange-500'}`} />
              <span className="font-medium">OSRM {routingStatus.available ? 'Available' : 'Offline'}</span>
              <Info className="w-3 h-3 cursor-help" />
              <div className="pointer-events-none absolute right-0 top-full z-50 mt-2 hidden w-72 rounded-lg bg-slate-900 px-3 py-2 text-[11px] leading-relaxed text-white shadow-xl group-hover:block">
                <p className="font-semibold">Road-routing service</p>
                <p className="mt-1 text-slate-300">{routingStatus.reason}</p>
                {!routingStatus.available && <p className="mt-1 text-amber-300">The app will use its local safe-road fallback until OSRM is reachable.</p>}
              </div>
            </div>
          )}

          {/* About */}
          <button onClick={() => setShowAboutModal(true)}
            className="p-2 rounded-full transition"
            style={{ backgroundColor: '#f7f7f7', border: '2px solid #000000ff', color: '#525050ff' }}
            onMouseOver={e => e.currentTarget.style.backgroundColor = '#ebebeb'}
            onMouseOut={e => e.currentTarget.style.backgroundColor = '#f7f7f7'}
            title="About this system">
            <Info className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* ── MAIN CONTENT ───────────────────────────────────────────── */}
      <main className="flex-1 p-4 lg:p-6 grid grid-cols-1 lg:grid-cols-12 gap-5 max-w-[1600px] mx-auto w-full">

        {/* LEFT: Map + Control Panel */}
        <div className="lg:col-span-7 flex flex-col gap-5">
          {/* Map Card */}
          <div className="rounded-2xl overflow-hidden shadow-sm border border-slate-200/80 bg-white min-h-[460px]">
            <div className="px-5 py-3 flex items-center justify-between border-b border-slate-100">
              <div>
                <h2 className="font-bold text-sm text-slate-800">Live Situation Map</h2>
                <p className="text-xs text-slate-400 mt-0.5">Odisha Disaster Corridor · Click map to set flood location</p>
              </div>
              <div className="flex gap-2 text-[11px]">
                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full border border-blue-200 bg-blue-50 text-blue-700 font-medium">🏭 Warehouses</span>
                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full border border-amber-200 bg-amber-50 text-amber-700 font-medium">⛺ Camps</span>
                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full border border-emerald-200 bg-emerald-50 text-emerald-700 font-medium">🚛 Trucks</span>
              </div>
            </div>
            <div style={{ height: 420 }}>
              <MapView
                warehouses={state?.warehouses || []}
                camps={state?.camps || []}
                vehicles={state?.vehicles || []}
                zones={state?.zones || []}
                orders={state?.orders || []}
                floodGeojson={satellite?.polygons}
                predictions={predictions}
                sites={sites}
                oswcWarehouses={oswcWarehouses.warehouses}
                warehouseRiskRoute={warehouseRiskRoute}
                onLocationSelect={handleMapLocationSelect}
              />
            </div>
          </div>

          <RoutePlanner
            predictions={predictions}
            zones={state?.zones || []}
            warehouses={oswcWarehouses.warehouses}
            onRouteChange={setWarehouseRiskRoute}
          />

          {/* Control Panel Card */}
          <div className="rounded-2xl shadow-sm border border-slate-200/80 bg-white overflow-hidden">
            <ControlPanel
              selectedCoords={selectedCoords}
              zones={state?.zones || []}
              autoDispatch={state?.kpis?.auto_dispatch || false}
              onSimulateFlood={handleSimulateFlood}
              onGrowZone={handleGrowZone}
              onClearZones={handleClearZones}
              onResetDemo={handleResetDemo}
              onRunCycle={handleRunCycle}
              onToggleAutoDispatch={handleToggleAutoDispatch}
            />
          </div>
        </div>

        {/* RIGHT: KPIs + Tabs for Orders/Log */}
        <div className="lg:col-span-5 flex flex-col gap-5">
          {/* KPI Cards */}
          <KpiCards kpis={state?.kpis} />

          {/* GloFAS Live Flood Risk Panel */}
          <FloodRiskPanel />
          <SatelliteFloodPanel onData={setSatellite} />
          <WarehouseSitesPanel onSites={setSites} />

          {/* Tabbed Panel: Orders + Agent Log */}
          <div className="rounded-2xl flex flex-col shadow-sm overflow-hidden bg-white border border-slate-200/80 h-[480px]">

            {/* Tab Bar */}
            <div className="flex border-b border-slate-100 bg-slate-50/70 p-1.5 gap-1.5">
              <button
                onClick={() => setActiveTab('orders')}
                className={`flex-1 flex items-center justify-center gap-2 rounded-xl py-2.5 text-xs font-semibold transition cursor-pointer ${
                  activeTab === 'orders'
                    ? 'bg-white text-rose-600 shadow-xs ring-1 ring-slate-200/80 font-bold'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                <span>📦 Relief Orders</span>
                {pendingCount > 0 && (
                  <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full text-white bg-rose-500">
                    {pendingCount}
                  </span>
                )}
              </button>
              <button
                onClick={() => setActiveTab('log')}
                className={`flex-1 flex items-center justify-center gap-2 rounded-xl py-2.5 text-xs font-semibold transition cursor-pointer ${
                  activeTab === 'log'
                    ? 'bg-white text-rose-600 shadow-xs ring-1 ring-slate-200/80 font-bold'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                <span>🤖 Agent Activity</span>
              </button>
            </div>

            {/* Tab Content (Guaranteed Pixel-Perfect, No Horizontal Overflow) */}
            <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
              {activeTab === 'orders' ? (
                <OrdersTable
                  orders={state?.orders || []}
                  onApprove={handleApproveOrder}
                  onCancel={handleCancelOrder}
                />
              ) : (
                <AgentLog events={state?.events || []} />
              )}
            </div>
          </div>
        </div>
      </main>

      {/* ── FOOTER ─────────────────────────────────────────────────── */}
      <footer className="py-3 px-6 text-center text-xs text-slate-400 border-t border-slate-200/80 bg-white">
        ResQChain Swarm · Odisha OSDMA Corridor · 3 Hubs · 3 Coastal Shelters · 6 Fleet Vehicles
        <span className="mx-2">·</span>
        Routing by <a href="https://project-osrm.org" target="_blank" rel="noreferrer" style={{ color: '#ff5a5f' }}>OSRM</a>
        <span className="mx-2">·</span>
        AI by <span style={{ color: '#2563eb' }}>Gemini 2.5 Flash</span>
      </footer>

      {/* ── ABOUT MODAL ────────────────────────────────────────────── */}
      {showAboutModal && (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center p-4"
          style={{ backgroundColor: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}>
          <div className="bg-white rounded-2xl w-full max-w-2xl shadow-2xl max-h-[85vh] overflow-y-auto"
            style={{ border: '2px solid #000000' }}>
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: '2px solid #000000' }}>
              <div>
                <h2 className="font-extrabold text-lg" style={{ color: '#222' }}>How ResQChain Works</h2>
                <p className="text-sm mt-0.5" style={{ color: '#767676' }}>6 AI agents working together in real time</p>
              </div>
              <button onClick={() => setShowAboutModal(false)}
                className="p-2 rounded-full transition"
                style={{ backgroundColor: '#f7f7f7', border: '2px solid #000000' }}
                onMouseOver={e => e.currentTarget.style.backgroundColor = '#ebebeb'}
                onMouseOut={e => e.currentTarget.style.backgroundColor = '#f7f7f7'}>
                <X className="w-5 h-5" style={{ color: '#717171' }} />
              </button>
            </div>

            {/* Agent Cards */}
            <div className="p-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                { icon: '🌧️', name: 'Monitor Agent', desc: 'Watches live Open-Meteo rainfall and GPS truck positions every 10 seconds.', color: '#eff6ff', accent: '#2563eb' },
                { icon: '⚠️', name: 'Risk Agent', desc: 'Maps danger zones from weather data and raises prioritized supply demands.', color: '#fef2f2', accent: '#dc2626' },
                { icon: '📦', name: 'Inventory Agent', desc: 'Uses Gemini AI to pick the best warehouse and reserve the right supplies.', color: '#fffbeb', accent: '#d97706' },
                { icon: '🗺️', name: 'Routing Agent', desc: 'Calculates safe truck routes via OSRM, routing around flood zones.', color: '#faf5ff', accent: '#7c3aed' },
                { icon: '🚛', name: 'Dispatch Agent', desc: 'Assigns the nearest available truck and sends Telegram alerts.', color: '#f0fdf4', accent: '#16a34a' },
                { icon: '🧠', name: 'Orchestrator', desc: 'Runs all 6 agents in sequence every 10 seconds, logging every decision.', color: '#f0f9ff', accent: '#0284c7' },
              ].map((a, i) => (
                <div key={i} className="flex gap-3 p-4 rounded-xl" style={{ backgroundColor: a.color, border: '2px solid #000000' }}>
                  <span className="text-2xl">{a.icon}</span>
                  <div>
                    <p className="font-bold text-sm" style={{ color: a.accent }}>{a.name}</p>
                    <p className="text-xs mt-1" style={{ color: '#555' }}>{a.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="px-6 pb-6 text-center">
              <button onClick={() => setShowAboutModal(false)}
                className="px-8 py-2.5 rounded-xl text-sm font-bold text-white transition"
                style={{ background: 'linear-gradient(135deg, #ff5a5f, #ff385c)', border: '2px solid #000000' }}>
                Got it!
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
