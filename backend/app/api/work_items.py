"""Work Items API — CRUD + State Transitions."""
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
import structlog
from app.db.postgres import get_db
from app.db.mongodb import get_mongodb
from app.db.orm import WorkItemORM, StateTransitionORM
from app.db.redis_client import get_cached_incident, cache_incident
from app.engine.workflow import WorkItemContext, WorkItemStateError
from app.models.work_item import WorkItemResponse, WorkItemTransition

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/work-items", tags=["Work Items"])


@router.get("", response_model=list[WorkItemResponse], summary="List all work items")
async def list_work_items(
    status: str | None = Query(None, description="Filter by status"),
    severity: str | None = Query(None, description="Filter by severity"),
    component_type: str | None = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    async with get_db() as session:
        q = select(WorkItemORM).order_by(
            # Priority ordering: P0 > P1 > P2 > P3, then newest first
            WorkItemORM.severity.asc(),
            desc(WorkItemORM.created_at)
        )
        if status:
            q = q.where(WorkItemORM.status == status.upper())
        if severity:
            q = q.where(WorkItemORM.severity == severity.upper())
        if component_type:
            q = q.where(WorkItemORM.component_type == component_type.upper())
        q = q.limit(limit).offset(offset)
        result = await session.execute(q)
        items = result.scalars().all()
    return [WorkItemResponse.model_validate(item) for item in items]


@router.get("/{work_item_id}", response_model=WorkItemResponse, summary="Get work item by ID")
async def get_work_item(work_item_id: str):
    # Try cache first
    cached = await get_cached_incident(work_item_id)
    if cached:
        return WorkItemResponse(**cached)

    async with get_db() as session:
        result = await session.execute(
            select(WorkItemORM).where(WorkItemORM.id == work_item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail=f"Work item {work_item_id} not found")

    response = WorkItemResponse.model_validate(item)
    await cache_incident(work_item_id, response.model_dump(), ttl=60)
    return response


@router.get("/{work_item_id}/signals", summary="Get raw signals for a work item (from MongoDB)")
async def get_work_item_signals(
    work_item_id: str,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
):
    db = get_mongodb()
    cursor = (
        db["raw_signals"]
        .find({"work_item_id": work_item_id}, {"_id": 0})
        .sort("ingested_at", -1)
        .skip(offset)
        .limit(limit)
    )
    signals = await cursor.to_list(length=limit)
    total = await db["raw_signals"].count_documents({"work_item_id": work_item_id})
    return {"total": total, "signals": signals}


@router.get("/{work_item_id}/timeline", summary="Get state transition history")
async def get_work_item_timeline(work_item_id: str):
    async with get_db() as session:
        result = await session.execute(
            select(StateTransitionORM)
            .where(StateTransitionORM.work_item_id == work_item_id)
            .order_by(StateTransitionORM.transitioned_at)
        )
        transitions = result.scalars().all()
    return [
        {
            "from_status": t.from_status,
            "to_status": t.to_status,
            "transitioned_by": t.transitioned_by,
            "notes": t.notes,
            "transitioned_at": t.transitioned_at.isoformat(),
        }
        for t in transitions
    ]


@router.patch(
    "/{work_item_id}/transition",
    response_model=WorkItemResponse,
    summary="Transition work item to next state",
)
async def transition_work_item(work_item_id: str, body: WorkItemTransition):
    async with get_db() as session:
        result = await session.execute(
            select(WorkItemORM).where(WorkItemORM.id == work_item_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail=f"Work item {work_item_id} not found")

        has_rca = item.rca_id is not None
        ctx = WorkItemContext(work_item_id, item.status, has_rca=has_rca)
        ctx.set_transition_metadata(by=body.assigned_to, notes=body.notes)

        try:
            new_status = await ctx.transition_to(body.target_status.value)
        except WorkItemStateError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        # Reload after transition
        await session.refresh(item)
        return WorkItemResponse.model_validate(item)
