import json
import logging
from sqlalchemy.orm import Session
from app.config import settings
from app.models import Zone, Demand, Order, Event
from app.agents import monitor_agent, risk_agent, inventory_agent, dispatch_agent, routing_agent
from app.services import llm

logger = logging.getLogger("orchestrator")

# Executes one complete autonomous swarm cycle coordinating all specialized agents in sequence
def run_cycle(db: Session) -> dict:
    stats = {
        "monitor": {},
        "risk": {},
        "inventory_count": 0,
        "reroutes_count": 0,
        "sitrep": ""
    }

    # 1. MONITOR AGENT: Track weather and fleet progression
    try:
        stats["monitor"] = monitor_agent.run(db)
    except Exception as e:
        logger.error(f"Monitor agent error: {e}")
        db.add(Event(agent="orchestrator", level="warn", message=f"Monitor agent warning: {str(e)[:100]}"))
        db.commit()

    # 2. RISK AGENT: Map hazards and generate prioritized relief demands
    try:
        stats["risk"] = risk_agent.run(db)
    except Exception as e:
        logger.error(f"Risk agent error: {e}")
        db.add(Event(agent="orchestrator", level="warn", message=f"Risk agent warning: {str(e)[:100]}"))
        db.commit()

    # 3. INVENTORY AGENT: Query stock, reason over candidate warehouses, reserve supplies
    inventory_res = []
    try:
        inventory_res = inventory_agent.run(db)
        stats["inventory_count"] = len(inventory_res)
    except Exception as e:
        logger.error(f"Inventory agent error: {e}")
        db.add(Event(agent="orchestrator", level="warn", message=f"Inventory agent warning: {str(e)[:100]}"))
        db.commit()

    # 4. DISPATCH AGENT: Match trucks, compute safe routes, dispatch orders
    try:
        if inventory_res:
            dispatch_agent.run(db, inventory_res)
    except Exception as e:
        logger.error(f"Dispatch agent error: {e}")
        db.add(Event(agent="orchestrator", level="warn", message=f"Dispatch agent warning: {str(e)[:100]}"))
        db.commit()

    # 5. DYNAMIC RE-ROUTING: Inspect in-transit orders for newly obstructing hazard zones
    try:
        active_zones = db.query(Zone).filter(Zone.active == True).all()
        in_transit_orders = db.query(Order).filter(Order.status == "IN_TRANSIT").all()
        for order in in_transit_orders:
            if routing_agent.reroute_order(db, order, active_zones):
                stats["reroutes_count"] += 1
    except Exception as e:
        logger.error(f"Rerouting error: {e}")
        db.add(Event(agent="orchestrator", level="warn", message=f"Rerouting warning: {str(e)[:100]}"))
        db.commit()

    # 6. SITUATION REPORT (LLM generated with fallback)
    active_zones_cnt = db.query(Zone).filter(Zone.active == True).count()
    open_demands_cnt = db.query(Demand).filter(Demand.status == "OPEN").count()
    in_transit_cnt = db.query(Order).filter(Order.status == "IN_TRANSIT").count()
    delivered_cnt = db.query(Order).filter(Order.status == "DELIVERED").count()

    system_prompt = (
        "You are the Lead Swarm Orchestrator. Provide a single, professional one-sentence situation report "
        "summarizing the current emergency logistics state."
    )
    payload = {
        "active_zones": active_zones_cnt,
        "open_demands": open_demands_cnt,
        "in_transit_orders": in_transit_cnt,
        "delivered_orders": delivered_cnt,
        "reroutes_this_cycle": stats["reroutes_count"]
    }

    try:
        llm_reply = llm.ask_json(system_prompt, payload)
        sitrep = llm_reply.get("reasoning") or llm_reply.get("sitrep") or ""
        if not sitrep or len(sitrep) < 10:
            sitrep = (
                f"Swarm cycle completed: {active_zones_cnt} active hazard zones, {in_transit_cnt} orders in transit, "
                f"{open_demands_cnt} open demands pending fulfillment."
            )
    except Exception:
        sitrep = (
            f"Swarm cycle completed: {active_zones_cnt} active hazard zones, {in_transit_cnt} orders in transit, "
            f"{open_demands_cnt} open demands."
        )

    stats["sitrep"] = sitrep

    # Write orchestrator summary event if hazards or active operations exist
    if active_zones_cnt > 0 or in_transit_cnt > 0 or open_demands_cnt > 0:
        db.add(Event(
            agent="orchestrator",
            level="info",
            message=sitrep,
            details_json=json.dumps(payload)
        ))
        db.commit()

    return stats
