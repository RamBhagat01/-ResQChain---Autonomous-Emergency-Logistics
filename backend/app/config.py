import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the .env file from workspace root or backend dir
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configuration settings with safe defaults
class Settings:
    # LLM settings
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Routing: OSRM public demo server — no API key required
    OSRM_BASE_URL: str = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org/route/v1/driving")

    # Copernicus GloFAS (Global Flood Awareness System) API Key
    COPERNICUS_GLOFAS_API_KEY: str = os.getenv("COPERNICUS_GLOFAS_API_KEY", "")

    # Alerting settings
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Swarm behaviour
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")
    AUTO_DISPATCH: bool = os.getenv("AUTO_DISPATCH", "false").lower() in ("true", "1", "yes")
    CYCLE_SECONDS: int = int(os.getenv("CYCLE_SECONDS", "10"))
    RAIN_THRESHOLD_MM: float = float(os.getenv("RAIN_THRESHOLD_MM", "7.5"))
    MAX_ZONE_RADIUS_KM: float = float(os.getenv("MAX_ZONE_RADIUS_KM", "5"))
    ZONE_TTL_MINUTES: int = int(os.getenv("ZONE_TTL_MINUTES", "60"))
    SIM_SPEED_KM_PER_STEP: float = float(os.getenv("SIM_SPEED_KM_PER_STEP", "3"))

    # Satellite flood observation. ``sample`` is deterministic and works offline.
    SATELLITE_MODE: str = os.getenv("SATELLITE_MODE", "sample").lower()
    SATELLITE_REFRESH_HOURS: int = int(os.getenv("SATELLITE_REFRESH_HOURS", "6"))
    SATELLITE_EVENT_WINDOW_DAYS: int = int(os.getenv("SATELLITE_EVENT_WINDOW_DAYS", "12"))
    SATELLITE_REFERENCE_DAYS: int = int(os.getenv("SATELLITE_REFERENCE_DAYS", "90"))
    SATELLITE_VV_THRESHOLD_DB: float = float(os.getenv("SATELLITE_VV_THRESHOLD_DB", "-18"))
    SATELLITE_VV_DROP_DB: float = float(os.getenv("SATELLITE_VV_DROP_DB", "-3"))
    SATELLITE_MIN_BLOB_AREA_KM2: float = float(os.getenv("SATELLITE_MIN_BLOB_AREA_KM2", "0.02"))
    SATELLITE_TARGET_RESOLUTION_M: int = int(os.getenv("SATELLITE_TARGET_RESOLUTION_M", "50"))
    SATELLITE_TILE_DEGREES: float = float(os.getenv("SATELLITE_TILE_DEGREES", "0.35"))

    # Transparent heuristic flood-risk weights. They are intentionally not ML claims.
    RISK_WEIGHT_SATELLITE: float = float(os.getenv("RISK_WEIGHT_SATELLITE", "0.35"))
    RISK_WEIGHT_RAIN: float = float(os.getenv("RISK_WEIGHT_RAIN", "0.25"))
    RISK_WEIGHT_RIVER: float = float(os.getenv("RISK_WEIGHT_RIVER", "0.20"))
    RISK_WEIGHT_TERRAIN: float = float(os.getenv("RISK_WEIGHT_TERRAIN", "0.10"))
    RISK_WEIGHT_HISTORY: float = float(os.getenv("RISK_WEIGHT_HISTORY", "0.10"))
    RELIEF_DAYS: int = int(os.getenv("RELIEF_DAYS", "3"))
    FOOD_KITS_PER_PERSON: float = float(os.getenv("FOOD_KITS_PER_PERSON", "0.25"))
    WATER_LITERS_PER_PERSON: float = float(os.getenv("WATER_LITERS_PER_PERSON", "15"))
    BLANKETS_PER_PERSON: float = float(os.getenv("BLANKETS_PER_PERSON", "1"))
    MEDICAL_KITS_PER_PERSON: float = float(os.getenv("MEDICAL_KITS_PER_PERSON", "0.02"))
    PREDICTED_ZONE_TTL_HOURS: int = int(os.getenv("PREDICTED_ZONE_TTL_HOURS", "24"))

    # Database and network
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./resqchain.db")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")

# Single settings instance used across the app
settings = Settings()

