from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base

# Warehouse facility storing relief items
class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    reliability = Column(Float, default=0.9)  # Score between 0 and 1

    # Relations
    inventory = relationship("Inventory", back_populates="warehouse", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="warehouse")

# Inventory items stored at each warehouse
class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    item = Column(String, nullable=False)  # food_kits, water_liters, medical_kits, blankets
    quantity = Column(Integer, default=0)

    # Relations
    warehouse = relationship("Warehouse", back_populates="inventory")

# Relief camp or community center needing supplies
class Camp(Base):
    __tablename__ = "camps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    population = Column(Integer, default=500)

    # Relations
    demands = relationship("Demand", back_populates="camp", cascade="all, delete-orphan")

# Supply requests raised for a specific camp
class Demand(Base):
    __tablename__ = "demands"

    id = Column(Integer, primary_key=True, index=True)
    camp_id = Column(Integer, ForeignKey("camps.id"), nullable=False)
    item = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    priority = Column(Integer, default=3)  # 1 (lowest) to 5 (highest/critical)
    status = Column(String, default="OPEN")  # OPEN, ASSIGNED, FULFILLED
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    camp = relationship("Camp", back_populates="demands")
    orders = relationship("Order", back_populates="demand")

# Delivery trucks and transport vehicles
class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    capacity = Column(Integer, default=500)
    status = Column(String, default="IDLE")  # IDLE, ASSIGNED, IN_TRANSIT
    current_order_id = Column(Integer, nullable=True)
    driver_telegram_chat_id = Column(String, nullable=True)

    # Relations
    orders = relationship("Order", back_populates="vehicle")

# Flood, storm, or danger zones to be avoided
class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    center_lat = Column(Float, nullable=False)
    center_lon = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False)
    severity = Column(Integer, default=3)  # 1 to 5
    source = Column(String, default="simulated")  # weather, simulated, gdacs
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# Dispatch orders linking demand, warehouse, vehicle, and safe route
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    demand_id = Column(Integer, ForeignKey("demands.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    item = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String, default="PENDING_APPROVAL")  # PENDING_APPROVAL, DISPATCHED, IN_TRANSIT, DELIVERED, FAILED, CANCELLED
    route_geojson = Column(Text, nullable=True)  # JSON string of GeoJSON LineString coordinates
    distance_km = Column(Float, default=0.0)
    eta_minutes = Column(Float, default=0.0)
    reroute_count = Column(Integer, default=0)
    ai_reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    demand = relationship("Demand", back_populates="orders")
    warehouse = relationship("Warehouse", back_populates="orders")
    vehicle = relationship("Vehicle", back_populates="orders")

# Swarm agent activity log entries
class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    agent = Column(String, nullable=False)  # monitor, risk, inventory, routing, dispatch, orchestrator
    level = Column(String, default="info")  # info, warn, alert
    message = Column(String, nullable=False)
    details_json = Column(Text, nullable=True)

# Meteorological observations recorded per monitoring point
class Observation(Base):
    __tablename__ = "observations"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    rain_mm = Column(Float, default=0.0)
    wind_kmh = Column(Float, default=0.0)

