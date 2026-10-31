from sqlalchemy.orm import Session
from app.models import Warehouse, Inventory, Camp, Vehicle, Zone, Demand, Order, Event, Observation

# Pre-defined geographic coordinates for monitoring in Odisha's flood & cyclone belt
MONITORING_POINTS = [
    {"name": "Bhubaneswar", "lat": 20.2961, "lon": 85.8245},
    {"name": "Cuttack", "lat": 20.4625, "lon": 85.8828},
    {"name": "Puri", "lat": 19.8135, "lon": 85.8312},
    {"name": "Paradeep", "lat": 20.3160, "lon": 86.6114},
    {"name": "Kendrapara", "lat": 20.5000, "lon": 86.4200},
    {"name": "Balasore", "lat": 21.4934, "lon": 86.9135},
]

# Populates the database with initial demo warehouses, camps, vehicles, and stock in Odisha
def seed_database(db: Session, force_reset: bool = False):
    # If resetting, clear existing data
    if force_reset:
        db.query(Observation).delete()
        db.query(Event).delete()
        db.query(Order).delete()
        db.query(Demand).delete()
        db.query(Zone).delete()
        db.query(Vehicle).delete()
        db.query(Inventory).delete()
        db.query(Camp).delete()
        db.query(Warehouse).delete()
        db.commit()

    # Check if database already has warehouses
    if db.query(Warehouse).first():
        return

    # 1. Create Warehouses across Odisha
    warehouses_data = [
        {"name": "Bhubaneswar Central Hub", "lat": 20.2961, "lon": 85.8245, "reliability": 0.95},
        {"name": "Cuttack Mahanadi Depot", "lat": 20.4625, "lon": 85.8828, "reliability": 0.88},
        {"name": "Berhampur Southern Hub", "lat": 19.3150, "lon": 84.7941, "reliability": 0.92},
    ]

    warehouses = []
    for w in warehouses_data:
        wh = Warehouse(**w)
        db.add(wh)
        warehouses.append(wh)
    db.commit()

    # 2. Add Inventory per Warehouse
    # Varied stock levels to showcase intelligent supplier choice in demos
    inventory_data = {
        "Bhubaneswar Central Hub": [
            ("food_kits", 350),
            ("water_liters", 1500),
            ("medical_kits", 80),
            ("blankets", 300),
        ],
        "Cuttack Mahanadi Depot": [
            ("food_kits", 120),  # Closer to flood delta, but limited food
            ("water_liters", 400),
            ("medical_kits", 300),  # High medical kits
            ("blankets", 150),
        ],
        "Berhampur Southern Hub": [
            ("food_kits", 2000),  # Ample stock, but further away
            ("water_liters", 5000),
            ("medical_kits", 800),
            ("blankets", 1200),
        ],
    }

    for wh in warehouses:
        for item, qty in inventory_data.get(wh.name, []):
            inv = Inventory(warehouse_id=wh.id, item=item, quantity=qty)
            db.add(inv)
    db.commit()

    # 3. Create Coastal & Delta Relief Camps in Odisha
    camps_data = [
        {"name": "Puri Cyclone Shelter", "lat": 19.8135, "lon": 85.8312, "population": 1500},
        {"name": "Paradeep Coastal Shelter", "lat": 20.3160, "lon": 86.6114, "population": 1200},
        {"name": "Kendrapara Flood Camp", "lat": 20.5000, "lon": 86.4200, "population": 800},
    ]

    for c in camps_data:
        camp = Camp(**c)
        db.add(camp)
    db.commit()

    # 4. Create Fleet Vehicles (2 per warehouse)
    vehicles_data = [
        {"name": "Truck Alpha", "lat": 20.2961, "lon": 85.8245, "capacity": 500},
        {"name": "Truck Beta", "lat": 20.2961, "lon": 85.8245, "capacity": 500},
        {"name": "Truck Gamma", "lat": 20.4625, "lon": 85.8828, "capacity": 500},
        {"name": "Truck Delta", "lat": 20.4625, "lon": 85.8828, "capacity": 500},
        {"name": "Truck Epsilon", "lat": 19.3150, "lon": 84.7941, "capacity": 500},
        {"name": "Truck Zeta", "lat": 19.3150, "lon": 84.7941, "capacity": 500},
    ]

    for v in vehicles_data:
        vehicle = Vehicle(**v, status="IDLE")
        db.add(vehicle)
    db.commit()

    # 5. Add Initial Orchestrator Event
    event = Event(
        agent="orchestrator",
        level="info",
        message="System seeded with Odisha Disaster Management Corridor data.",
        details_json='{"status": "initialized", "region": "Odisha Disaster Corridor, India"}'
    )
    db.add(event)
    db.commit()
