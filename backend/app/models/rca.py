"""RCA (Root Cause Analysis) Pydantic models."""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, model_validator
import uuid


class RootCauseCategory(str, Enum):
    INFRASTRUCTURE = "Infrastructure"
    CODE_BUG = "Code Bug"
    CONFIGURATION = "Configuration"
    EXTERNAL_DEPENDENCY = "External Dependency"
    CAPACITY = "Capacity"
    NETWORK = "Network"
    SECURITY = "Security"
    HUMAN_ERROR = "Human Error"
    UNKNOWN = "Unknown"


class RCACreate(BaseModel):
    """Payload to create/submit an RCA."""
    incident_start: datetime = Field(..., description="When the incident began (first signal)")
    incident_end: datetime = Field(..., description="When the incident was fully resolved")
    root_cause_category: RootCauseCategory
    root_cause_description: str = Field(..., min_length=20, max_length=5000, description="Detailed description of the root cause")
    fix_applied: str = Field(..., min_length=10, max_length=5000, description="What was done to fix the issue")
    prevention_steps: str = Field(..., min_length=10, max_length=5000, description="Steps to prevent recurrence")
    affected_services: list[str] = Field(default_factory=list)
    submitted_by: str = Field(..., description="Name/email of the person submitting the RCA")

    @model_validator(mode="after")
    def end_must_be_after_start(self) -> "RCACreate":
        if self.incident_end <= self.incident_start:
            raise ValueError("incident_end must be after incident_start")
        return self

    def mttr_would_be_positive(self) -> bool:
        """Return True if MTTR calculation would yield a positive number."""
        return self.incident_end > self.incident_start


class RCARecord(RCACreate):
    """RCA as stored in PostgreSQL."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    work_item_id: str = ""
    mttr_minutes: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"from_attributes": True}


class RCAResponse(RCARecord):
    pass
