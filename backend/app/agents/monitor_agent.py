import json
from sqlalchemy.orm import Session
from app.models import Observation, Event
from app.services.weather import get_current_weather
from app.seed import MONITORING_POINTS
from app.mock import fleet_simulator

# Monitors regional weather telemetry and advances fleet vehicle positions
def run(db: Session):
    observations_recorded = 0
    high_rain_points = []

    # 1. Fetch weather telemetry for each designated regional point
    for pt in MONITORING_POINTS:
        weather = get_current_weather(pt["lat"], pt["lon"])
        if weather:
            obs = Observation(
                lat=pt["lat"],
                lon=pt["lon"],
                rain_mm=weather["rain_mm"],
                wind_kmh=weather["wind_kmh"]
            )
            db.add(obs)
            observations_recorded += 1

            if weather["rain_mm"] > 5.0:
                high_rain_points.append(f"{pt['name']} ({weather['rain_mm']} mm/h)")

    # 2. Advance fleet simulator step for all trucks in transit
    fleet_simulator.step(db)

    # 3. Log monitor agent activity event
    if high_rain_points:
        level = "warn"
        msg = f"Heavy precipitation detected at: {', '.join(high_rain_points)}."
    else:
        level = "info"
        msg = f"Monitored {observations_recorded} weather stations. Fleet telemetry synchronized."

    event = Event(
        agent="monitor",
        level=level,
        message=msg,
        details_json=json.dumps({"stations_checked": len(MONITORING_POINTS), "observations_recorded": observations_recorded})
    )
    db.add(event)
    db.commit()

    return {"observations_recorded": observations_recorded, "high_rain_points": high_rain_points}
