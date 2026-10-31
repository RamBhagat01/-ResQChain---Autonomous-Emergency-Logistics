import json
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Vehicle, Order, Demand, Event
from app.services.geo import haversine_km

# Simulates fleet vehicles traveling towards their delivery destinations along route coordinates
def step(db: Session):
    # Query all vehicles currently in transit
    vehicles_in_transit = db.query(Vehicle).filter(Vehicle.status == "IN_TRANSIT").all()
    step_km = settings.SIM_SPEED_KM_PER_STEP

    for vehicle in vehicles_in_transit:
        if not vehicle.current_order_id:
            vehicle.status = "IDLE"
            continue

        order = db.query(Order).filter(Order.id == vehicle.current_order_id).first()
        if not order or not order.route_geojson:
            continue

        try:
            # Route coords are [[lon, lat], ...]
            route_data = json.loads(order.route_geojson)
            coords = route_data.get("coordinates", [])
            if not coords or len(coords) < 2:
                continue
        except Exception:
            continue

        # Find closest point along route to current vehicle location
        closest_idx = 0
        min_dist = float("inf")
        for i, pt in enumerate(coords):
            # pt is [lon, lat]
            d = haversine_km(vehicle.lat, vehicle.lon, pt[1], pt[0])
            if d < min_dist:
                min_dist = d
                closest_idx = i

        # Step forward along route coordinates by step_km
        remaining_km = step_km
        current_idx = closest_idx

        while remaining_km > 0 and current_idx < len(coords) - 1:
            next_idx = current_idx + 1
            seg_dist = haversine_km(coords[current_idx][1], coords[current_idx][0], coords[next_idx][1], coords[next_idx][0])

            if seg_dist == 0:
                current_idx = next_idx
                continue

            if remaining_km >= seg_dist:
                remaining_km -= seg_dist
                current_idx = next_idx
            else:
                # Interpolate fraction along segment
                fraction = remaining_km / seg_dist
                new_lon = coords[current_idx][0] + (coords[next_idx][0] - coords[current_idx][0]) * fraction
                new_lat = coords[current_idx][1] + (coords[next_idx][1] - coords[current_idx][1]) * fraction
                vehicle.lat = new_lat
                vehicle.lon = new_lon
                remaining_km = 0
                break

        # Check if the vehicle reached or surpassed the final coordinate
        if current_idx >= len(coords) - 1 or remaining_km > 0:
            dest_pt = coords[-1]
            vehicle.lat = dest_pt[1]
            vehicle.lon = dest_pt[0]
            vehicle.status = "IDLE"
            vehicle.current_order_id = None

            # Mark order as DELIVERED
            order.status = "DELIVERED"

            # Mark corresponding demand as FULFILLED
            if order.demand_id:
                demand = db.query(Demand).filter(Demand.id == order.demand_id).first()
                if demand:
                    demand.status = "FULFILLED"

            # Log delivery completion event
            db.add(Event(
                agent="dispatch",
                level="info",
                message=f"Order #{order.id} delivered by {vehicle.name}: {order.quantity} units of {order.item}.",
                details_json=json.dumps({"order_id": order.id, "vehicle_id": vehicle.id, "status": "DELIVERED"})
            ))

    db.commit()
