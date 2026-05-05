"""
Debounce Engine — implements sliding-window debouncing.

Logic:
  - First signal for a component_id in a 10s window → create WorkItem
  - Subsequent signals in the same window → increment count, link to WorkItem
  - After window expires, the next signal starts a NEW WorkItem
"""
import asyncio
import uuid
from datetime import datetime
import structlog
from app.config import get_settings
from app.db import redis_client
from app.db.mongodb import get_mongodb
from app.db.postgres import get_db
from app.db.orm import WorkItemORM
from app.engine.alerting import AlertDispatcher
from app.websocket.manager import ws_manager
from app.utils.metrics import metrics_collector
from app.utils.retry import async_retry

log = structlog.get_logger(__name__)
settings = get_settings()

alert_dispatcher = AlertDispatcher()

# In-memory lock per component to prevent race conditions
_component_locks: dict[str, asyncio.Lock] = {}
_locks_lock = asyncio.Lock()


async def _get_component_lock(component_id: str) -> asyncio.Lock:
    async with _locks_lock:
        if component_id not in _component_locks:
            _component_locks[component_id] = asyncio.Lock()
        return _component_locks[component_id]


async def process_signal(payload: dict) -> None:
    """
    Main signal processor. Called for every message from Kafka.
    Thread-safe per component_id via asyncio locks.
    """
    start_time = asyncio.get_event_loop().time()
    component_id = payload["component_id"]
    lock = await _get_component_lock(component_id)

    async with lock:
        await _debounce_and_store(payload)

    latency = asyncio.get_event_loop().time() - start_time
    metrics_collector.increment_processed()
    metrics_collector.observe_latency(latency)


async def _debounce_and_store(payload: dict) -> None:
    component_id = payload["component_id"]
    signal_id = payload.get("id", str(uuid.uuid4()))

    # Always store raw signal in MongoDB (audit log)
    await _store_raw_signal(payload, signal_id)
    await redis_client.record_signal_ingested()

    # Check if we're in an active debounce window
    existing_work_item_id = await redis_client.get_debounce_key(component_id)

    if existing_work_item_id:
        # Already have a work item — just link the signal and increment count
        await _link_signal_to_work_item(signal_id, existing_work_item_id, component_id)
        log.debug("debounce.signal_linked", component=component_id, work_item=existing_work_item_id)
    else:
        # First signal in window — create a new Work Item
        work_item_id = str(uuid.uuid4())
        await redis_client.set_debounce_key(
            component_id, work_item_id,
            ttl=settings.debounce_window_seconds
        )
        await _create_work_item(payload, signal_id, work_item_id)
        log.info("debounce.work_item_created", component=component_id, work_item=work_item_id)


@async_retry(max_attempts=3, min_wait=0.2, max_wait=5.0)
async def _store_raw_signal(payload: dict, signal_id: str) -> None:
    """Store raw signal in MongoDB (audit log)."""
    db = get_mongodb()
    await db["raw_signals"].insert_one({
        **payload,
        "_id": signal_id,
        "id": signal_id,
        "ingested_at": datetime.utcnow(),
    })


@async_retry(max_attempts=3, min_wait=0.2, max_wait=5.0)
async def _create_work_item(payload: dict, signal_id: str, work_item_id: str) -> None:
    """Create a new WorkItem in PostgreSQL and notify WebSocket clients."""
    component_type = payload.get("component_type", "UNKNOWN")
    severity = payload.get("severity", "P3")

    work_item = WorkItemORM(
        id=work_item_id,
        component_id=payload["component_id"],
        component_type=component_type,
        severity=severity,
        title=f"[{severity}] {component_type} failure: {payload['component_id']}",
        status="OPEN",
        signal_count=1,
        first_signal_id=signal_id,
        extra_metadata=payload.get("metadata", {}),
    )

    async with get_db() as session:
        session.add(work_item)
        await session.commit()

    # Link signal to work item in MongoDB
    await _link_signal_to_work_item(signal_id, work_item_id, payload["component_id"])

    # Fire alert strategy
    asyncio.create_task(
        alert_dispatcher.dispatch(
            component_type=component_type,
            severity=severity,
            work_item_id=work_item_id,
            component_id=payload["component_id"],
            message=payload.get("message", ""),
        )
    )

    # Fire AI RCA generation for high severity incidents
    if severity in ["P0", "P1"]:
        from app.llm.gateway import generate_ai_rca
        asyncio.create_task(generate_ai_rca(work_item_id, payload))

    # Notify WebSocket subscribers
    await ws_manager.broadcast({
        "event": "incident_created",
        "work_item": {
            "id": work_item_id,
            "component_id": payload["component_id"],
            "component_type": component_type,
            "severity": severity,
            "status": "OPEN",
            "title": work_item.title,
            "signal_count": 1,
            "created_at": datetime.utcnow().isoformat(),
        }
    })

    metrics_collector.set_active_incidents(
        metrics_collector._active_incidents + 1
    )


@async_retry(max_attempts=3, min_wait=0.1, max_wait=2.0)
async def _link_signal_to_work_item(signal_id: str, work_item_id: str, component_id: str) -> None:
    """Update signal in MongoDB with work_item_id and increment count in Postgres."""
    db = get_mongodb()
    await db["raw_signals"].update_one(
        {"_id": signal_id},
        {"$set": {"work_item_id": work_item_id}}
    )
    # Increment signal_count in PostgreSQL
    from sqlalchemy import update
    from app.db.orm import WorkItemORM as WI
    async with get_db() as session:
        await session.execute(
            update(WI)
            .where(WI.id == work_item_id)
            .values(signal_count=WI.signal_count + 1)
        )
        await session.commit()
