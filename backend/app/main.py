"""
FastAPI application entrypoint.
Manages startup/shutdown of all async resources via lifespan context manager.
"""
import structlog
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.db.postgres import init_postgres, close_postgres
from app.db.mongodb import init_mongodb, close_mongodb
from app.db.redis_client import init_redis, close_redis
from app.kafka.producer import init_producer, close_producer
from app.kafka.consumer import init_consumer, close_consumer
from app.engine.debouncer import process_signal
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.utils.metrics import metrics_collector, metrics_app
from app.api import signals, work_items, rca, dashboard, health

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

log = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan — initialize all resources on startup,
    gracefully shut them down on shutdown.
    """
    log.info("🚀 IMS Starting up...", env=settings.app_env)

    # Initialize all data stores
    await init_postgres()
    await init_mongodb()
    await init_redis()

    # Initialize Kafka pipeline
    await init_producer()
    await init_consumer(signal_processor_fn=process_signal)

    # Start metrics reporter (every 5 seconds)
    await metrics_collector.start_reporter(interval=settings.metrics_interval_seconds)

    log.info("✅ IMS fully initialized. Ready to accept signals.")
    yield

    # ── Graceful shutdown ──────────────────────────────────────────────────
    log.info("🛑 IMS Shutting down gracefully...")
    await metrics_collector.stop_reporter()
    await close_consumer()
    await close_producer()
    await close_redis()
    await close_mongodb()
    await close_postgres()
    log.info("✅ IMS shutdown complete.")


app = FastAPI(
    title="Mission-Critical Incident Management System",
    description=(
        "A production-grade IMS for monitoring distributed stacks. "
        "Supports high-throughput signal ingestion (10K/s), "
        "workflow-driven incident management, and mandatory RCA tracking."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimiterMiddleware)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(signals.router)
app.include_router(work_items.router)
app.include_router(rca.router)
app.include_router(dashboard.router)

# Mount Prometheus metrics endpoint
app.mount("/metrics", metrics_app)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "Incident Management System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
