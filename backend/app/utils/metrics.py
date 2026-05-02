"""
Throughput metrics collector.
Tracks signals ingested/processed/dropped per second.
Prints a report to console every METRICS_INTERVAL_SECONDS.
"""
import asyncio
import time
from dataclasses import dataclass, field
from threading import Lock
import structlog

log = structlog.get_logger(__name__)


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

    def increment_processed(self, n: int = 1) -> None:
        with self._lock:
            self._processed += n

    def increment_dropped(self, n: int = 1) -> None:
        with self._lock:
            self._dropped += n

    def set_active_incidents(self, n: int) -> None:
        with self._lock:
            self._active_incidents = n

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
            # Reset counters
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
            print(
                f"\033[36m[METRICS]\033[0m "
                f"Ingested: \033[33m{snap['signals_per_sec']}/s\033[0m | "
                f"Processed: \033[32m{snap['processed_per_sec']}/s\033[0m | "
                f"Dropped: \033[31m{snap['dropped_total']}\033[0m | "
                f"Active Incidents: \033[35m{snap['active_incidents']}\033[0m"
            )


# Global singleton
metrics_collector = MetricsCollector()
