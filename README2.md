# ResQChain Swarm - Development Tracker

This file documents the step-by-step progress across all implementation phases for the **ResQChain Swarm** hackathon project.

---

## 📊 Phase-by-Phase Progress Tracker

- [x] **Phase 0: Project Setup** (Completed)
- [x] **Phase 1: Database + Seed Data** (Completed)
- [x] **Phase 2: Mock Supplier API + Fleet Simulator** (Completed)
- [x] **Phase 3: Weather + Monitor + Risk Agents** (Completed)
- [x] **Phase 4: Routing Agent** (Completed)
- [x] **Phase 5: Inventory + Dispatch Agents** (Completed)
- [x] **Phase 6: LLM + Orchestrator + Scheduler** (Completed)
- [x] **Phase 7: Frontend Dashboard** (Completed)
- [x] **Phase 8: Polish, Tests & Demo Script** (Completed)
- [ ] **Phase 9: Deployment** (Optional)

---

## 🛠️ Detailed Progress Log

### ✅ Phase 0: Project Setup
* **Date Completed:** 2026-10-31
* **Files Created / Modified:**
  - `.gitignore`: Configured exclusions for `.env`, Python cache, `venv`, SQLite DBs, and `node_modules`.
  - `.env.example` & `.env`: Configured environment variables (Gemini API key, Telegram, simulator settings). Routing uses OSRM public server — no key needed.
  - `backend/requirements.txt`: Specified FastAPI, Uvicorn, SQLAlchemy, HTTPX, Shapely, python-dotenv, APScheduler, Pydantic, google-genai, Pytest.
  - `backend/venv/`: Installed all backend packages.
  - `backend/app/main.py`: Created minimal FastAPI application with `/api/health` and CORS.
  - `frontend/package.json`: Configured React 18, Vite, `react-leaflet@4.2.1`, `leaflet`, and Tailwind CSS.
  - `frontend/vite.config.js`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`: Setup build and styling pipelines.
* **Verification:**
  - Backend responded with `{"status": "ok"}` on `GET /api/health`.
  - Frontend production build succeeded with 0 errors via `npm run build`.

---

### ✅ Phase 1: Database + Seed Data
* **Date Completed:** 2026-10-31
* **Files Created / Modified:**
  - `backend/app/config.py`: Centralized configuration loading from `.env` with fallback defaults.
  - `backend/app/db.py`: SQLite connection engine and session factory (`get_db`, `init_db`).
  - `backend/app/models.py`: Defined 9 SQLAlchemy relational models:
    - `warehouses`, `inventory`, `camps`, `demands`, `vehicles`, `zones`, `orders`, `events`, `observations`.
  - `backend/app/schemas.py`: Pydantic models for validation and comprehensive `StateResponse`.
  - `backend/app/seed.py`: Seed data generator for Odisha's coastal/flood corridor:
    - 3 Warehouses (Bhubaneswar, Cuttack, Berhampur) with stocked inventory across 4 essential relief items.
    - 3 Camps (Puri, Paradeep, Kendrapara) with demographic sizes.
    - 6 Fleet Vehicles (Alpha through Zeta) distributed across depots.
    - Initial orchestrator activity event.
  - `backend/app/main.py`: Mounted lifespan startup hooks (`init_db`, `seed_database`), implemented `GET /api/state` and `GET /api/events`.
* **Verification:**
  - `GET /api/state` verified: returns 3 warehouses, 3 camps, 6 trucks, complete inventory, initial event, and live KPI counters.

---

### ✅ Phase 2: Mock Supplier API + Fleet Simulator
* **Date Completed:** 2026-10-31
* **Files Created / Modified:**
  - `backend/app/services/geo.py`:
    - `haversine_km`: GPS distance calculator using the Haversine formula.
    - `circle_to_polygon`: Converts danger circle (lat, lon, radius) to Shapely Polygon with GeoJSON standard `[lon, lat]` points.
    - `point_in_zone`: Fast distance-based hazard proximity detection.
    - `route_intersects_zones`: Checks if route LineString intersects active hazard polygons.
  - `backend/app/mock/supplier_api.py`:
    - `GET /mock/suppliers/inventory?item=...`: Returns partner warehouse stock, coordinates, and reliability.
    - `POST /mock/suppliers/reserve`: Atomic inventory reservation and stock decrementing with reservation IDs.
  - `backend/app/mock/fleet_simulator.py`:
    - `step(db)`: Moves `IN_TRANSIT` trucks along route geometry at `SIM_SPEED_KM_PER_STEP`.
    - Handles milestone transitions: upon arrival, sets order to `DELIVERED`, marks demand `FULFILLED`, sets truck to `IDLE`, and writes delivery event logs.
  - `backend/app/main.py`: Mounted `/mock/suppliers` router onto FastAPI.
* **Verification:**
  - `GET /mock/suppliers/inventory?item=food_kits` returned all 3 regional warehouses with available quantities and reliability ratings.
  - `POST /mock/suppliers/reserve` successfully decremented Bhubaneswar stock by 50 units (350 -> 300) and generated unique reservation ID.
  - `step(db)` tested and verified against database session.

---

### ✅ Phase 3: Weather + Monitor + Risk Agents
* **Date Completed:** 2026-10-31
* **Files Created / Modified:**
  - `backend/app/services/weather.py`:
    - `get_current_weather(lat, lon)`: Connects to the free Open-Meteo weather API (no key required) with 4s timeout and graceful offline fallback.
  - `backend/app/agents/monitor_agent.py`:
    - `run(db)`: Pulls live precipitation and wind speed across the 6 regional monitoring points, records `Observation` rows, triggers fleet simulator step, and logs monitor telemetry events.
  - `backend/app/agents/risk_agent.py`:
    - `run(db)`: Analyzes rain readings against `RAIN_THRESHOLD_MM`, creates dynamic hazard zones, auto-expires weather zones after `ZONE_TTL_MINUTES`, checks proximity to relief camps, raises prioritized emergency `demands` (`food_kits`, `water_liters`, `medical_kits`), flags trapped vehicles, and logs audit events.
  - `backend/app/main.py`: Added disaster simulation and control endpoints:
    - `POST /api/simulate/flood`: Triggers simulated flood or disaster zone.
    - `POST /api/simulate/grow`: Enlarges a zone's radius for live re-routing demos.
    - `POST /api/simulate/clear`: Deactivates simulated danger zones.
    - `POST /api/simulate/reset`: Reseeds database back to default initial state.
    - `POST /api/cycle/run`: Manually runs immediate swarm cycle for testing/demos.
* **Verification:**
  - Simulated a flood near Paradeep (`radius_km: 4.0`, `severity: 4`) via `/api/simulate/flood`.
  - Executed cycle via `/api/cycle/run`: Monitor Agent queried 6 weather stations, Risk Agent identified the Paradeep shelter, and created prioritized `OPEN` demands.
  - Verified in `/api/state`: `kpis.active_zones: 1`, `kpis.open_demands: 3`, and activity events recorded.

---

### ✅ Phase 4: Routing Agent
* **Date Completed:** 2026-10-31
* **Files Created / Modified:**
  - `backend/app/services/routing.py`:
    - `fetch_osrm_route(waypoints)`: Calls OSRM public demo server (`https://router.project-osrm.org`) — **no API key required**. Decodes encoded polyline geometry into (lat, lon) pairs, returns `distance_km`, `duration_min`, and route coordinates.
    - `generate_hazard_detour(origin, dest, zone)`: Geometric fallback that computes a perpendicular vector waypoint offset from the hazard zone perimeter (no external call needed).
    - `calculate_route(origin_lat, origin_lon, dest_lat, dest_lon, zones)`: Main entry — clear path calls OSRM directly; blocked path computes detour waypoint and stitches two OSRM legs together; OSRM offline falls back to geometric estimation with 1.25x haversine road factor.
  - `backend/app/agents/routing_agent.py`:
    - `compute_safe_route`: Computes clear path around active zones. If destination is inside a danger zone, routes to safe perimeter staging coordinates and flags `needs_air_boat_support`.
    - `reroute_order`: Inspects `IN_TRANSIT` orders, detects if newly formed/expanded zones intersect existing path, recalibrates route from current truck coordinates, increments `reroute_count`, and logs an alert.
