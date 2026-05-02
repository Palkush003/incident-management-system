"""Signal ingestion API endpoint."""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
import structlog
from app.models.signal import SignalPayload, SignalIngestionResponse, SignalRecord
from app.kafka.producer import enqueue_signal

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/signals", tags=["Signal Ingestion"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SignalIngestionResponse,
    summary="Ingest a failure signal",
    description=(
        "Accepts a failure signal from any monitored component. "
        "Returns 202 Accepted immediately — processing is async via Kafka. "
        "Rate limited to 10,000 requests/second per client IP."
    ),
)
async def ingest_signal(payload: SignalPayload) -> SignalIngestionResponse:
    signal_id = str(uuid.uuid4())
    record = SignalRecord(
        **payload.model_dump(),
        id=signal_id,
        ingested_at=datetime.utcnow(),
    )
    await enqueue_signal(record.model_dump(), component_id=record.component_id)
    log.debug("signal.accepted", signal_id=signal_id, component=payload.component_id)
    return SignalIngestionResponse(signal_id=signal_id)


@router.post(
    "/batch",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Batch ingest signals (up to 1000)",
)
async def ingest_signals_batch(payloads: list[SignalPayload]) -> dict:
    if len(payloads) > 1000:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Maximum 1000 signals per batch.",
        )
    signal_ids = []
    for payload in payloads:
        sid = str(uuid.uuid4())
        record = SignalRecord(**payload.model_dump(), id=sid)
        await enqueue_signal(record.model_dump(), component_id=record.component_id)
        signal_ids.append(sid)
    return {"accepted": len(signal_ids), "signal_ids": signal_ids}
