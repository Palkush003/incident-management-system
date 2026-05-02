"""Async MongoDB client using Motor."""
import structlog
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel
from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def init_mongodb() -> None:
    """Initialize MongoDB client and create indexes."""
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongo_url, serverSelectionTimeoutMS=5000)
    _db = _client[settings.mongo_db]

    # Create indexes for raw_signals collection
    signals_col = _db["raw_signals"]
    await signals_col.create_indexes([
        IndexModel([("component_id", ASCENDING), ("ingested_at", DESCENDING)]),
        IndexModel([("work_item_id", ASCENDING)]),
        IndexModel([("severity", ASCENDING)]),
        IndexModel([("ingested_at", DESCENDING)]),
        IndexModel([("ingested_at", ASCENDING)], expireAfterSeconds=2592000),  # 30-day TTL
    ])

    log.info("mongodb.initialized", db=settings.mongo_db)


async def close_mongodb() -> None:
    if _client:
        _client.close()
        log.info("mongodb.closed")


def get_mongodb() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB not initialized. Call init_mongodb() first.")
    return _db
