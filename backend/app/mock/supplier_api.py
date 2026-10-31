import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Warehouse, Inventory

router = APIRouter(prefix="/mock/suppliers", tags=["Mock Supplier API"])

# Response schema for warehouse inventory item
class SupplierWarehouseStock(BaseModel):
    warehouse_id: int
    name: str
    lat: float
    lon: float
    available_quantity: int
    reliability: float

# Request schema for inventory reservation
class ReservationRequest(BaseModel):
    warehouse_id: int
    item: str
    quantity: int

# Response schema for reservation result
class ReservationResponse(BaseModel):
    reservation_id: Optional[str] = None
    ok: bool
    remaining_quantity: Optional[int] = None
    message: Optional[str] = None

# Query available stock for a specific item across all partner warehouses
@router.get("/inventory", response_model=List[SupplierWarehouseStock])
def get_inventory(item: str = Query(..., description="Item type: food_kits, water_liters, medical_kits, blankets"), db: Session = Depends(get_db)):
    warehouses = db.query(Warehouse).all()
    results = []

    for wh in warehouses:
        # Find inventory for requested item in this warehouse
        inv = db.query(Inventory).filter(
            Inventory.warehouse_id == wh.id,
            Inventory.item == item
        ).first()

        qty = inv.quantity if inv else 0
        results.append(
            SupplierWarehouseStock(
                warehouse_id=wh.id,
                name=wh.name,
                lat=wh.lat,
                lon=wh.lon,
                available_quantity=qty,
                reliability=wh.reliability,
            )
        )

    return results

# Reserve and decrement inventory stock when an order is confirmed
@router.post("/reserve", response_model=ReservationResponse)
def reserve_inventory(req: ReservationRequest, db: Session = Depends(get_db)):
    inv = db.query(Inventory).filter(
        Inventory.warehouse_id == req.warehouse_id,
        Inventory.item == req.item
    ).first()

    if not inv or inv.quantity < req.quantity:
        return ReservationResponse(
            ok=False,
            message=f"Insufficient inventory for {req.item}. Available: {inv.quantity if inv else 0}"
        )

    # Decrement warehouse stock
    inv.quantity -= req.quantity
    db.commit()

    return ReservationResponse(
        reservation_id=f"res-{uuid.uuid4().hex[:8]}",
        ok=True,
        remaining_quantity=inv.quantity,
        message="Stock successfully reserved."
    )
