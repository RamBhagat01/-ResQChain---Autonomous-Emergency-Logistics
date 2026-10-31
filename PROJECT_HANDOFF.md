# ResQChain Swarm — Project Handoff Documentation

**Purpose:** This document is a current-state technical handoff for another AI or developer. It explains what exists, how the system works, what has been verified, what is still incomplete, and how to formulate the next task safely.

**Repository:** `D:\vs-code\next_wave`

**Snapshot date:** 2026-11-01

## 1. Product summary

ResQChain Swarm is an emergency-response logistics demonstrator for Odisha's coastal and flood corridor. It combines a FastAPI backend, SQLite persistence, a React/Leaflet operations dashboard, deterministic safety logic, optional Gemini reasoning, live weather/flood data, simulated fleet movement, supplier inventory reservation, and dynamic hazard-aware re-routing.

The core operating loop is:

```text
Monitor weather + fleet
        ↓
Risk assessment → active hazard zones → camp demands
        ↓
Inventory selection → reserve stock
        ↓
Dispatch → select truck → calculate safe route
        ↓
Human approval or auto-dispatch
        ↓
Fleet simulation → delivery
        ↓
Re-check routes and re-route if a new hazard intersects them
```

The application is designed to remain demonstrable when optional services are unavailable. Gemini falls back to deterministic scoring, OSRM falls back to local road corridors and then geometric detours, and Telegram failures do not stop the swarm cycle.

## 2. Current implementation status

### Implemented

- FastAPI backend with startup database initialization, seed data, CORS, and APScheduler background cycles.
- SQLite/SQLAlchemy data model for warehouses, inventory, camps, demands, vehicles, zones, orders, events, and observations.
- Odisha monitoring points, warehouses, relief camps, and six seeded trucks.
- Open-Meteo weather integration with graceful failure handling.
- Risk agent that creates and expires weather zones, detects affected camps, creates priority demands, and flags trapped vehicles.
- Mock supplier inventory and reservation API.
- Optional Gemini structured JSON reasoning with deterministic fallback mode.
- Safe routing using public OSRM, a local Odisha corridor graph, and a geometric fallback.
- Dispatch agent with capacity-aware truck selection, route generation, order creation, and optional Telegram notification.
- Human-in-the-loop order approval and cancellation, including inventory, demand, and vehicle restoration on cancellation.
- Simulated truck movement and delivery completion.
- Dynamic re-routing of in-transit orders when active zones intersect their route.
- React/Vite dashboard with live polling, Leaflet map, KPI cards, orders table, agent log, controls, routing availability badge, and flood-risk panel.
- Live flood-risk endpoint using Open-Meteo's GloFAS-derived flood API and CWC-style thresholds.
- Optional Sentinel-1 RTC flood observation with offline SAMPLE fallback, heuristic risk scores, satellite-context allocation reasoning, and OSM warehouse/staging recommendations.
- Four backend smoke tests and a presenter demo script.

### Verified in this snapshot

- Backend smoke tests: `4 passed`.
- Frontend production build: successful with Vite.
- The current working tree contains uncommitted changes related to the live flood-risk feature and routing/configuration updates. Preserve those changes unless the next task explicitly replaces them.

### Known documentation drift

The older [README2.md](./README2.md) contains historical notes that refer to Maharashtra locations and older presets such as Sangli/Kolhapur/Karad. The current source code and seed data are Odisha-focused: Bhubaneswar, Cuttack, Berhampur, Puri, Paradeep, and Kendrapara. Treat the source code and this handoff as authoritative until the older tracker is cleaned up.

## 3. Repository structure

```text
next_wave/
├── package.json                 Root scripts for starting both services
├── dev.js                       Spawns backend and frontend together
├── .env.example                 Configuration template
├── README.md                    Short local setup guide
├── README2.md                   Historical phase tracker; partly stale
├── DEMO_SCRIPT.md               Hackathon presenter walkthrough
├── PROJECT_HANDOFF.md           This document
├── resqchain.db                 Root SQLite database used by default in some runs
├── backend/
│   ├── package.json             Backend runner script
│   ├── requirements.txt         Python dependencies
│   ├── dev.js                   Windows-friendly Uvicorn launcher
│   ├── resqchain.db             Backend SQLite database
│   ├── app/
│   │   ├── main.py              FastAPI app and HTTP endpoints
│   │   ├── config.py            Environment settings and defaults
│   │   ├── db.py                SQLAlchemy engine/session helpers
│   │   ├── models.py            ORM tables
│   │   ├── schemas.py           Pydantic response/request models
│   │   ├── seed.py              Demo geography and seed data
│   │   ├── scheduler.py         Recurring swarm cycle
│   │   ├── agents/              Monitor, risk, inventory, routing, dispatch, orchestrator
│   │   ├── services/            Weather, flood risk, routing, geo, LLM, notifications
│   │   └── mock/                Supplier API and fleet simulator
│   └── tests/test_smoke.py      Backend integration smoke tests
└── frontend/
    ├── package.json             React/Vite dependencies and build scripts
    └── src/
        ├── App.jsx              Dashboard composition and polling/actions
        ├── api.js               Backend fetch client
        ├── index.css            Tailwind/base/map styling
        └── components/          Map, controls, KPIs, flood risk, orders, logs
```

