import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Demand, Vehicle, Order, Zone, Warehouse, Camp, Event
from app.services.geo import haversine_km
from app.services.notifier import send_telegram_alert
from app.agents.routing_agent import compute_safe_route

# Matches approved warehouse reservations with available fleet trucks, calculates safe routes, and dispatches orders
def run(db: Session, inventory_resolutions: List[Dict[str, Any]]):
    active_zones = db.query(Zone).filter(Zone.active == True).all()

    for item in inventory_resolutions:
        demand = item["demand"]
        camp = item["camp"]
        warehouse = item["warehouse"]
        ai_reasoning = item["ai_reasoning"]

        if not warehouse:
            continue

        # 1. Search for an available IDLE vehicle with sufficient cargo capacity
        idle_vehicles = db.query(Vehicle).filter(
            Vehicle.status == "IDLE",
            Vehicle.capacity >= demand.quantity
        ).all()

        if not idle_vehicles:
            # Fallback when no truck is free
            db.add(Event(
                agent="dispatch",
                level="warn",
                message=f"Demand #{demand.id} queued: No free truck with capacity {demand.quantity} units available.",
                details_json=json.dumps({"demand_id": demand.id, "required_capacity": demand.quantity})
            ))
            db.commit()
            continue

        # Choose the vehicle closest to the pickup warehouse
        chosen_vehicle = min(
            idle_vehicles,
            key=lambda v: haversine_km(v.lat, v.lon, warehouse.lat, warehouse.lon)
        )

        # 2. Compute a hazard-avoiding safe driving route from warehouse to relief camp
        route_info = compute_safe_route(
            warehouse.lat,
            warehouse.lon,
            camp.lat,
            camp.lon,
            active_zones
        )

        # 3. Determine order status based on auto-dispatch setting
        order_status = "IN_TRANSIT" if settings.AUTO_DISPATCH else "PENDING_APPROVAL"
        vehicle_status = "IN_TRANSIT" if settings.AUTO_DISPATCH else "ASSIGNED"

        # 4. Create Order record
        order = Order(
            demand_id=demand.id,
            warehouse_id=warehouse.id,
            vehicle_id=chosen_vehicle.id,
            item=demand.item,
            quantity=demand.quantity,
            status=order_status,
            route_geojson=route_info["route_geojson"],
            distance_km=route_info["distance_km"],
            eta_minutes=route_info["eta_minutes"],
            reroute_count=0,
            ai_reasoning=ai_reasoning
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # Update vehicle and demand status
        chosen_vehicle.status = vehicle_status
        chosen_vehicle.current_order_id = order.id
        demand.status = "ASSIGNED"
        db.commit()

        # 5. Log dispatch activity
        db.add(Event(
            agent="dispatch",
            level="info",
            message=f"Order #{order.id} generated: {order.quantity} {order.item} via {chosen_vehicle.name} from {warehouse.name} to {camp.name} ({order.distance_km} km, ETA {order.eta_minutes} mins). Status: {order_status}.",
            details_json=json.dumps({
                "order_id": order.id,
                "vehicle": chosen_vehicle.name,
                "status": order_status,
                "distance_km": order.distance_km,
                "eta_minutes": order.eta_minutes
            })
        ))
        db.commit()

        # 6. Send real-time Telegram notification if configured
        alert_msg = (
            f"🚨 <b>ResQChain Emergency Dispatch</b>\n"
            f"<b>Order ID:</b> #{order.id}\n"
            f"<b>Destination:</b> {camp.name}\n"
            f"<b>Cargo:</b> {order.quantity} units of {order.item}\n"
            f"<b>Depot:</b> {warehouse.name}\n"
            f"<b>Assigned Vehicle:</b> {chosen_vehicle.name}\n"
            f"<b>Route Distance:</b> {order.distance_km} km (ETA: {order.eta_minutes} mins)\n"
            f"<b>Status:</b> {order_status}"
        )
        send_telegram_alert(alert_msg)
