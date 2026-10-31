import httpx
from typing import Optional, Dict

# Fetches live precipitation and wind speed from the free Open-Meteo weather API
def get_current_weather(lat: float, lon: float) -> Optional[Dict[str, float]]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "precipitation,rain,wind_speed_10m",
        "timezone": "auto"
    }

    try:
        # 4-second timeout to ensure the swarm cycle is never blocked by slow network
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json().get("current", {})
                rain = float(data.get("rain", data.get("precipitation", 0.0)) or 0.0)
                wind = float(data.get("wind_speed_10m", 0.0) or 0.0)
                return {"rain_mm": rain, "wind_kmh": wind}
    except Exception:
        # Fallback gracefully if internet or weather API is temporarily unreachable
        return None

    return None
