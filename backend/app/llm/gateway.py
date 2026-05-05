"""
Simulated Enterprise LLM Gateway.
Provides AI-assisted Root Cause Analysis (RCA) suggestions while enforcing
strict SRE principles: token tracking, spend tracking, and rate limiting.
"""
import asyncio
import time
import random
import structlog
from app.db.redis_client import get_redis
from app.utils.metrics import metrics_collector
from app.db.postgres import get_db
from sqlalchemy import text

log = structlog.get_logger(__name__)

# Mock LLM Config
COST_PER_1K_TOKENS = 0.002
MAX_LLM_CALLS_PER_MINUTE = 5


async def _check_rate_limit(component_type: str) -> bool:
    """Enforce a strict quota on LLM calls to prevent runaway cloud costs."""
    r = get_redis()
    # Simple sliding window mock using Redis
    key = f"rate_limit:llm:{component_type}"
    
    # We use a simple INCR + EXPIRE logic for the demo
    # In production, we'd use the Lua token bucket script
    current = await r.incr(key)
    if current == 1:
        await r.expire(key, 60)
        
    if current > MAX_LLM_CALLS_PER_MINUTE:
        metrics_collector.record_llm_rate_limit()
        log.warning("llm.gateway.rate_limited", component_type=component_type, calls_this_min=current)
        return False
    return True


def _calculate_mock_tokens(payload_str: str) -> tuple[int, int]:
    """Estimate token usage for the mocked call."""
    prompt_tokens = len(payload_str) // 4  # Rough heuristic: 1 token = 4 chars
    completion_tokens = random.randint(50, 150)
    return prompt_tokens, completion_tokens


async def generate_ai_rca(work_item_id: str, payload: dict) -> None:
    """
    Background task: Generates an AI-suggested RCA and attaches it to the WorkItem.
    """
    component_type = payload.get("component_type", "UNKNOWN")
    component_id = payload.get("component_id", "UNKNOWN")
    
    # 1. Enforce Rate Limit (Cost Prevention)
    if not await _check_rate_limit(component_type):
        return

    log.info("llm.gateway.generating_rca", work_item_id=work_item_id)
    start_time = time.monotonic()
    
    # 2. Simulate Network/LLM Latency (0.5 to 2 seconds)
    latency = random.uniform(0.5, 2.0)
    await asyncio.sleep(latency)
    
    # 3. Simulate Token Usage and Cost
    prompt_tokens, completion_tokens = _calculate_mock_tokens(str(payload))
    total_tokens = prompt_tokens + completion_tokens
    cost = (total_tokens / 1000) * COST_PER_1K_TOKENS
    
    # Observe Metrics
    metrics_collector.record_llm_usage(total_tokens, cost, time.monotonic() - start_time)
    
    # 4. Generate Mock "AI Suggestion"
    ai_suggestion = f"AI Analysis: The {component_type} '{component_id}' likely failed due to an upstream timeout. Suggested Fix: Increase the connection pool size or verify network routing to the dependent service."
    
    # 5. Save to Database (append to extra_metadata)
    try:
        from app.db.orm import WorkItemORM
        from sqlalchemy import update
        
        async with get_db() as session:
            # Fetch current metadata, update it, and save.
            # ORM update is safer across different drivers
            result = await session.execute(
                text("SELECT extra_metadata FROM work_items WHERE id = :wid"), 
                {"wid": work_item_id}
            )
            row = result.fetchone()
            if row:
                current_meta = row[0] or {}
                current_meta["ai_rca_suggestion"] = ai_suggestion
                current_meta["llm_cost_usd"] = round(cost, 4)
                
                await session.execute(
                    update(WorkItemORM)
                    .where(WorkItemORM.id == work_item_id)
                    .values(extra_metadata=current_meta)
                )
                await session.commit()
            
        log.info(
            "llm.gateway.rca_attached", 
            work_item_id=work_item_id, 
            tokens=total_tokens, 
            cost=f"${cost:.4f}"
        )
    except Exception as e:
        log.error("llm.gateway.db_error", error=str(e))
