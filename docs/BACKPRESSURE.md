# Backpressure Strategy

## The Problem

The system must handle **10,000 signals/second** bursts without crashing, even when the persistence layer (Kafka, PostgreSQL, MongoDB) is slow or temporarily unavailable.

## 4-Layer Defense in Depth

```
Signal Arrival (10K/s burst)
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Layer 1: Rate Limiter (Token Bucket, Redis Lua)                   │
│                                                                   │
│  ┌──────────────────────────┐                                     │
│  │ Tokens: ████████░░░░░░░  │ ← Refill at 10K/s                  │
│  └──────────────────────────┘                                     │
│                                                                   │
│  ✓ ALLOWED: Request takes 1 token                                │
│  ✗ REJECTED: No tokens → HTTP 429 + Retry-After: 1              │
│                                                                   │
│  Implementation: Atomic Lua script in Redis                       │
│  Shared across all backend instances (distributed)               │
└───────────────────────┬───────────────────────────────────────────┘
                        │ Allowed requests
                        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Layer 2: In-Memory Buffer (asyncio.Queue, 50K capacity)           │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │ Queue [████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░]  │    │
│  │       ← 25K items (half full)                            │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│  Normal: Signals queued for async Kafka publish                   │
│  Buffer Full: Oldest signal DROPPED + metric incremented         │
│  → Ensures no blocking, no crashes, even if Kafka is slow        │
└───────────────────────┬───────────────────────────────────────────┘
                        │ Drains continuously
                        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Layer 3: Kafka (Persistent, Partitioned by component_id)          │
│                                                                   │
│  Topic: raw-signals (6 partitions)                               │
│  Partitioning: By component_id → ordering per component          │
│  Producer: linger_ms=5, batch_size=64KB, gzip compression        │
│                                                                   │
│  Kafka → If full/slow: Buffer absorbs (Layer 2)                  │
│  Kafka → If down: Buffer in memory, reconnect with retry         │
│  Consumer lag: Monitored and reported in /health                  │
└───────────────────────┬───────────────────────────────────────────┘
                        │ Consumed by processor
                        ▼
┌───────────────────────────────────────────────────────────────────┐
│ Layer 4: DB Write Retry + Circuit Breaker (Tenacity)              │
│                                                                   │
│  Retry: 3 attempts, exponential backoff (0.2s → 5s) + jitter     │
│  Circuit Breaker:                                                 │
│    CLOSED (normal) → 5 failures → OPEN (reject) → 30s → HALF_OPEN│
│                                                                   │
│  If DB is down: Circuit opens, signals accumulate in Kafka        │
│  If DB recovers: Circuit closes, consumer resumes from offset     │
│  → Kafka provides durability, DB writes are eventually consistent │
└───────────────────────────────────────────────────────────────────┘
```

## Key Decisions

| Decision | Rationale |
|---|---|
| **Bounded asyncio.Queue** | Prevents unbounded memory growth during outages |
| **Drop oldest on overflow** | Newer signals are more useful than old ones |
| **Kafka partitioned by component_id** | Ordering per component, parallelism across components |
| **linger_ms batching** | Trades latency for throughput under load |
| **Atomic Lua rate limiter** | No race conditions in distributed deployments |
| **Circuit Breaker on DB** | Prevents thundering herd on DB recovery |

## Observable Backpressure Metrics

Every 5 seconds the backend prints:
```
[METRICS] Ingested: 9847.3/s | Processed: 9800.1/s | Dropped: 0 | Active Incidents: 3
```

- **Ingested**: Signals accepted into the in-memory buffer
- **Processed**: Signals fully processed through Kafka → DB
- **Dropped**: Signals lost due to buffer overflow (should be 0 under normal conditions)
- **Active Incidents**: Current open/investigating work items

The `/health` endpoint also exposes these metrics via API.
