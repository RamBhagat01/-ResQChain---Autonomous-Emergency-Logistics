import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.config import settings
from app.models import Zone, Camp, Demand, Vehicle, Observation, Event
from app.services.geo import haversine_km

# Evaluates danger zones from weather observations and triggers emergency supply demands for affected camps
def run(db: Session):
    active_zones = db.query(Zone).filter(Zone.active == True).all()

    # 1. Process recent weather observations to create weather-triggered zones
    cutoff = datetime.utcnow() - timedelta(minutes=15)
    recent_obs = db.query(Observation).filter(Observation.timestamp >= cutoff).all()

    for obs in recent_obs:
        if obs.rain_mm >= settings.RAIN_THRESHOLD_MM:
            # Check if an active zone already covers this location
            existing = any(
                z.active and haversine_km(obs.lat, obs.lon, z.center_lat, z.center_lon) <= z.radius_km
                for z in active_zones
            )
            if not existing:
                new_zone = Zone(
                    name=f"Heavy Rain Danger Zone ({obs.rain_mm:.1f} mm/h)",
                    center_lat=obs.lat,
                    center_lon=obs.lon,
                    radius_km=settings.MAX_ZONE_RADIUS_KM,
                    severity=min(5, max(2, int(obs.rain_mm / 5.0))),
                    source="weather",
                    active=True
                )
                db.add(new_zone)
                db.commit()
                active_zones.append(new_zone)

    # 2. Deactivate weather zones older than ZONE_TTL_MINUTES (keep manual simulated zones active until cleared)
    ttl_cutoff = datetime.utcnow() - timedelta(minutes=settings.ZONE_TTL_MINUTES)
    for z in active_zones:
        if z.source == "weather" and z.created_at < ttl_cutoff:
            z.active = False
            db.commit()

    # Refresh list of currently active zones
    active_zones = db.query(Zone).filter(Zone.active == True).all()

    # 3. Assess impact on relief camps and generate emergency supply demands
    camps = db.query(Camp).all()
    new_demands_count = 0
    affected_camps = []

    for camp in camps:
        # Check if camp is inside or within 3 km of any active danger zone
        nearby_zones = [
            z for z in active_zones
            if haversine_km(camp.lat, camp.lon, z.center_lat, z.center_lon) <= (z.radius_km + 3.0)
        ]

        if nearby_zones:
            affected_camps.append(camp.name)
            highest_severity = max(z.severity for z in nearby_zones)

            # Essential emergency relief supplies
            required_items = [
                ("food_kits", max(50, int(camp.population * 0.2))),
                ("water_liters", max(200, int(camp.population * 0.5))),
                ("medical_kits", max(10, highest_severity * 15)),
            ]

            for item_name, qty in required_items:
                # Avoid duplicate open demands for the same camp and item
                existing_demand = db.query(Demand).filter(
                    Demand.camp_id == camp.id,
                    Demand.item == item_name,
                    Demand.status.in_(["OPEN", "ASSIGNED"])
                ).first()

                if not existing_demand:
                    demand = Demand(
                        camp_id=camp.id,
                        item=item_name,
                        quantity=qty,
                        priority=highest_severity,
                        status="OPEN"
                    )
                    db.add(demand)
                    new_demands_count += 1

    # 4. Identify vehicles located inside danger zones
    vehicles = db.query(Vehicle).all()
    trapped_vehicles = []
    for v in vehicles:
        for z in active_zones:
            if haversine_km(v.lat, v.lon, z.center_lat, z.center_lon) <= z.radius_km:
                trapped_vehicles.append(v.name)
                break

    db.commit()

    # 5. Log risk assessment summary event
    if active_zones:
        level = "alert" if new_demands_count > 0 else "warn"
        msg = f"Risk assessment: {len(active_zones)} active danger zones. Affected camps: {len(affected_camps)}. Created {new_demands_count} new demands."
    else:
        level = "info"
        msg = "Risk assessment: No active hazard zones detected. Regional conditions normal."

    event = Event(
        agent="risk",
        level=level,
        message=msg,
        details_json=json.dumps({
            "active_zones": len(active_zones),
            "affected_camps": affected_camps,
            "new_demands": new_demands_count,
            "trapped_vehicles": trapped_vehicles
        })
    )
    db.add(event)
    db.commit()

    return {
        "active_zones": len(active_zones),
        "affected_camps": affected_camps,
        "new_demands_count": new_demands_count,
        "trapped_vehicles": trapped_vehicles
    }

