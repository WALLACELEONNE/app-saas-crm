"""Products — Inputs (insumos) and Grains."""
from typing import Optional
from pydantic import BaseModel
from core.crud import make_crud_router


class ProductCreate(BaseModel):
    category: str  # input | grain
    name: str
    sku: Optional[str] = None
    unit: str = "ton"
    current_price: float = 0
    currency: str = "BRL"
    notes: Optional[str] = None


class ProductUpdate(BaseModel):
    category: Optional[str] = None
    name: Optional[str] = None
    current_price: Optional[float] = None
    unit: Optional[str] = None
    notes: Optional[str] = None


router = make_crud_router(
    "products", ProductCreate, ProductUpdate,
    search_fields=["name", "sku"],
)
