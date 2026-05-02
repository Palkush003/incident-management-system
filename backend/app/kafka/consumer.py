"""Async Kafka consumer — reads raw-signals and dispatches to the signal processor."""
import asyncio
import json
import structlog
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError
from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

_consumer: AIOKafkaConsumer | None = None
_consume_task: asyncio.Task | None = None


async def init_consumer(signal_processor_fn) -> None:
    """Start consumer and background consume loop."""
    global _consumer, _consume_task
    _consumer = AIOKafkaConsumer(
        settings.kafka_raw_signals_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        auto_commit_interval_ms=1000,
        max_poll_records=500,
        session_timeout_ms=30000,
        heartbeat_interval_ms=10000,
    )
    await _consumer.start()
    _consume_task = asyncio.create_task(
        _consume_loop(signal_processor_fn), name="kafka-consumer"
    )
    log.info("kafka.consumer.started", group=settings.kafka_consumer_group)


async def close_consumer() -> None:
    global _consume_task
    if _consume_task:
        _consume_task.cancel()
        try:
            await _consume_task
        except asyncio.CancelledError:
            pass
    if _consumer:
        await _consumer.stop()
    log.info("kafka.consumer.stopped")


async def _consume_loop(processor_fn) -> None:
    """Main consume loop — processes messages concurrently via asyncio tasks."""
    while True:
        try:
            async for msg in _consumer:
                asyncio.create_task(
                    _safe_process(processor_fn, msg.value),
                    name=f"process-signal-{msg.offset}"
                )
        except asyncio.CancelledError:
            break
        except KafkaConnectionError as exc:
            log.error("kafka.consumer.connection_error", error=str(exc))
            await asyncio.sleep(2)
        except Exception as exc:
            log.error("kafka.consumer.error", error=str(exc))
            await asyncio.sleep(0.5)


async def _safe_process(processor_fn, payload: dict) -> None:
    try:
        await processor_fn(payload)
    except Exception as exc:
        log.error("signal.processing.failed", error=str(exc), payload=str(payload)[:200])
