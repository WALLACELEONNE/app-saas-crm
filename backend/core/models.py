"""Base Pydantic models. All entities carry: id (UUID), seq_id, timestamps, soft delete, tenant."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
import uuid


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class BaseEntity(BaseModel):
    """Base for all DB entities. Stored in MongoDB with the same field names."""
    id: str = Field(default_factory=new_uuid)
    seq_id: int = 0
    tenant_id: str = "tenant-default"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    deleted_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None


class AuditLog(BaseModel):
    id: str = Field(default_factory=new_uuid)
    tenant_id: str = "tenant-default"
    entity: str
    entity_id: str
    action: str  # create | update | delete | restore
    before: Optional[dict] = None
    after: Optional[dict] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    timestamp: datetime = Field(default_factory=utcnow)
