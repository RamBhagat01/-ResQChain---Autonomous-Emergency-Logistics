from typing import List, Optional
from pathlib import Path
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.config import settings
from app.db import init_db, get_db, SessionLocal
from app.models import Warehouse, Camp, Vehicle, Zone, Demand, Order, Event, Inventory, SatelliteFloodObservation
from app.schemas import StateResponse, EventOut, KpiOut, ZoneCreate, ZoneGrow, ZoneOut, OrderOut, AutoDispatchSetting, SatelliteFloodResponse, FloodRiskScoreOut, WarehouseSitesResponse
from app.seed import seed_database
from app.mock.supplier_api import router as mock_supplier_router
from app.agents import orchestrator
from app.scheduler import start_scheduler, stop_scheduler
from app.services.routing import check_osrm_service
from app.services.routing import calculate_route, fetch_osrm_route
from app.services.geo import point_in_zone, route_intersects_zones
from app.services.satellite_flood import latest_result, refresh_satellite_cache
from app.services.flood_prediction import compute_scores
from app.services.warehouse_siting import recommend_sites
from app.seed import MONITORING_POINTS

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


@app.get("/api/routing/warehouse-to-risk")
def warehouse_to_risk_route(
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lon: float = Query(..., ge=-180, le=180),
    dest_lat: float = Query(..., ge=-90, le=90),
    dest_lon: float = Query(..., ge=-180, le=180),
    db: Session = Depends(get_db),
):
    """Preview a safe route from a selected warehouse to a risk point."""
    active_zones = db.query(Zone).filter(Zone.active == True).all()
    endpoint_zones = [
        zone for zone in active_zones
        if point_in_zone(origin_lat, origin_lon, zone) or point_in_zone(dest_lat, dest_lon, zone)
    ]
    avoid_zones = [zone for zone in active_zones if zone not in endpoint_zones]
    route = calculate_route(origin_lat, origin_lon, dest_lat, dest_lon, avoid_zones)
    # Never show a straight-line/geometric fallback as a truck-drivable route.
    # If the legacy offline corridor fallback was selected, ask OSRM directly;
    # if unavailable, return no line rather than implying a drivable path.
    if route.get("approximate_route") or not route.get("geometry_coords"):
        route = fetch_osrm_route(origin_lat, origin_lon, dest_lat, dest_lon)
    if not route:
        return {
            "available": False,
            "message": "OSRM road routing is unavailable for this route. No drivable path is being shown; retry when routing is reachable.",
            "geometry_coords": [],
            "origin": {"lat": origin_lat, "lon": origin_lon},
            "destination": {"lat": dest_lat, "lon": dest_lon},
            "routing": "unavailable",
        }
    route_hazards = [zone for zone in active_zones if route_intersects_zones(route.get("geometry_coords", []), [zone])]
    hazard_names = list(dict.fromkeys(zone.name for zone in [*endpoint_zones, *route_hazards]))
    return {
        **route,
        "available": True,
        "origin": {"lat": origin_lat, "lon": origin_lon},
        "destination": {"lat": dest_lat, "lon": dest_lon},
        "routing": "OSRM road route",
        "hazard_warning": (
            "OSRM road route intersects active hazard area(s): "
            + ", ".join(hazard_names)
            + ". Verify road closures and field conditions before dispatch."
            if hazard_names else None
        ),
    }


@app.get("/api/warehouses/oswc")
def oswc_warehouses():
    """Return CSV-sourced OSWC locations; these are reference capacity records, not live stock."""
    data_path = Path(__file__).parent / "data" / "oswc_warehouses.json"
    # utf-8-sig accepts both plain UTF-8 and PowerShell-exported JSON with a BOM.
    rows = json.loads(data_path.read_bytes().decode("utf-8-sig"))
    located = [row for row in rows if row.get("lat") is not None and row.get("lon") is not None
               and 17.5 <= row["lat"] <= 23.0 and 80.0 <= row["lon"] <= 88.0]
    return {
        "source": "User-provided Odisha OSWC warehouse CSV; coordinates resolved from supplied Google Maps links",
        "total_rows": len(rows),
        "located_count": len(located),
        "unlocated_count": len(rows) - len(located),
        "warehouses": located,
    }

# Retrieve comprehensive system state for dashboard visualization in one call
@app.get("/api/state", response_model=StateResponse)
def get_state(db: Session = Depends(get_db)):
    warehouses = db.query(Warehouse).all()
    camps = db.query(Camp).all()
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
    satellite = latest_result(db)

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
        satellite_mode=satellite.get("mode", "SAMPLE"),
        satellite_flooded_km2=satellite.get("flooded_km2", 0.0),
        satellite_data_age_hours=satellite.get("data_age_hours"),
    )

    return StateResponse(
        warehouses=warehouses,
        camps=camps,
        # Fleet positions are intentionally not exposed to the dashboard/API state payload.
        vehicles=[],
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

# Live GloFAS flood risk for all Odisha monitoring points (no API key needed)
@app.get("/api/flood-risk")
def get_flood_risk_endpoint():
    from app.services.flood_risk import get_all_flood_risks
    return get_all_flood_risks(MONITORING_POINTS)


@app.get("/api/satellite/flood", response_model=SatelliteFloodResponse)
def satellite_flood(db: Session = Depends(get_db)):
    return latest_result(db)


@app.post("/api/satellite/refresh")
def satellite_refresh():
    # APScheduler executes the actual work; this endpoint only queues it.
    from app.scheduler import scheduler, scheduled_satellite_refresh
    job_id = "satellite_flood_manual"
    scheduler.add_job(scheduled_satellite_refresh, id=job_id, replace_existing=True)
    return {"status": "queued", "message": "Satellite refresh queued in the background."}


@app.get("/api/flood-prediction", response_model=List[FloodRiskScoreOut])
def flood_prediction(db: Session = Depends(get_db)):
    result = latest_result(db)
    points = [{**p, "population": 0} for p in MONITORING_POINTS]
    for camp in db.query(Camp).all():
        points.append({"name": camp.name, "lat": camp.lat, "lon": camp.lon, "population": camp.population})
    scores = compute_scores(points, result)
    # Predicted zones are deliberately simple circles for compatibility with the existing routing layer.
    from datetime import datetime, timedelta, timezone
    for item in scores:
        if item["level"] in {"HIGH", "CRITICAL"}:
            duplicate = db.query(Zone).filter(Zone.source == "PREDICTED", Zone.active == True,
                Zone.center_lat.between(item["lat"] - 0.03, item["lat"] + 0.03), Zone.center_lon.between(item["lon"] - 0.03, item["lon"] + 0.03)).first()
            if not duplicate:
                db.add(Zone(name=f"Predicted flood risk: {item['name']}", center_lat=item["lat"], center_lon=item["lon"],
                    radius_km=2.0, severity=5 if item["level"] == "CRITICAL" else 4, source="PREDICTED", active=True))
    db.commit()
    return scores


@app.get("/api/warehouse-sites", response_model=WarehouseSitesResponse)
def warehouse_sites(lat: float = Query(20.4625), lon: float = Query(85.8828), radius_km: float = Query(30, gt=0, le=100), limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    return recommend_sites(lat, lon, radius_km, limit, latest_result(db), db.query(Zone).filter(Zone.active == True).all(), db.query(Camp).all())

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
