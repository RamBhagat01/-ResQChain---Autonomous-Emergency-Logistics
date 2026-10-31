const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

// Fetch full system state bundle (warehouses, camps, vehicles, zones, demands, orders, kpis, events)
export async function fetchState() {
  const res = await fetch(`${API_BASE}/state`);
  if (!res.ok) throw new Error("Failed to fetch state");
  return res.json();
}

// Check whether live OSRM road routing is reachable from the backend.
export async function fetchRoutingStatus() {
  const res = await fetch(`${API_BASE}/routing/status`);
  if (!res.ok) throw new Error("Failed to check routing service");
  return res.json();
}

// Trigger simulated flood disaster zone
export async function simulateFlood(payload) {
  const res = await fetch(`${API_BASE}/simulate/flood`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to simulate flood");
  return res.json();
}

// Enlarge an active danger zone to trigger dynamic rerouting demo
export async function simulateGrow(payload) {
  const res = await fetch(`${API_BASE}/simulate/grow`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to grow zone");
  return res.json();
}

// Clear all active simulated disaster zones
export async function simulateClear() {
  const res = await fetch(`${API_BASE}/simulate/clear`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to clear zones");
  return res.json();
}

// Reset entire database back to default initial seed state
export async function simulateReset() {
  const res = await fetch(`${API_BASE}/simulate/reset`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to reset demo");
  return res.json();
}

// Approve a pending relief order for immediate dispatch
export async function approveOrder(orderId) {
  const res = await fetch(`${API_BASE}/orders/${orderId}/approve`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to approve order");
  return res.json();
}

// Cancel an order, returning stock and freeing assigned truck
export async function cancelOrder(orderId) {
  const res = await fetch(`${API_BASE}/orders/${orderId}/cancel`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to cancel order");
  return res.json();
}

// Toggle autonomous auto-dispatch mode
export async function setAutoDispatch(enabled) {
  const res = await fetch(`${API_BASE}/settings/auto-dispatch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error("Failed to set auto-dispatch");
  return res.json();
}

// Manually trigger an immediate swarm cycle
export async function runCycleNow() {
  const res = await fetch(`${API_BASE}/cycle/run`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger cycle");
  return res.json();
}

// Fetch live GloFAS flood risk for all Odisha monitoring points
export async function fetchFloodRisk() {
  const res = await fetch(`${API_BASE}/flood-risk`);
  if (!res.ok) throw new Error("Failed to fetch flood risk");
  return res.json();
}

export async function fetchSatelliteFlood() {
  const res = await fetch(`${API_BASE}/satellite/flood`);
  if (!res.ok) throw new Error("Failed to fetch satellite flood data");
  return res.json();
}

export async function refreshSatellite() {
  const res = await fetch(`${API_BASE}/satellite/refresh`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to queue satellite refresh");
  return res.json();
}

export async function fetchFloodPrediction() {
  const res = await fetch(`${API_BASE}/flood-prediction`);
  if (!res.ok) throw new Error("Failed to fetch heuristic risk scores");
  return res.json();
}

export async function fetchWarehouseSites(params = {}) {
  const query = new URLSearchParams(params).toString();
  const res = await fetch(`${API_BASE}/warehouse-sites?${query}`);
  if (!res.ok) throw new Error("Failed to fetch warehouse sites");
  return res.json();
}

