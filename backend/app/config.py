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

    # Database and network
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./resqchain.db")
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")

# Single settings instance used across the app
settings = Settings()

