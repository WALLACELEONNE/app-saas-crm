"""Clients module — Producers and Companies."""
from typing import Optional
from pydantic import BaseModel, Field
from core.crud import make_crud_router


class Contact(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class ClientCreate(BaseModel):
    type: str  # producer | company
    name: str
    doc: Optional[str] = None  # CPF/CNPJ
    region: Optional[str] = None
    culture: list[str] = Field(default_factory=list)
    classification: Optional[str] = None  # A/B/C
    potential: Optional[str] = None  # alto/medio/baixo
    area_ha: Optional[float] = None
    contacts: list[Contact] = Field(default_factory=list)
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    type: Optional[str] = None
    name: Optional[str] = None
    doc: Optional[str] = None
    region: Optional[str] = None
    culture: Optional[list[str]] = None
    classification: Optional[str] = None
    potential: Optional[str] = None
    area_ha: Optional[float] = None
    contacts: Optional[list[Contact]] = None
    notes: Optional[str] = None


router = make_crud_router(
    "clients", ClientCreate, ClientUpdate,
    search_fields=["name", "doc", "region"],
)
