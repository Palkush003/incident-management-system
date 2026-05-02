"""
Kafka async producer with in-memory backpressure buffer.

Architecture:
  Caller → asyncio.Queue (bounded 50K) → Background task → Kafka
  If Kafka is slow, signals accumulate in the Queue (backpressure).
  If Queue is full, oldest signal is dropped and a metric is incremented.
"""
import asyncio
import json
import structlog
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError
from app.config import get_settings
from app.utils.metrics import metrics_collector

log = structlog.get_logger(__name__)
settings = get_settings()

_producer: AIOKafkaProducer | None = None
_buffer: asyncio.Queue = asyncio.Queue(maxsize=settings.memory_buffer_size)
_flush_task: asyncio.Task | None = None


async def init_producer() -> None:
    """Start Kafka producer and background flush task."""
    global _producer, _flush_task
    _producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        compression_type="gzip",
        max_request_size=10485760,  # 10MB
        request_timeout_ms=30000,
        retry_backoff_ms=100,
    )
    await _producer.start()
    _flush_task = asyncio.create_task(_flush_loop(), name="kafka-flush")
    log.info("kafka.producer.started", servers=settings.kafka_bootstrap_servers)


async def close_producer() -> None:
    global _flush_task
    if _flush_task:
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
    if _producer:
        await _producer.stop()
    log.info("kafka.producer.stopped")


async def enqueue_signal(payload: dict, component_id: str) -> None:
    """
    Enqueue a signal for async publishing. Non-blocking.
    If buffer is full, drop oldest and log the drop.
    """
    item = (settings.kafka_raw_signals_topic, component_id, payload)
    if _buffer.full():
        try:
            _buffer.get_nowait()  # Drop oldest
            metrics_collector.increment_dropped()
            log.warning("kafka.buffer.overflow", dropped=1)
        except asyncio.QueueEmpty:
            pass
    await _buffer.put(item)
    metrics_collector.increment_ingested()


async def _flush_loop() -> None:
    """Background task: drain buffer → Kafka."""
    while True:
        try:
            topic, key, payload = await _buffer.get()
            if _producer:
                await _producer.send_and_wait(topic, value=payload, key=key)
        except asyncio.CancelledError:
            break
        except KafkaConnectionError as exc:
            log.error("kafka.send.failed", error=str(exc))
            await asyncio.sleep(0.5)
        except Exception as exc:
            log.error("kafka.flush.error", error=str(exc))
