"""Work Item Pydantic models (the core incident record)."""
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
import uuid


class WorkItemStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


# Valid transitions map
VALID_TRANSITIONS: dict[WorkItemStatus, list[WorkItemStatus]] = {
    WorkItemStatus.OPEN: [WorkItemStatus.INVESTIGATING],
    WorkItemStatus.INVESTIGATING: [WorkItemStatus.RESOLVED],
    WorkItemStatus.RESOLVED: [WorkItemStatus.CLOSED],
    WorkItemStatus.CLOSED: [],  # Terminal state
}


class WorkItemCreate(BaseModel):
    component_id: str
    component_type: str
    severity: str
    title: str
    first_signal_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkItemTransition(BaseModel):
    target_status: WorkItemStatus
    assigned_to: str | None = None
    notes: str | None = None


class WorkItemResponse(BaseModel):
    id: str
    component_id: str
    component_type: str
    severity: str
    title: str
    status: WorkItemStatus
    signal_count: int = 0
    first_signal_id: str
    assigned_to: str | None = None
    rca_id: str | None = None
    mttr_minutes: float | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class StateTransitionLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    work_item_id: str
    from_status: WorkItemStatus
    to_status: WorkItemStatus
    transitioned_by: str | None = None
    notes: str | None = None
    transitioned_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}
