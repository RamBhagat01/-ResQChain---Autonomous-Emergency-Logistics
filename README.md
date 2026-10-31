# ResQChain Swarm
### Autonomous Emergency Response & Supply Chain Logistics Swarm

An execution engine for emergency climate or supply disruptions that continuously monitors weather and fleet telemetry, queries regional supplier inventory APIs, dynamically recalculates safe transit routes around affected zones, and dispatches automated relief orders end-to-end.

---

## 🚀 Running Locally with `npm run dev`

You can run `npm run dev` from the `frontend`, `backend`, or root folder:

### 1. Run Backend Server
```bash
cd backend
npm run dev
```
- Starts the FastAPI backend at `http://localhost:8000` with hot reloading.
- Automatically uses the Python virtual environment (`venv/Scripts/uvicorn` or system uvicorn).
- Automatically clears stale processes on port 8000.

### 2. Run Frontend Dashboard
```bash
cd frontend
npm run dev
```
- Starts the Vite React dashboard at `http://localhost:5173`.
- Binds to `0.0.0.0` for local and network access.

### 3. Run Both Concurrently from Root
```bash
# from project root: d:\vs-code\next_wave
npm run dev
```
- Starts both Backend (port 8000) and Frontend (port 5173) in a single command.
- Or use `npm run dev:backend` / `npm run dev:frontend`.
