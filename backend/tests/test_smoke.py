import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import SessionLocal, init_db
from app.seed import seed_database

# Pytest fixture to initialize clean test database with seed data
@pytest.fixture(scope="module", autouse=True)
def setup_database():
    init_db()
    db = SessionLocal()
    seed_database(db, force_reset=True)
    db.close()
    yield

# Test 1: Verify health check endpoint returns 200 and ok status
def test_health():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

# Test 2: Verify system state endpoint returns seeded entities and KPIs
def test_initial_state():
    client = TestClient(app)
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["warehouses"]) == 3
    assert len(data["camps"]) == 3
    assert len(data["vehicles"]) == 6
    assert data["kpis"]["active_zones"] == 0

# Test 3: Verify mock supplier inventory API returns stock availability
def test_supplier_inventory():
    client = TestClient(app)
    resp = client.get("/mock/suppliers/inventory?item=food_kits")
    assert resp.status_code == 200
    stocks = resp.json()
    assert len(stocks) == 3
    assert any(s["available_quantity"] > 0 for s in stocks)

# Test 4: Full pipeline smoke test (Flood -> Demand -> LLM Inventory -> Route -> Dispatch -> Approval)
def test_flood_to_order_pipeline():
    client = TestClient(app)

    # 1. Trigger flood near Paradeep (Odisha coastal delta)
    flood_payload = {
        "name": "Paradeep Delta Flood",
        "lat": 20.3160,
        "lon": 86.6114,
        "radius_km": 4.0,
        "severity": 4
    }
    flood_resp = client.post("/api/simulate/flood", json=flood_payload)
    assert flood_resp.status_code == 200
    zone_data = flood_resp.json()
    assert zone_data["active"] is True

    # 2. Execute autonomous cycle
    cycle_resp = client.post("/api/cycle/run")
    assert cycle_resp.status_code == 200

    # 3. Verify state has created demands and orders
    state_resp = client.get("/api/state")
    state_data = state_resp.json()
    assert state_data["kpis"]["active_zones"] >= 1
    assert len(state_data["orders"]) >= 1

    first_order = state_data["orders"][0]
    assert first_order["status"] == "PENDING_APPROVAL"
    assert first_order["vehicle_id"] is not None
    assert first_order["warehouse_id"] is not None
    assert first_order["distance_km"] > 0
    assert len(first_order["ai_reasoning"]) > 0

    # 4. Operator approves the order
    approve_resp = client.post(f"/api/orders/{first_order['id']}/approve")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "IN_TRANSIT"
