"""Orders — Sale and Purchase orders with logistic status."""
from typing import Optional
from pydantic import BaseModel, Field
from core.crud import make_crud_router


class OrderItem(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    volume: float
    unit: str = "ton"
    price: float = 0


class OrderCreate(BaseModel):
    type: str  # sale | purchase
    contract_id: Optional[str] = None
    client_id: str
    client_name: Optional[str] = None
    items: list[OrderItem] = Field(default_factory=list)
    total: float = 0
    currency: str = "BRL"
    status: str = "pending"  # pending | confirmed | in_transit | delivered | cancelled
    logistic_status: str = "queue"  # queue | loading | in_transit | delivered
    notes: Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[str] = None
    logistic_status: Optional[str] = None
    items: Optional[list[OrderItem]] = None
    total: Optional[float] = None
    notes: Optional[str] = None


router = make_crud_router(
    "orders", OrderCreate, OrderUpdate,
    search_fields=["client_name"],
)
