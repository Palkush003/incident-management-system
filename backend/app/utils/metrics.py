import asyncio
import time
from dataclasses import dataclass, field
from threading import Lock
import structlog
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

log = structlog.get_logger(__name__)

# ── Prometheus Metrics ───────────────────────────────────────────────────────
# These are standard metrics that an SRE would monitor in a cluster.

INGESTED_TOTAL = Counter(
    "ims_signals_ingested_total", 
    "Total signals ingested into the system"
)
PROCESSED_TOTAL = Counter(
    "ims_signals_processed_total", 
    "Total signals processed by the pipeline"
)
DROPPED_TOTAL = Counter(
    "ims_signals_dropped_total", 
    "Total signals dropped due to backpressure/overflow"
)
ACTIVE_INCIDENTS = Gauge(
    "ims_active_incidents", 
    "Current number of open incidents"
)
PROCESSING_LATENCY = Histogram(
    "ims_signal_processing_latency_seconds",
    "Time taken to process a signal from Kafka to DB",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0)
)
KAFKA_PRODUCER_ERRORS = Counter(
    "ims_kafka_producer_errors_total",
    "Total errors encountered by the Kafka producer"
)

# ── LLMOps Metrics ───────────────────────────────────────────────────────────
LLM_TOKENS_TOTAL = Counter(
    "ims_llm_tokens_total",
    "Total prompt and completion tokens used by the AI RCA assistant"
)
LLM_SPEND_DOLLARS = Counter(
    "ims_llm_spend_dollars",
    "Total financial cost (USD) incurred by the AI RCA assistant"
)
LLM_LATENCY = Histogram(
    "ims_llm_generation_latency_seconds",
    "Time taken for the LLM to generate an RCA suggestion",
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)
LLM_RATE_LIMIT_DROPS = Counter(
    "ims_llm_rate_limited_total",
    "Number of times an AI request was blocked to prevent runaway costs"
)


@dataclass
class MetricsCollector:
    _ingested: int = 0
    _processed: int = 0
    _dropped: int = 0
    _active_incidents: int = 0
    _lock: Lock = field(default_factory=Lock)
    _last_reset: float = field(default_factory=time.monotonic)
    _report_task: asyncio.Task | None = None

    def increment_ingested(self, n: int = 1) -> None:
        with self._lock:
            self._ingested += n
            INGESTED_TOTAL.inc(n)

    def increment_processed(self, n: int = 1) -> None:
        with self._lock:
            self._processed += n
            PROCESSED_TOTAL.inc(n)

    def increment_dropped(self, n: int = 1) -> None:
        with self._lock:
            self._dropped += n
            DROPPED_TOTAL.inc(n)

    def set_active_incidents(self, n: int) -> None:
        with self._lock:
            self._active_incidents = n
            ACTIVE_INCIDENTS.set(n)

    def observe_latency(self, seconds: float) -> None:
        PROCESSING_LATENCY.observe(seconds)

    def record_kafka_error(self) -> None:
        KAFKA_PRODUCER_ERRORS.inc()

    def record_llm_usage(self, tokens: int, cost: float, latency: float) -> None:
        LLM_TOKENS_TOTAL.inc(tokens)
        LLM_SPEND_DOLLARS.inc(cost)
        LLM_LATENCY.observe(latency)

    def record_llm_rate_limit(self) -> None:
        LLM_RATE_LIMIT_DROPS.inc()

    def snapshot(self) -> dict:
        with self._lock:
            elapsed = max(time.monotonic() - self._last_reset, 0.001)
            snap = {
                "signals_per_sec": round(self._ingested / elapsed, 1),
                "processed_per_sec": round(self._processed / elapsed, 1),
                "dropped_total": self._dropped,
                "active_incidents": self._active_incidents,
                "elapsed_sec": round(elapsed, 1),
            }
            # Reset local counters for console reporting, 
            # but Prometheus counters keep growing (standard practice)
            self._ingested = 0
            self._processed = 0
            self._last_reset = time.monotonic()
            return snap

    async def start_reporter(self, interval: int = 5) -> None:
        """Print throughput metrics to console every `interval` seconds."""
        self._report_task = asyncio.create_task(
            self._report_loop(interval), name="metrics-reporter"
        )

    async def stop_reporter(self) -> None:
        if self._report_task:
            self._report_task.cancel()
            try:
                await self._report_task
            except asyncio.CancelledError:
                pass

    async def _report_loop(self, interval: int) -> None:
        while True:
            await asyncio.sleep(interval)
            snap = self.snapshot()
            log.info(
                "📊 THROUGHPUT REPORT",
                signals_per_sec=snap["signals_per_sec"],
                processed_per_sec=snap["processed_per_sec"],
                dropped_total=snap["dropped_total"],
                active_incidents=snap["active_incidents"],
            )


# Global singleton
metrics_collector = MetricsCollector()

# Prometheus ASGI app to expose /metrics
metrics_app = make_asgi_app()
