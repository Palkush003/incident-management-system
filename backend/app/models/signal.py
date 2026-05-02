"""Pydantic models for inbound signals."""
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator
import uuid


class ComponentType(str, Enum):
    RDBMS = "RDBMS"
    NOSQL = "NOSQL"
    CACHE = "CACHE"
    ASYNC_QUEUE = "ASYNC_QUEUE"
    API = "API"
    MCP_HOST = "MCP_HOST"
    LOAD_BALANCER = "LOAD_BALANCER"
    MICROSERVICE = "MICROSERVICE"


class Severity(str, Enum):
    P0 = "P0"  # Critical — immediate action required
    P1 = "P1"  # High — urgent
    P2 = "P2"  # Medium — standard
    P3 = "P3"  # Low — informational


class SignalPayload(BaseModel):
    """Inbound signal from a monitored component."""
    component_id: str = Field(..., description="Unique ID of the failing component", examples=["CACHE_CLUSTER_01"])
    component_type: ComponentType
    severity: Severity
    message: str = Field(..., max_length=2000)
    error_code: str | None = Field(None, examples=["ERR_CONNECTION_TIMEOUT"])
    stack_trace: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_host: str | None = Field(None, description="Hostname that detected the failure")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("component_id")
    @classmethod
    def component_id_must_be_upper(cls, v: str) -> str:
        return v.upper().strip()


class SignalRecord(SignalPayload):
    """Signal as stored in MongoDB (with generated ID and work_item link)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    work_item_id: str | None = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class SignalIngestionResponse(BaseModel):
    """Response returned after signal ingestion."""
    signal_id: str
    status: str = "accepted"
    message: str = "Signal queued for async processing"
