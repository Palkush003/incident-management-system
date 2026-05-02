"""Dashboard aggregation API and WebSocket endpoint."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select, func, desc
import structlog
from app.db.postgres import get_db
from app.db.orm import WorkItemORM, RCARecordORM
from app.db.redis_client import get_dashboard_state, set_dashboard_state, get_throughput_series
from app.websocket.manager import ws_manager
from app.utils.metrics import metrics_collector
import asyncio

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Dashboard"])


@router.get("/dashboard/summary", summary="Real-time dashboard summary")
async def dashboard_summary():
    # Try cache first (60s TTL)
    cached = await get_dashboard_state()
    if cached:
        return cached

    async with get_db() as session:
        # Active incidents by severity
        severity_counts = await session.execute(
            select(WorkItemORM.severity, func.count(WorkItemORM.id))
            .where(WorkItemORM.status != "CLOSED")
            .group_by(WorkItemORM.severity)
        )
        by_severity = {row[0]: row[1] for row in severity_counts}

        # Status breakdown
        status_counts = await session.execute(
            select(WorkItemORM.status, func.count(WorkItemORM.id))
            .group_by(WorkItemORM.status)
        )
        by_status = {row[0]: row[1] for row in status_counts}

        # Average MTTR
        mttr_result = await session.execute(
            select(func.avg(RCARecordORM.mttr_minutes))
        )
        avg_mttr = mttr_result.scalar() or 0

        # Recent incidents (top 10)
        recent = await session.execute(
            select(WorkItemORM)
            .where(WorkItemORM.status != "CLOSED")
            .order_by(WorkItemORM.severity.asc(), desc(WorkItemORM.created_at))
            .limit(10)
        )
        recent_items = recent.scalars().all()

    snap = metrics_collector.snapshot()

    summary = {
        "by_severity": by_severity,
        "by_status": by_status,
        "avg_mttr_minutes": round(avg_mttr, 2),
        "total_active": sum(v for k, v in by_status.items() if k != "CLOSED"),
        "signals_per_sec": snap["signals_per_sec"],
        "recent_incidents": [
            {
                "id": i.id,
                "component_id": i.component_id,
                "severity": i.severity,
                "status": i.status,
                "title": i.title,
                "signal_count": i.signal_count,
                "created_at": i.created_at.isoformat(),
            }
            for i in recent_items
        ],
    }

    await set_dashboard_state(summary)
    return summary


@router.get("/dashboard/metrics", summary="Time-series throughput metrics")
async def dashboard_metrics(seconds: int = Query(60, le=300)):
    series = await get_throughput_series(last_n_seconds=seconds)
    return {"series": sorted(series, key=lambda x: x["timestamp"])}


@router.get("/dashboard/mttr-stats", summary="MTTR statistics by component type")
async def mttr_stats():
    async with get_db() as session:
        result = await session.execute(
            select(
                WorkItemORM.component_type,
                func.avg(RCARecordORM.mttr_minutes).label("avg_mttr"),
                func.min(RCARecordORM.mttr_minutes).label("min_mttr"),
                func.max(RCARecordORM.mttr_minutes).label("max_mttr"),
                func.count(RCARecordORM.id).label("count"),
            )
            .join(RCARecordORM, RCARecordORM.work_item_id == WorkItemORM.id)
            .group_by(WorkItemORM.component_type)
        )
        rows = result.all()

    return [
        {
            "component_type": r.component_type,
            "avg_mttr_minutes": round(r.avg_mttr or 0, 2),
            "min_mttr_minutes": round(r.min_mttr or 0, 2),
            "max_mttr_minutes": round(r.max_mttr or 0, 2),
            "incident_count": r.count,
        }
        for r in rows
    ]


# ── WebSocket Endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial state on connect
        summary = await dashboard_summary()
        await ws_manager.send_to(websocket, {"event": "initial_state", "data": summary})

        # Keep connection alive, listen for client messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle ping/pong
                if data == "ping":
                    await ws_manager.send_to(websocket, {"event": "pong"})
            except asyncio.TimeoutError:
                # Send server heartbeat
                await ws_manager.send_to(websocket, {"event": "heartbeat"})
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as exc:
        log.error("ws.error", error=str(exc))
        await ws_manager.disconnect(websocket)
