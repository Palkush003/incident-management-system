"""RCA API — Submit and retrieve Root Cause Analysis."""
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
import structlog
from app.db.postgres import get_db
from app.db.orm import WorkItemORM, RCARecordORM
from app.db.redis_client import invalidate_incident_cache
from app.engine.mttr import calculate_mttr_minutes, format_mttr
from app.models.rca import RCACreate, RCAResponse
from app.websocket.manager import ws_manager
import uuid
from datetime import datetime

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/work-items", tags=["RCA"])


@router.post(
    "/{work_item_id}/rca",
    response_model=RCAResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Root Cause Analysis",
    description=(
        "Submit a complete RCA for a Work Item. "
        "All fields are MANDATORY. The system will auto-calculate MTTR. "
        "This endpoint will reject incomplete submissions."
    ),
)
async def submit_rca(work_item_id: str, body: RCACreate) -> RCAResponse:
    async with get_db() as session:
        # Verify work item exists
        result = await session.execute(
            select(WorkItemORM).where(WorkItemORM.id == work_item_id)
        )
        work_item = result.scalar_one_or_none()
        if not work_item:
            raise HTTPException(status_code=404, detail=f"Work item {work_item_id} not found")

        if work_item.status == "CLOSED":
            raise HTTPException(
                status_code=409,
                detail="This incident is already CLOSED. RCA cannot be modified.",
            )

        # Check for duplicate RCA
        existing_rca = await session.execute(
            select(RCARecordORM).where(RCARecordORM.work_item_id == work_item_id)
        )
        if existing_rca.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="An RCA for this Work Item already exists. Use PATCH to update.",
            )

        # Calculate MTTR
        mttr = calculate_mttr_minutes(body.incident_start, body.incident_end)

        # Persist RCA record
        rca_id = str(uuid.uuid4())
        rca = RCARecordORM(
            id=rca_id,
            work_item_id=work_item_id,
            incident_start=body.incident_start,
            incident_end=body.incident_end,
            root_cause_category=body.root_cause_category.value,
            root_cause_description=body.root_cause_description,
            fix_applied=body.fix_applied,
            prevention_steps=body.prevention_steps,
            affected_services=body.affected_services,
            submitted_by=body.submitted_by,
            mttr_minutes=mttr,
        )
        session.add(rca)
        await session.flush()

        # Link RCA to Work Item and store MTTR
        await session.execute(
            update(WorkItemORM)
            .where(WorkItemORM.id == work_item_id)
            .values(rca_id=rca_id, mttr_minutes=mttr, updated_at=datetime.utcnow())
        )

    await invalidate_incident_cache(work_item_id)

    # Broadcast RCA submission event
    await ws_manager.broadcast({
        "event": "rca_submitted",
        "work_item_id": work_item_id,
        "mttr_minutes": mttr,
        "mttr_formatted": format_mttr(mttr),
        "submitted_by": body.submitted_by,
        "timestamp": datetime.utcnow().isoformat(),
    })

    log.info(
        "rca.submitted",
        work_item_id=work_item_id,
        mttr_minutes=mttr,
        category=body.root_cause_category,
        submitted_by=body.submitted_by,
    )

    return RCAResponse(
        id=rca_id,
        work_item_id=work_item_id,
        mttr_minutes=mttr,
        created_at=datetime.utcnow(),
        **body.model_dump(),
    )


@router.get(
    "/{work_item_id}/rca",
    response_model=RCAResponse,
    summary="Get RCA for a work item",
)
async def get_rca(work_item_id: str) -> RCAResponse:
    async with get_db() as session:
        result = await session.execute(
            select(RCARecordORM).where(RCARecordORM.work_item_id == work_item_id)
        )
        rca = result.scalar_one_or_none()
        if not rca:
            raise HTTPException(
                status_code=404,
                detail=f"No RCA found for work item {work_item_id}. "
                       "Submit one via POST /work-items/{id}/rca",
            )
    return RCAResponse.model_validate(rca)