## 4. Runtime and configuration

### Services

| Service | URL | Role |
|---|---|---|
| Frontend | `http://localhost:5173` | React/Vite dashboard |
| Backend | `http://localhost:8000` | FastAPI API and scheduler |
| Swagger | `http://localhost:8000/docs` | Interactive API documentation |
| Health | `http://localhost:8000/api/health` | Backend liveness check |

### Start commands

From the repository root:

```powershell
npm.cmd run dev
```

Or independently:

```powershell
cd backend
npm.cmd run dev

cd ..\frontend
npm.cmd run dev
```

The workspace uses a Windows PowerShell policy that blocks `npm.ps1`; use `npm.cmd` when invoking npm from PowerShell.

### Environment variables

Settings are loaded from the root `.env` by [backend/app/config.py](./backend/app/config.py). Important values:

- `GEMINI_API_KEY`: enables Gemini reasoning. Empty means deterministic fallback mode.
- `GEMINI_MODEL`: defaults to `gemini-2.5-flash`.
- `OSRM_BASE_URL`: defaults to the public OSRM demo server.
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`: optional dispatch alerts.
- `AUTO_DISPATCH`: `false` by default; `true` skips human approval.
- `CYCLE_SECONDS`: background cycle interval, default `10`.
- `RAIN_THRESHOLD_MM`: weather-to-zone threshold, default `7.5`.
- `MAX_ZONE_RADIUS_KM`: maximum simulated zone radius, default `5`.
- `ZONE_TTL_MINUTES`: weather-zone expiry, default `60`.
- `SIM_SPEED_KM_PER_STEP`: simulated truck movement per cycle, default `3`.
- `DATABASE_URL`: defaults to `sqlite:///./resqchain.db`.
- `COPERNICUS_GLOFAS_API_KEY`: currently documented/configured but not required by the live flood-risk endpoint; the endpoint uses Open-Meteo.

Do not commit real API keys from `.env`.

## 5. Backend architecture

### Application lifecycle

[backend/app/main.py](./backend/app/main.py) creates the FastAPI app. On startup it:

1. Creates missing SQLite tables.
2. Seeds the database if it is empty.
3. Starts APScheduler.

On shutdown it stops the scheduler. The scheduler invokes [backend/app/agents/orchestrator.py](./backend/app/agents/orchestrator.py) every `CYCLE_SECONDS`.

### Agent responsibilities

| Agent | Main responsibility | Important side effects |
|---|---|---|
| Monitor | Fetch weather and advance trucks | Adds observations and monitor events |
| Risk | Convert rain/hazards into zones and demands | Creates/expirs zones, creates demands, logs affected camps/trucks |
| Inventory | Select supplier warehouse and reserve stock | Decrements inventory, records reasoning/events |
| Routing | Build hazard-safe route and re-route active orders | Stores route GeoJSON, distance, ETA, reroute count |
| Dispatch | Match demand to warehouse/truck and create order | Assigns truck, updates demand, sends optional Telegram alert |
| Orchestrator | Run agents in sequence and produce sitrep | Fault-isolates stages and logs summary |

The orchestrator order is Monitor → Risk → Inventory → Dispatch → Dynamic re-routing → Situation report. Each major stage is isolated with `try/except`; an agent error is recorded as an orchestrator warning and does not terminate the scheduler.

### Database entities

- `Warehouse`: named hub, coordinates, reliability score.
- `Inventory`: item quantity per warehouse. Items are `food_kits`, `water_liters`, `medical_kits`, and `blankets`.
- `Camp`: relief destination and population.
- `Demand`: requested item/quantity, priority 1–5, and lifecycle `OPEN → ASSIGNED → FULFILLED`.
- `Vehicle`: truck position, capacity, status `IDLE`, `ASSIGNED`, or `IN_TRANSIT`.
- `Zone`: active flood/storm area, radius, severity, source, and creation time.
- `Order`: warehouse-to-camp dispatch, lifecycle `PENDING_APPROVAL`, `IN_TRANSIT`, `DELIVERED`, `FAILED`, or `CANCELLED`; includes route GeoJSON and AI reasoning.
- `Event`: append-only agent activity/audit log.
- `Observation`: timestamped rain and wind readings.

