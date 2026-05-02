"""SQLAlchemy ORM models for PostgreSQL."""
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Float, Text, ForeignKey, JSON, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import uuid


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class WorkItemORM(Base):
    __tablename__ = "work_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    component_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    component_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN", index=True)
    signal_count: Mapped[int] = mapped_column(Integer, default=1)
    first_signal_id: Mapped[str] = mapped_column(String(36), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rca_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("rca_records.id"), nullable=True)
    mttr_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    rca: Mapped["RCARecordORM | None"] = relationship("RCARecordORM", back_populates="work_item", foreign_keys=[rca_id])
    transitions: Mapped[list["StateTransitionORM"]] = relationship("StateTransitionORM", back_populates="work_item", cascade="all, delete-orphan")


class RCARecordORM(Base):
    __tablename__ = "rca_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    work_item_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    incident_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    incident_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    root_cause_category: Mapped[str] = mapped_column(String(50), nullable=False)
    root_cause_description: Mapped[str] = mapped_column(Text, nullable=False)
    fix_applied: Mapped[str] = mapped_column(Text, nullable=False)
    prevention_steps: Mapped[str] = mapped_column(Text, nullable=False)
    affected_services: Mapped[list] = mapped_column(JSON, default=list)
    submitted_by: Mapped[str] = mapped_column(String(255), nullable=False)
    mttr_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    work_item: Mapped["WorkItemORM | None"] = relationship("WorkItemORM", back_populates="rca", foreign_keys=[WorkItemORM.rca_id])


class StateTransitionORM(Base):
    __tablename__ = "state_transitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    work_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("work_items.id"), nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    transitioned_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    transitioned_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    work_item: Mapped["WorkItemORM"] = relationship("WorkItemORM", back_populates="transitions")


class AlertLogORM(Base):
    __tablename__ = "alert_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    work_item_id: Mapped[str] = mapped_column(String(36), index=True)
    priority: Mapped[str] = mapped_column(String(10))
    alert_type: Mapped[str] = mapped_column(String(50))
    channel: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    sent_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
