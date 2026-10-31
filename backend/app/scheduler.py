import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.db import SessionLocal
from app.agents import orchestrator

logger = logging.getLogger("scheduler")

# Background scheduler instance for autonomous recurring swarm cycles
scheduler = AsyncIOScheduler()

# Function triggered by the scheduler every CYCLE_SECONDS
def scheduled_swarm_cycle():
    db = SessionLocal()
    try:
        orchestrator.run_cycle(db)
    except Exception as e:
        logger.error(f"Error during scheduled swarm cycle: {e}")
    finally:
        db.close()

# Starts the autonomous background swarm scheduler
def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(
            scheduled_swarm_cycle,
            "interval",
            seconds=settings.CYCLE_SECONDS,
            id="swarm_autonomous_loop",
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"Swarm scheduler started. Running cycle every {settings.CYCLE_SECONDS}s.")

# Safely shuts down the scheduler on server stop
def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Swarm scheduler stopped.")