### Seeded geography

Monitoring points are Bhubaneswar, Cuttack, Puri, Paradeep, Kendrapara, and Balasore. Seeded warehouses are Bhubaneswar Central Hub, Cuttack Mahanadi Depot, and Berhampur Southern Hub. Seeded camps are Puri Cyclone Shelter, Paradeep Coastal Shelter, and Kendrapara Flood Camp. Six trucks are distributed two per warehouse.

## 6. API contract

### Read endpoints

- `GET /api/health` → `{ "status": "ok" }`.
- `GET /api/state` → warehouses, camps, vehicles, zones, demands, orders, KPIs, and newest events.
- `GET /api/events?limit=100` → newest agent events.
- `GET /api/routing/status` → OSRM availability and fallback explanation.
- `GET /api/flood-risk` → flood discharge/risk for all monitoring points, sorted by severity descending.
- `GET /mock/suppliers/inventory?item=food_kits` → stock for each warehouse.

### Simulation/control endpoints

- `POST /api/simulate/flood` with `{name?, lat, lon, radius_km, severity}`.
- `POST /api/simulate/grow` with `{zone_id, extra_km}`.
- `POST /api/simulate/clear` → deactivates simulated zones.
- `POST /api/simulate/reset` → deletes operational records and restores seed data.
- `POST /api/cycle/run` → immediately executes one orchestrator cycle.
- `POST /api/settings/auto-dispatch` with `{enabled: boolean}`.

### Order lifecycle endpoints

- `POST /api/orders/{order_id}/approve` → `PENDING_APPROVAL` to `IN_TRANSIT`, and truck to `IN_TRANSIT`.
- `POST /api/orders/{order_id}/cancel` → marks cancelled, restores stock, frees truck, and reopens demand.

### Mock supplier endpoints

- `POST /mock/suppliers/reserve` with `{warehouse_id, item, quantity}`. It returns an opaque reservation ID and decrements stock when sufficient inventory exists.

## 7. Routing and fallback behavior

[backend/app/services/routing.py](./backend/app/services/routing.py) uses a layered strategy:

1. If a route is clear, call OSRM for real road geometry.
2. If OSRM is unavailable, use the local Odisha road-corridor graph.
3. If the local graph cannot produce a safe path, generate a geometric detour around hazard zones.
4. If a route intersects a zone, calculate a perpendicular detour waypoint and try OSRM leg-by-leg; then apply the local graph/geometric fallbacks.

Routes are stored as GeoJSON-style `LineString` JSON in `Order.route_geojson`, with `[longitude, latitude]` coordinate order. When a destination is inside a hazard zone, the routing agent targets a safe perimeter staging point and sets `needs_air_boat_support` internally.

## 8. Frontend behavior

[frontend/src/App.jsx](./frontend/src/App.jsx) polls `/api/state` every three seconds and routing status every fifteen seconds. The UI provides:

- Live situation map with warehouse, camp, truck, zone, and route layers.
- KPI cards for zones, demands, in-transit orders, delivered orders, and reroutes.
- GloFAS/Open-Meteo flood-risk panel.
- Orders tab with Accept/Reject for pending orders and expandable reasoning.
- Agent Activity tab with severity styling and expandable JSON details.
- Controls for flood simulation, zone growth, clearing, reset, manual cycle, and auto-dispatch.
- Connection, Gemini/heuristic, and OSRM status badges.
- About modal describing the six-agent architecture.

The frontend API wrapper is [frontend/src/api.js](./frontend/src/api.js). It currently hard-codes `http://localhost:8000/api`; production deployment should make this configurable.

## 9. Standard demo flow

1. Start both services and open `http://localhost:5173`.
2. Confirm the baseline state and live loop indicator.
3. Select a map location or preset and simulate a flood.
4. Run a cycle or wait for the ten-second scheduler.
5. Inspect risk-generated demands, supplier reasoning, and safe route.
6. Approve a pending order, or enable auto-dispatch.
7. Let the fleet simulator move the truck.
8. Grow the active zone to demonstrate dynamic re-routing.
9. Use Reset Demo to restore the seed state.

