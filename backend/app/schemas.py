from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel

# Inventory schemas
class InventoryBase(BaseModel):
    item: str
    quantity: int

class InventoryOut(InventoryBase):
    id: int
    warehouse_id: int

    class Config:
        from_attributes = True

# Warehouse schemas
class WarehouseOut(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    reliability: float
    inventory: List[InventoryOut] = []

    class Config:
        from_attributes = True

# Camp schemas
class CampOut(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    population: int

    class Config:
        from_attributes = True

# Demand schemas
class DemandCreate(BaseModel):
    camp_id: int
    item: str
    quantity: int
    priority: int = 3

class DemandOut(BaseModel):
    id: int
    camp_id: int
    item: str
    quantity: int
    priority: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

# Vehicle schemas
class VehicleOut(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    capacity: int
    status: str
    current_order_id: Optional[int] = None
    driver_telegram_chat_id: Optional[str] = None

    class Config:
        from_attributes = True

# Hazard Zone schemas
class ZoneCreate(BaseModel):
    name: Optional[str] = "Simulated Hazard Zone"
    lat: float
    lon: float
    radius_km: float = 3.0
    severity: int = 3
    source: str = "simulated"

class ZoneGrow(BaseModel):
    zone_id: int
    extra_km: float = 2.0

class ZoneOut(BaseModel):
    id: int
    name: str
    center_lat: float
    center_lon: float
    radius_km: float
    severity: int
    source: str
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Order schemas
class OrderOut(BaseModel):
    id: int
    demand_id: int
    warehouse_id: int
    vehicle_id: Optional[int]
    item: str
    quantity: int
    status: str
    route_geojson: Optional[str] = None
    distance_km: float
    eta_minutes: float
    reroute_count: int
    ai_reasoning: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# Event schemas
class EventOut(BaseModel):
    id: int
    timestamp: datetime
    agent: str
    level: str
    message: str
    details_json: Optional[str] = None

    class Config:
        from_attributes = True

# System KPI schema
class AutoDispatchSetting(BaseModel):
    enabled: bool

class KpiOut(BaseModel):
    active_zones: int
    open_demands: int
    orders_in_transit: int
    delivered_orders: int
    total_reroutes: int
    auto_dispatch: bool
    fallback_mode: bool
    satellite_mode: str = "SAMPLE"
    satellite_flooded_km2: float = 0.0
    satellite_data_age_hours: Optional[float] = None

# Comprehensive state bundle for frontend polling
class StateResponse(BaseModel):
    warehouses: List[WarehouseOut]
    camps: List[CampOut]
    vehicles: List[VehicleOut]
    zones: List[ZoneOut]
    demands: List[DemandOut]
    orders: List[OrderOut]
    kpis: KpiOut
    events: List[EventOut]


class SatelliteFloodResponse(BaseModel):
    polygons: dict
    flooded_km2: float
    scene_dates: List[str]
    scene_ids: List[str]
    data_age_hours: Optional[float] = None
    mode: str
    status: str = "ok"
    message: Optional[str] = None


class FloodRiskScoreOut(BaseModel):
    name: str
    lat: float
    lon: float
    score: float
    level: str
    explanation: List[str]
    affected_population: int = 0
    source: str = "heuristic risk score"


class WarehouseSiteOut(BaseModel):
    rank: int
    name: str
    address: Optional[str] = None
    lat: float
    lon: float
    osm_link: Optional[str] = None
    score: float
    reason: str
    status: str = "decision support"


class WarehouseSitesResponse(BaseModel):
    status: str
    decision_support: bool = True
    human_verification_required: bool = True
    sites: List[WarehouseSiteOut] = []
    message: Optional[str] = None