* **Verification:**
  - Computed corridor Bhubaneswar -> Paradeep without hazards via OSRM (no API key needed).
  - Placed 10 km flood zone in between: two-leg OSRM stitching produced detour polyline around hazard perimeter, confirming dynamic obstacle avoidance.
  - OSRM offline fallback verified — geometric estimation within 5% of real distance.

---

### ✅ Phase 5: Inventory + Dispatch Agents
* **Date Completed:** 2026-10-31
* **Files Created / Modified:**
  - `backend/app/services/notifier.py`:
    - `send_telegram_alert(msg)`: Sends HTML formatted notifications to Telegram bot chat when configured; fails silently without blocking the swarm cycle.
  - `backend/app/services/llm.py`:
    - `ask_json(system_prompt, user_payload)`: Structured JSON caller using `google-genai` SDK with automatic code-fence stripping.
    - `rule_based_warehouse_selection`: Deterministic mathematical fallback scoring (`stock * 0.5 + reliability * 0.3 - distance_penalty * 0.2`) when Gemini API key is absent.
  - `backend/app/agents/inventory_agent.py`:
    - `run(db)`: Queries mock supplier inventory API over HTTP via `httpx`, computes distance matrix from warehouses to affected camps, invokes LLM / heuristic decision-maker, reserves stock via supplier API, and persists AI audit reasoning.
  - `backend/app/agents/dispatch_agent.py`:
    - `run(db)`: Assigns nearest available `IDLE` truck with capacity, invokes Routing Agent to generate hazard-avoiding route, creates `Order`, transitions demand to `ASSIGNED`, and fires Telegram alerts.
  - `backend/app/main.py`:
    - `POST /api/orders/{id}/approve`: Operator human-in-the-loop approval endpoint transitioning orders from `PENDING_APPROVAL` to `IN_TRANSIT`.
    - `POST /api/orders/{id}/cancel`: Cancellation endpoint restoring warehouse inventory, releasing vehicles to `IDLE`, and resetting demands to `OPEN`.
    - `POST /api/settings/auto-dispatch`: Endpoint to toggle autonomous dispatch mode.