The longer presenter script is [DEMO_SCRIPT.md](./DEMO_SCRIPT.md), but its older place names should be updated to match the current Odisha UI before presenting.

## 10. Verification and test commands

Backend smoke tests were run successfully with:

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests/test_smoke.py -q
```

Result in this snapshot: `4 passed`. There are currently deprecation warnings for `datetime.utcnow()`, Pydantic class-based `Config`, and Starlette's TestClient/httpx combination. These warnings do not fail the suite but are good candidates for a maintenance task.

Frontend build was run successfully with:

```powershell
cd frontend
npm.cmd run build
```

## 11. Current risks and technical debt

- The root and backend SQLite databases are mutable demo state; reset behavior should be understood before using production-like data.
- `inventory_agent.py` calls the mock supplier router through an in-process `TestClient`, which is convenient for the demo but should be replaced with a service/repository boundary or real HTTP client in production.
- The public OSRM endpoint is rate-limited and not a production SLA. A self-hosted or managed routing provider is needed for deployment.
- Flood-risk calls are synchronous and fetch one monitoring point at a time. The dashboard may become slow if the upstream API is slow.
- `GET /api/flood-risk` is not cached and is not currently covered by a smoke test.
- `AUTO_DISPATCH` is global in-memory configuration and is not persisted.
- Order and inventory operations are not fully transactional across all agent steps; concurrent scheduler/manual cycles need protection before multi-user deployment.
- Pydantic schemas use legacy class-based `Config` and naive UTC timestamps.
- CORS includes `*` alongside credential support; this should be tightened for production.
- Frontend API base URL is hard-coded to localhost.
- Some source/doc files contain mojibake characters from encoding conversion; clean UTF-8 normalization would improve maintainability.
- Historical documentation and the current code disagree on region and demo presets.
- Live Sentinel-1 processing was not timed in this environment; the verified configuration remained offline-safe SAMPLE mode.

## 12. Recommended next-task backlog

Prioritize according to the next prompt rather than doing all items at once:

1. Update historical docs and presenter script to the current Odisha geography.
2. Add flood-risk tests with mocked upstream responses and a frontend loading/error state test.
3. Add a configurable frontend API base URL and production environment setup.
4. Replace legacy datetime/Pydantic patterns and remove test warnings.
5. Add idempotency/concurrency protection around scheduler cycles, reservations, and order creation.
6. Add authentication/authorization and tighten CORS before external deployment.
7. Add persistent job/audit identifiers and structured event types.
8. Add deployment packaging, health/readiness checks, and a production database option.
9. Install and validate optional live geospatial dependencies, then measure one-tile Sentinel-1 refresh time on the deployment laptop.

## 13. Prompt template for the next AI

Copy and adapt this template:

```text
You are continuing work on the ResQChain Swarm project at D:\\vs-code\\next_wave.

Read PROJECT_HANDOFF.md first, then inspect the relevant source files. The current system is an Odisha-focused FastAPI + SQLite backend and React/Vite/Leaflet dashboard. Preserve existing uncommitted changes unless the task explicitly replaces them.

Task:
[Describe one concrete change]

Acceptance criteria:
- [Observable behavior]
- [API/UI/data requirement]
- [Test or verification requirement]

Constraints:
- Keep Gemini optional and preserve deterministic fallback behavior.
- Keep OSRM/local-road/geometric routing fallbacks working.
- Do not expose secrets or overwrite the demo database unexpectedly.
- Update documentation/tests when behavior changes.

Before finishing:
1. Report files changed.
2. Run the focused backend tests and/or frontend build.
3. Report any warnings, limitations, or remaining follow-up work.
```

## 14. Source-of-truth files

- [backend/app/main.py](./backend/app/main.py): API surface and app lifecycle.
- [backend/app/agents/orchestrator.py](./backend/app/agents/orchestrator.py): cycle order and fault isolation.
- [backend/app/models.py](./backend/app/models.py): persistence model.
- [backend/app/seed.py](./backend/app/seed.py): current demo geography and seed quantities.
- [backend/app/services/routing.py](./backend/app/services/routing.py): route strategy and fallbacks.
- [backend/app/services/flood_risk.py](./backend/app/services/flood_risk.py): live flood-risk integration and thresholds.
- [frontend/src/App.jsx](./frontend/src/App.jsx): dashboard composition and polling.
- [frontend/src/api.js](./frontend/src/api.js): frontend/backend contract.
- [backend/tests/test_smoke.py](./backend/tests/test_smoke.py): current automated behavior coverage.

