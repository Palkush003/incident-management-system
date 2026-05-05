"""
State Pattern — Work Item Lifecycle Management.

States:      OPEN → INVESTIGATING → RESOLVED → CLOSED
Transitions: Enforced by each state object.
Audit:       Every transition is logged to PostgreSQL.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING
import structlog
from sqlalchemy import update, select
from app.db.postgres import get_db
from app.db.orm import WorkItemORM, StateTransitionORM
from app.db.redis_client import invalidate_incident_cache
from app.websocket.manager import ws_manager

if TYPE_CHECKING:
    pass

log = structlog.get_logger(__name__)


class WorkItemStateError(Exception):
    """Raised when an invalid state transition is attempted."""


# ── Abstract State ────────────────────────────────────────────────────────────

class WorkItemState(ABC):
    """Abstract base for all Work Item states."""

    @abstractmethod
    def status_name(self) -> str: ...

    @abstractmethod
    async def transition_to_investigating(self, context: "WorkItemContext") -> None: ...

    @abstractmethod
    async def transition_to_resolved(self, context: "WorkItemContext") -> None: ...

    @abstractmethod
    async def transition_to_closed(self, context: "WorkItemContext") -> None: ...

    def _reject(self, from_state: str, to_state: str):
        raise WorkItemStateError(
            f"Cannot transition from {from_state} → {to_state}. "
            f"Only valid transitions are: OPEN→INVESTIGATING, INVESTIGATING→RESOLVED, RESOLVED→CLOSED."
        )


# ── Concrete States ───────────────────────────────────────────────────────────

class OpenState(WorkItemState):
    def status_name(self) -> str:
        return "OPEN"

    async def transition_to_investigating(self, context: "WorkItemContext") -> None:
        await context._apply_transition("OPEN", "INVESTIGATING")
        context.state = InvestigatingState()

    async def transition_to_resolved(self, context: "WorkItemContext") -> None:
        self._reject("OPEN", "RESOLVED")

    async def transition_to_closed(self, context: "WorkItemContext") -> None:
        self._reject("OPEN", "CLOSED")


class InvestigatingState(WorkItemState):
    def status_name(self) -> str:
        return "INVESTIGATING"

    async def transition_to_investigating(self, context: "WorkItemContext") -> None:
        self._reject("INVESTIGATING", "INVESTIGATING")

    async def transition_to_resolved(self, context: "WorkItemContext") -> None:
        await context._apply_transition("INVESTIGATING", "RESOLVED")
        context.state = ResolvedState()

    async def transition_to_closed(self, context: "WorkItemContext") -> None:
        self._reject("INVESTIGATING", "CLOSED")


class ResolvedState(WorkItemState):
    def status_name(self) -> str:
        return "RESOLVED"

    async def transition_to_investigating(self, context: "WorkItemContext") -> None:
        self._reject("RESOLVED", "INVESTIGATING")

    async def transition_to_resolved(self, context: "WorkItemContext") -> None:
        self._reject("RESOLVED", "RESOLVED")

    async def transition_to_closed(self, context: "WorkItemContext") -> None:
        # CRITICAL: Must have a completed RCA before closing
        if not context.has_complete_rca:
            raise WorkItemStateError(
                "Cannot close incident: RCA is missing or incomplete. "
                "Please submit a complete Root Cause Analysis first."
            )
        await context._apply_transition("RESOLVED", "CLOSED")
        context.state = ClosedState()


class ClosedState(WorkItemState):
    def status_name(self) -> str:
        return "CLOSED"

    async def transition_to_investigating(self, context: "WorkItemContext") -> None:
        self._reject("CLOSED", "INVESTIGATING")

    async def transition_to_resolved(self, context: "WorkItemContext") -> None:
        self._reject("CLOSED", "RESOLVED")

    async def transition_to_closed(self, context: "WorkItemContext") -> None:
        self._reject("CLOSED", "CLOSED")


# ── Context ───────────────────────────────────────────────────────────────────

_STATE_MAP = {
    "OPEN": OpenState,
    "INVESTIGATING": InvestigatingState,
    "RESOLVED": ResolvedState,
    "CLOSED": ClosedState,
}


class WorkItemContext:
    """
    The context object that holds the current state and delegates
    transition calls to the state object.
    """

    def __init__(self, work_item_id: str, current_status: str, has_rca: bool = False):
        self.work_item_id = work_item_id
        self.has_complete_rca = has_rca
        state_cls = _STATE_MAP.get(current_status, OpenState)
        self.state: WorkItemState = state_cls()
        self._transitioned_by: str | None = None
        self._notes: str | None = None

    def set_transition_metadata(self, by: str | None, notes: str | None):
        self._transitioned_by = by
        self._notes = notes

    async def transition_to(self, target_status: str) -> str:
        target = target_status.upper()
        if target == "INVESTIGATING":
            await self.state.transition_to_investigating(self)
        elif target == "RESOLVED":
            await self.state.transition_to_resolved(self)
        elif target == "CLOSED":
            await self.state.transition_to_closed(self)
        else:
            raise WorkItemStateError(f"Unknown target status: {target_status}")
        return self.state.status_name()

    async def _apply_transition(self, from_status: str, to_status: str) -> None:
        """Persist the transition to PostgreSQL and broadcast via WebSocket."""
        async with get_db() as session:
            # Update work item status (transactional)
            await session.execute(
                update(WorkItemORM)
                .where(WorkItemORM.id == self.work_item_id)
                .values(status=to_status, updated_at=datetime.utcnow())
            )
            # Log the transition
            transition_log = StateTransitionORM(
                work_item_id=self.work_item_id,
                from_status=from_status,
                to_status=to_status,
                transitioned_by=self._transitioned_by,
                notes=self._notes,
            )
            session.add(transition_log)
            await session.commit()

        # Invalidate cache
        await invalidate_incident_cache(self.work_item_id)

        # Broadcast to WebSocket clients
        await ws_manager.broadcast({
            "event": "status_changed",
            "work_item_id": self.work_item_id,
            "from_status": from_status,
            "to_status": to_status,
            "transitioned_by": self._transitioned_by,
            "timestamp": datetime.utcnow().isoformat(),
        })

        log.info(
            "work_item.transition",
            work_item_id=self.work_item_id,
            from_status=from_status,
            to_status=to_status,
            by=self._transitioned_by,
        )
