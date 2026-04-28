"""Contracts — Buy / Sell / Barter."""
from typing import Optional
from pydantic import BaseModel
from core.crud import make_crud_router


class ContractCreate(BaseModel):
    type: str  # buy | sell | barter
    client_id: str
    client_name: Optional[str] = None
    product_id: str
    product_name: Optional[str] = None
    volume: float
    unit: str = "ton"
    price: float = 0
    currency: str = "BRL"
    signed_at: Optional[str] = None
    delivery_window: Optional[str] = None
    barter_ratio: Optional[float] = None  # ton de grão por ton de insumo
    counter_product_id: Optional[str] = None
    status: str = "draft"  # draft | active | settled | cancelled
    notes: Optional[str] = None


class ContractUpdate(BaseModel):
    type: Optional[str] = None
    volume: Optional[float] = None
    price: Optional[float] = None
    status: Optional[str] = None
    delivery_window: Optional[str] = None
    notes: Optional[str] = None


router = make_crud_router(
    "contracts", ContractCreate, ContractUpdate,
    search_fields=["client_name", "product_name"],
)
