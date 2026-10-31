import json
import math
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Order, Zone, Vehicle, Camp, Event
from app.services.routing import calculate_route
from app.services.geo import point_in_zone, route_intersects_zones, haversine_km

# Calculates a safe transit route between two points, routing around active hazard zones
def compute_safe_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    zones: List
) -> Dict[str, Any]:
    active_zones = [z for z in zones if getattr(z, "active", True)]
    target_dest_lat = dest_lat
    target_dest_lon = dest_lon
    needs_air_boat_support = False

    # Check if the destination itself is located inside any active danger zone
    for z in active_zones:
        if point_in_zone(dest_lat, dest_lon, z):
            needs_air_boat_support = True
            # Route to the nearest safe staging point just outside the hazard perimeter
            dist = haversine_km(dest_lat, dest_lon, z.center_lat, z.center_lon)
            buffer_km = z.radius_km + 0.5

            if dist > 0.05:
                # Project outward from zone center through camp to safe perimeter
                ratio = buffer_km / dist
                target_dest_lat = z.center_lat + (dest_lat - z.center_lat) * ratio
                target_dest_lon = z.center_lon + (dest_lon - z.center_lon) * ratio
            else:
                # If camp is exactly at zone center, offset northward
                target_dest_lat = z.center_lat + (buffer_km / 111.32)
                target_dest_lon = z.center_lon
            break

    # Calculate optimal safe driving route
    route_result = calculate_route(origin_lat, origin_lon, target_dest_lat, target_dest_lon, active_zones)

    # Format route geometry as GeoJSON LineString dictionary string
    geojson_data = {
        "type": "LineString",
        "coordinates": route_result["geometry_coords"],
        "properties": {
            "distance_km": route_result["distance_km"],
            "duration_min": route_result["duration_min"],
            "approximate": route_result.get("approximate_route", False),
            "needs_air_boat_support": needs_air_boat_support
        }
    }

    return {
        "route_geojson": json.dumps(geojson_data),
        "distance_km": route_result["distance_km"],
        "eta_minutes": route_result["duration_min"],
        "needs_air_boat_support": needs_air_boat_support,
        "coordinates": route_result["geometry_coords"]
    }

# Evaluates an in-transit order's route against active hazard zones and recalculates if obstructed
def reroute_order(db: Session, order: Order, zones: List[Zone]) -> bool:
    if order.status != "IN_TRANSIT" or not order.route_geojson:
        return False

    try:
        route_data = json.loads(order.route_geojson)
        coords = route_data.get("coordinates", [])
    except Exception:
        return False

    # Check if the existing route intersects any currently active danger zone
    active_zones = [z for z in zones if z.active]
    if not route_intersects_zones(coords, active_zones):
        return False

    # Route is obstructed! Locate current vehicle position
    vehicle = db.query(Vehicle).filter(Vehicle.id == order.vehicle_id).first() if order.vehicle_id else None
    current_lat = vehicle.lat if vehicle else None
    current_lon = vehicle.lon if vehicle else None

    # Retrieve destination camp
    camp = db.query(Camp).join(Order, Order.demand_id == Camp.demands).first()
    if not camp:
        # Fallback to last point in route
        dest_lon, dest_lat = coords[-1]
    else:
        dest_lat, dest_lon = camp.lat, camp.lon

    if current_lat is None or current_lon is None:
        current_lon, current_lat = coords[0]

    # Compute a newly recalibrated safe path around the hazard
    new_route = compute_safe_route(current_lat, current_lon, dest_lat, dest_lon, active_zones)

    order.route_geojson = new_route["route_geojson"]
    order.distance_km = new_route["distance_km"]
    order.eta_minutes = new_route["eta_minutes"]
    order.reroute_count += 1

    msg = f"Order #{order.id} rerouted around hazard zone (Reroute #{order.reroute_count}). New ETA: {order.eta_minutes} mins."
    if new_route["needs_air_boat_support"]:
        msg += " Alert: Destination within hazard zone; staging at perimeter for air/boat support."

    db.add(Event(
        agent="routing",
        level="alert",
        message=msg,
        details_json=json.dumps({
            "order_id": order.id,
            "reroute_count": order.reroute_count,
            "new_distance_km": order.distance_km,
            "new_eta_min": order.eta_minutes,
            "needs_air_boat_support": new_route["needs_air_boat_support"]
        })
    ))
    db.commit()
    return True

