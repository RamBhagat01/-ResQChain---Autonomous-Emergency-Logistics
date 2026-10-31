from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.config import settings
from app.db import init_db, get_db, SessionLocal
from app.models import Warehouse, Camp, Vehicle, Zone, Demand, Order, Event, Inventory
from app.schemas import StateResponse, EventOut, KpiOut, ZoneCreate, ZoneGrow, ZoneOut, OrderOut, AutoDispatchSetting
from app.seed import seed_database
from app.mock.supplier_api import router as mock_supplier_router
from app.agents import orchestrator
from app.scheduler import start_scheduler, stop_scheduler
from app.services.routing import check_osrm_service

# Lifespan context to initialize database schema, seed data, and start autonomous scheduler
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

    # Start the autonomous background swarm scheduler
    start_scheduler()
    yield
    # Stop scheduler on shutdown
    stop_scheduler()

# Initialize FastAPI application
app = FastAPI(
    title="ResQChain Swarm API",
    description="Autonomous Emergency Response & Supply Chain Logistics Swarm",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend dashboard (local Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount mock supplier inventory API router
app.include_router(mock_supplier_router)

# Health check endpoint to verify backend service is running
@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/routing/status")
def routing_status():
    """Return live OSRM availability and a plain-language reason when offline."""
    return check_osrm_service()

# Retrieve comprehensive system state for dashboard visualization in one call
@app.get("/api/state", response_model=StateResponse)
def get_state(db: Session = Depends(get_db)):
    warehouses = db.query(Warehouse).all()
    camps = db.query(Camp).all()
    vehicles = db.query(Vehicle).all()
    zones = db.query(Zone).all()
    demands = db.query(Demand).all()
    orders = db.query(Order).all()

    # Query last 50 events, ordered newest first
    events = db.query(Event).order_by(desc(Event.timestamp)).limit(50).all()

    # Calculate key performance indicators (KPIs)
    active_zones_count = sum(1 for z in zones if z.active)
    open_demands_count = sum(1 for d in demands if d.status == "OPEN")
    in_transit_count = sum(1 for o in orders if o.status == "IN_TRANSIT")
    delivered_count = sum(1 for o in orders if o.status == "DELIVERED")
    total_reroutes = sum(o.reroute_count for o in orders)

    # Determine if fallback mode is active (missing API keys)
    fallback_mode = not bool(settings.GEMINI_API_KEY)  # OSRM needs no key

    kpis = KpiOut(
        active_zones=active_zones_count,
        open_demands=open_demands_count,
        orders_in_transit=in_transit_count,
        delivered_orders=delivered_count,
        total_reroutes=total_reroutes,
        auto_dispatch=settings.AUTO_DISPATCH,
        fallback_mode=fallback_mode,
    )

    return StateResponse(
        warehouses=warehouses,
        camps=camps,
        vehicles=vehicles,
        zones=zones,
        demands=demands,
        orders=orders,
        kpis=kpis,
        events=events,
    )

# Retrieve recent agent activity log events
@app.get("/api/events", response_model=List[EventOut])
def get_events(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.query(Event).order_by(desc(Event.timestamp)).limit(limit).all()

# --- Simulation Endpoints ---

# Creates a new simulated disaster zone (e.g., flood or flash storm)
@app.post("/api/simulate/flood", response_model=ZoneOut)
def simulate_flood(req: ZoneCreate, db: Session = Depends(get_db)):
    zone = Zone(
        name=req.name or f"Simulated Flood (Severity {req.severity})",
        center_lat=req.lat,
        center_lon=req.lon,
        radius_km=min(req.radius_km, settings.MAX_ZONE_RADIUS_KM),
        severity=req.severity,
        source="simulated",
        active=True
    )
    db.add(zone)
    db.add(Event(
        agent="risk",
        level="alert",
        message=f"Simulated flood triggered at ({req.lat:.4f}, {req.lon:.4f}) with radius {zone.radius_km} km, severity {req.severity}.",
        details_json=f'{{"lat": {req.lat}, "lon": {req.lon}, "radius_km": {zone.radius_km}, "severity": {req.severity}}}'
    ))
    db.commit()
    db.refresh(zone)
    return zone

# Enlarges an existing hazard zone to trigger dynamic re-routing in demos
@app.post("/api/simulate/grow", response_model=ZoneOut)
def simulate_grow(req: ZoneGrow, db: Session = Depends(get_db)):
    zone = db.query(Zone).filter(Zone.id == req.zone_id, Zone.active == True).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Active zone not found")

    zone.radius_km += req.extra_km
    db.add(Event(
        agent="risk",
        level="warn",
        message=f"Hazard zone #{zone.id} expanded by {req.extra_km} km to new radius {zone.radius_km} km.",
        details_json=f'{{"zone_id": {zone.id}, "new_radius_km": {zone.radius_km}}}'
    ))
    db.commit()
    db.refresh(zone)
    return zone

# Deactivates all simulated disaster zones
@app.post("/api/simulate/clear")
def simulate_clear(db: Session = Depends(get_db)):
    simulated_zones = db.query(Zone).filter(Zone.source == "simulated", Zone.active == True).all()
    count = len(simulated_zones)
    for z in simulated_zones:
        z.active = False

    db.add(Event(
        agent="risk",
        level="info",
        message=f"Cleared {count} simulated danger zones.",
        details_json=f'{{"cleared_count": {count}}}'
    ))
    db.commit()
    return {"status": "cleared", "cleared_count": count}

# Resets entire database back to default initial seed state
@app.post("/api/simulate/reset")
def simulate_reset(db: Session = Depends(get_db)):
    seed_database(db, force_reset=True)
    return {"status": "reset_complete"}

# --- Order Lifecycle Endpoints ---

# Human-in-the-loop operator approval to dispatch a pending order
@app.post("/api/orders/{order_id}/approve", response_model=OrderOut)
def approve_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=400, detail=f"Cannot approve order in status {order.status}")

    order.status = "IN_TRANSIT"
    if order.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == order.vehicle_id).first()
        if vehicle:
            vehicle.status = "IN_TRANSIT"

    db.add(Event(
        agent="dispatch",
        level="info",
        message=f"Human operator approved Order #{order.id}. Truck is now in transit."
    ))
    db.commit()
    db.refresh(order)
    return order

# Human operator cancellation of an order (restores stock, vehicle, and demand)
@app.post("/api/orders/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = "CANCELLED"

    # Free the assigned vehicle
    if order.vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == order.vehicle_id).first()
        if vehicle:
            vehicle.status = "IDLE"
            vehicle.current_order_id = None

    # Reset demand back to OPEN
    if order.demand_id:
        demand = db.query(Demand).filter(Demand.id == order.demand_id).first()
        if demand:
            demand.status = "OPEN"

    # Restore inventory
    inv = db.query(Inventory).filter(
        Inventory.warehouse_id == order.warehouse_id,
        Inventory.item == order.item
    ).first()
    if inv:
        inv.quantity += order.quantity

    db.add(Event(
        agent="dispatch",
        level="warn",
        message=f"Order #{order.id} was cancelled. Stock and vehicle restored."
    ))
    db.commit()
    db.refresh(order)
    return order

# Toggle auto-dispatch mode (autonomous vs human approval)
@app.post("/api/settings/auto-dispatch")
def set_auto_dispatch(setting: AutoDispatchSetting):
    settings.AUTO_DISPATCH = setting.enabled
    return {"auto_dispatch": settings.AUTO_DISPATCH}

# Manually executes a complete multi-agent swarm cycle via orchestrator
@app.post("/api/cycle/run")
def run_cycle_now(db: Session = Depends(get_db)):
    stats = orchestrator.run_cycle(db)
    return {
        "cycle_status": "success",
        "stats": stats
    }
