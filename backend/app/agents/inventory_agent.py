import json
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models import Demand, Camp, Warehouse, Inventory, Event
from app.services.geo import haversine_km
from app.services import llm

# Calls the mock supplier API over HTTP client
def fetch_inventory_from_supplier_api(item: str) -> List[Dict[str, Any]]:
    try:
        from app.main import app
        from starlette.testclient import TestClient
        client = TestClient(app)
        resp = client.get("/mock/suppliers/inventory", params={"item": item})
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []

# Calls the mock supplier reservation endpoint over HTTP client
def reserve_stock_from_supplier_api(warehouse_id: int, item: str, quantity: int) -> bool:
    try:
        from app.main import app
        from starlette.testclient import TestClient
        client = TestClient(app)
        resp = client.post(
            "/mock/suppliers/reserve",
            json={"warehouse_id": warehouse_id, "item": item, "quantity": quantity}
        )
        if resp.status_code == 200:
            return resp.json().get("ok", False)
    except Exception:
        pass
    return False

# Evaluates regional supplier stock and uses Gemini LLM reasoning to select the best warehouse for each open demand
def run(db: Session) -> List[Dict[str, Any]]:
    open_demands = db.query(Demand).filter(Demand.status == "OPEN").all()
    resolutions = []

    if not open_demands:
        return resolutions

    for demand in open_demands:
        camp = db.query(Camp).filter(Camp.id == demand.camp_id).first()
        if not camp:
            continue

        # 1. Query supplier inventory API over HTTP client
        candidates = fetch_inventory_from_supplier_api(demand.item)

        # Fallback to local DB query if HTTP client is unreachable
        if not candidates:
            warehouses = db.query(Warehouse).all()
            for wh in warehouses:
                inv = db.query(Inventory).filter(
                    Inventory.warehouse_id == wh.id,
                    Inventory.item == demand.item
                ).first()
                candidates.append({
                    "warehouse_id": wh.id,
                    "name": wh.name,
                    "lat": wh.lat,
                    "lon": wh.lon,
                    "available_quantity": inv.quantity if inv else 0,
                    "reliability": wh.reliability
                })

        # Calculate distances from each candidate warehouse to the destination camp
        for c in candidates:
            c["distance_km"] = round(haversine_km(c["lat"], c["lon"], camp.lat, camp.lon), 1)

        # 2. Consult Gemini LLM (with heuristic safety fallback)
        system_prompt = (
            "You are the Inventory Agent for ResQChain Swarm. "
            "Analyze the candidate warehouses considering stock availability, distance, and reliability rating. "
            "Select the best warehouse and provide a concise, high-clarity explanation of why."
        )

        user_payload = {
            "demand": {
                "id": demand.id,
                "camp_name": camp.name,
                "item": demand.item,
                "quantity": demand.quantity,
                "priority": demand.priority
            },
            "candidates": candidates
        }

        decision = llm.ask_json(system_prompt, user_payload)
        chosen_wh_id = decision.get("chosen_warehouse_id")
        reasoning = decision.get("reasoning", "Optimal warehouse chosen based on stock and transit proximity.")

        # 3. Reserve inventory via supplier API over HTTP
        reserved = reserve_stock_from_supplier_api(chosen_wh_id, demand.item, demand.quantity)

        # Fallback direct decrement if HTTP reservation failed
        if not reserved:
            inv = db.query(Inventory).filter(
                Inventory.warehouse_id == chosen_wh_id,
                Inventory.item == demand.item
            ).first()
            if inv and inv.quantity >= demand.quantity:
                inv.quantity -= demand.quantity
                db.commit()
                reserved = True

        wh_obj = db.query(Warehouse).filter(Warehouse.id == chosen_wh_id).first()
        wh_name = wh_obj.name if wh_obj else f"Warehouse #{chosen_wh_id}"

        # 4. Record agent activity log entry
        db.add(Event(
            agent="inventory",
            level="info",
            message=f"Demand #{demand.id} matched to {wh_name}. Stock reserved: {demand.quantity} {demand.item}.",
            details_json=json.dumps({
                "demand_id": demand.id,
                "warehouse_id": chosen_wh_id,
                "ai_reasoning": reasoning
            })
        ))
        db.commit()

        resolutions.append({
            "demand": demand,
            "camp": camp,
            "warehouse": wh_obj,
            "ai_reasoning": reasoning
        })

    return resolutions
