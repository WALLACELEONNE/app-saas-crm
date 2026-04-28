"""Logistics — Vehicles and Cargas (loads)."""
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel
from core.crud import make_crud_router


class VehicleCreate(BaseModel):
    plate: str
    type: str = "bitrem"
    capacity_ton: float = 30
    status: str = "available"  # available | loading | en_route | maintenance


class VehicleUpdate(BaseModel):
    plate: Optional[str] = None
    type: Optional[str] = None
    capacity_ton: Optional[float] = None
    status: Optional[str] = None


class CargaCreate(BaseModel):
    order_id: Optional[str] = None
    vehicle_plate: str
    driver: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    status: str = "queue"  # queue | loading | in_transit | delivered


class CargaUpdate(BaseModel):
    status: Optional[str] = None
    driver: Optional[str] = None
    destination: Optional[str] = None


router = APIRouter()
router.include_router(make_crud_router("vehicles", VehicleCreate, VehicleUpdate,
                                       search_fields=["plate"]),
                      prefix="/vehicles")
router.include_router(make_crud_router("cargas", CargaCreate, CargaUpdate,
                                       search_fields=["vehicle_plate", "driver", "destination"]),
                      prefix="/cargas")