* **Verification:**
  - Simulated a flood near Paradeep: generated open demands.
  - Swarm cycle executed:
    - **Food kits demand:** Algorithm considers stock, reliability and distance across the Odisha hubs.
    - **Medical kits demand:** Algorithm considers the closer Cuttack depot when stock and route safety permit.
    - Assigned Truck Alpha and Truck Gamma with generated safe routes, ETAs, and stored AI explanations.
  - Approved Order #1 via `POST /api/orders/1/approve`: successfully transitioned to `IN_TRANSIT`.

---

### ✅ Phase 6: LLM + Orchestrator + Scheduler
* **Date Completed:** 2026-10-31
* **Files Created / Modified:**
  - `backend/app/agents/orchestrator.py`:
    - `run_cycle(db)`: Coordinates the 6-stage autonomous swarm pipeline (Monitor -> Risk -> Demand -> Inventory -> Dispatch -> Dynamic Reroute -> SitRep).
    - Fault-isolated design: wraps each stage in `try/except` so single-agent exceptions never break the master loop.
  - `backend/app/scheduler.py`:
    - Background scheduler utilizing `AsyncIOScheduler` from APScheduler running every 10s.
  - `backend/app/main.py`:
    - Mounted scheduler startup and teardown in FastAPI lifespan.
* **Verification:**
  - Autonomous background scheduler verified running every 10 seconds.
  - Dynamic re-routing verified on expanding hazard zones with AI reasoning saved to `events`.

---

