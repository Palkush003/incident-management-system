"""Unit tests for Work Item State Machine (State Pattern).
Fully self-contained — no DB or FastAPI imports required.
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# ── Mock heavy dependencies before import ─────────────────────────────────────
# This allows the state machine tests to run without FastAPI/Redis installed
sys.modules.setdefault("fastapi", MagicMock())
sys.modules.setdefault("redis", MagicMock())
sys.modules.setdefault("redis.asyncio", MagicMock())

for _mod in [
    "app.db.redis_client", "app.db.postgres", "app.db.orm",
    "app.websocket", "app.websocket.manager",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Patch at module level before import
with patch("app.db.redis_client.invalidate_incident_cache", new=AsyncMock()), \
     patch("app.websocket.manager.ws_manager", new=MagicMock(broadcast=AsyncMock())):
    from app.engine.workflow import (
        WorkItemContext,
        WorkItemStateError,
        OpenState,
        InvestigatingState,
        ResolvedState,
        ClosedState,
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def make_context(status: str, has_rca: bool = False) -> WorkItemContext:
    ctx = WorkItemContext("test-work-item-id", status, has_rca=has_rca)
    ctx._apply_transition = AsyncMock()
    return ctx


# ── State Name Tests ──────────────────────────────────────────────────────────

def test_open_state_name():
    assert OpenState().status_name() == "OPEN"

def test_investigating_state_name():
    assert InvestigatingState().status_name() == "INVESTIGATING"

def test_resolved_state_name():
    assert ResolvedState().status_name() == "RESOLVED"

def test_closed_state_name():
    assert ClosedState().status_name() == "CLOSED"


# ── Valid Transitions ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_open_to_investigating():
    ctx = make_context("OPEN")
    await ctx.transition_to("INVESTIGATING")
    assert ctx.state.status_name() == "INVESTIGATING"

@pytest.mark.asyncio
async def test_investigating_to_resolved():
    ctx = make_context("INVESTIGATING")
    await ctx.transition_to("RESOLVED")
    assert ctx.state.status_name() == "RESOLVED"

@pytest.mark.asyncio
async def test_resolved_to_closed_with_rca():
    ctx = make_context("RESOLVED", has_rca=True)
    await ctx.transition_to("CLOSED")
    assert ctx.state.status_name() == "CLOSED"


# ── Invalid Transitions ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_open_to_resolved_rejected():
    ctx = make_context("OPEN")
    with pytest.raises(WorkItemStateError):
        await ctx.transition_to("RESOLVED")

@pytest.mark.asyncio
async def test_open_to_closed_rejected():
    ctx = make_context("OPEN")
    with pytest.raises(WorkItemStateError):
        await ctx.transition_to("CLOSED")

@pytest.mark.asyncio
async def test_investigating_to_closed_rejected():
    ctx = make_context("INVESTIGATING")
    with pytest.raises(WorkItemStateError):
        await ctx.transition_to("CLOSED")

@pytest.mark.asyncio
async def test_closed_is_terminal():
    ctx = make_context("CLOSED", has_rca=True)
    with pytest.raises(WorkItemStateError):
        await ctx.transition_to("OPEN")
    ctx2 = make_context("CLOSED", has_rca=True)
    with pytest.raises(WorkItemStateError):
        await ctx2.transition_to("INVESTIGATING")
    ctx3 = make_context("CLOSED", has_rca=True)
    with pytest.raises(WorkItemStateError):
        await ctx3.transition_to("RESOLVED")

# ── RCA Guard ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolved_to_closed_without_rca_rejected():
    """CRITICAL: Must reject CLOSED transition if RCA is missing."""
    ctx = make_context("RESOLVED", has_rca=False)
    with pytest.raises(WorkItemStateError, match="RCA is missing"):
        await ctx.transition_to("CLOSED")

@pytest.mark.asyncio
async def test_unknown_target_status_rejected():
    ctx = make_context("OPEN")
    with pytest.raises(WorkItemStateError, match="Unknown target status"):
        await ctx.transition_to("INVALID_STATUS")
