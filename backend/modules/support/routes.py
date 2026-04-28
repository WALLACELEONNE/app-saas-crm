"""Support — Tickets and SLAs."""
from typing import Optional
from pydantic import BaseModel, Field
from core.crud import make_crud_router


class TicketCreate(BaseModel):
    client_id: str
    client_name: Optional[str] = None
    subject: str
    description: Optional[str] = None
    priority: str = "medium"  # low | medium | high | critical
    sla_hours: int = 24
    status: str = "open"  # open | in_progress | closed
    assigned_to: Optional[str] = None
    comments: list[dict] = Field(default_factory=list)


class TicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    description: Optional[str] = None


router = make_crud_router(
    "tickets", TicketCreate, TicketUpdate,
    search_fields=["subject", "client_name"],
)