### ✅ Phase 7: Frontend Dashboard
* **Date Completed:** 2026-10-31
* **Files Created / Modified:**
  - `frontend/src/api.js`: Centralized fetch client for state polling, order approval/cancellation, and disaster simulation controls.
  - `frontend/src/components/MapView.jsx`:
    - Interactive Leaflet dark-map with custom styled HTML markers.
    - Renders warehouses (blue), relief camps (amber), moving trucks with status badges (emerald/slate), pulsing danger zones (translucent red), safe corridors (sky-blue), and dynamic rerouted detours (purple dashed).
    - Integrated map click coordinate capture.
  - `frontend/src/components/KpiCards.jsx`: Real-time KPI counters (active zones, open demands, trucks in transit, deliveries, and reroutes).
  - `frontend/src/components/AgentLog.jsx`: Real-time color-coded terminal log with expandable AI reasoning payloads.
  - `frontend/src/components/OrdersTable.jsx`: Orders management table with 1-click Approve / Cancel buttons and expandable Gemini reasoning.
  - `frontend/src/components/ControlPanel.jsx`:
    - Presets for 1-click demo triggering (Mahanadi Basin, Puri Cyclone, Paradeep Delta).
    - Radius & Severity sliders.
    - Grow Active Zone button (+2 km) for live dynamic re-routing demos.
    - Auto-Dispatch autonomous toggle switch.
  - `frontend/src/App.jsx`: Top navigation bar, status indicators, 3-second auto-polling loop, and responsive grid layout.
* **Verification:**
  - Vite production build succeeded with 0 errors (`npm run build`).
  - Frontend verified serving at `http://localhost:5173`.
  - Full demo story runnable with mouse clicks only.

---

### ✅ Phase 8: Polish, Tests & Demo Script
* **Date Completed:** 2026-10-31
* **Files Created / Modified:**
  - `backend/tests/test_smoke.py`:
    - `test_health`: Verified HTTP 200 and `{"status": "ok"}`.
    - `test_initial_state`: Verified seeded warehouses, camps, and trucks.
    - `test_supplier_inventory`: Verified mock supplier stock discovery.
    - `test_flood_to_order_pipeline`: End-to-end integration test validating simulated flood -> demand creation -> Gemini / heuristic supplier matching -> safe route computation -> truck dispatch -> operator approval.
  - `DEMO_SCRIPT.md`:
    - 8 structured presenter steps with exact click instructions and presentation talk tracks.
    - 3 bulletproof fallback plans (offline protection, OSRM offline geometric fallback, instant state reset).
    - Pitch lines ready for the judging panel.
  - `frontend/src/App.jsx`:
    - Added interactive **"Architecture / About" modal** with the ASCII system architecture diagram and 6-agent responsibility breakdown.
* **Verification:**
  - All 4 pytest smoke tests passed with 100% success (`4 passed in 13.13s`).
  - Production frontend build verified with 0 errors (`npm run build`).

---

## 🚀 Active Services Quick Reference

| Service | Address | Description |
|---|---|---|
| **Frontend Dashboard** | `http://localhost:5173` | React 18 + Leaflet UI |
| **Backend API Health** | `http://localhost:8000/api/health` | Health check endpoint |
| **Backend State API** | `http://localhost:8000/api/state` | Full state bundle |
| **Supplier Inventory API** | `http://localhost:8000/mock/suppliers/inventory?item=food_kits` | Mock supplier query |
| **Swagger Interactive Docs**| `http://localhost:8000/docs` | Interactive API explorer |

---

---

## 🛠️ Local Development Automation (npm run dev)

You can start services using `npm run dev` anywhere in the project:
- **backend/**: `npm run dev` executes `node dev.js`, which detects the Python venv (`venv/Scripts/uvicorn.exe`), auto-clears any stale processes on port 8000, and boots Uvicorn with hot reloading at `http://localhost:8000`.
- **frontend/**: `npm run dev` runs `vite --host 0.0.0.0` at `http://localhost:5173`.
- **Root directory (next_wave/)**: `npm run dev` runs both backend and frontend concurrently in a single terminal.

---

## 🎨 UI Redesign (Airbnb-Inspired)

- Clean, accessible light theme with Airbnb signature coral (`#FF5A5F` / `#FF385C`), rounded cards (`rounded-2xl`), subtle shadows, and crisp typography (`Inter`).
- Uninverted natural map view with rounded pill map pins.
- Clean tabbed panel for Orders & Agent Activity with plain-language explanations.
