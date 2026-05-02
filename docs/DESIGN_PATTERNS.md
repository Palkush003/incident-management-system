# Design Patterns Reference

## 1. State Pattern — Work Item Lifecycle

**File**: `backend/app/engine/workflow.py`

**Why**: The incident lifecycle has strict transition rules. Using a State Pattern encapsulates each state's behavior and makes invalid transitions impossible at compile time (not just runtime checks).

```
                 ┌─────────────────────────────────────────┐
                 │           WorkItemContext                │
                 │  - work_item_id                         │
                 │  - has_complete_rca                     │
                 │  - state: WorkItemState                  │
                 │                                         │
                 │  + transition_to(target) → str          │
                 └────────────────┬────────────────────────┘
                                  │ delegates to
                 ┌────────────────▼────────────────────────┐
                 │          <<abstract>>                   │
                 │          WorkItemState                  │
                 │                                         │
                 │  + status_name() → str                  │
                 │  + transition_to_investigating()        │
                 │  + transition_to_resolved()             │
                 │  + transition_to_closed()               │
                 └─────┬──────┬──────┬──────┬─────────────┘
                       │      │      │      │
               ┌───────▼─┐ ┌──▼───┐ ┌▼───────┐ ┌──────┐
               │  Open   │ │Invest│ │Resolved│ │Closed│
               │  State  │ │igating│ │ State  │ │State │
               └─────────┘ └──────┘ └────────┘ └──────┘
```

**RCA Guard**: `ResolvedState.transition_to_closed()` checks `context.has_complete_rca` before allowing the transition. This is the **mandatory business rule** enforcement.

---

## 2. Strategy Pattern — Alert Routing

**File**: `backend/app/engine/alerting.py`

**Why**: Different component types require fundamentally different alerting behaviors. The Strategy Pattern allows the dispatcher to select the correct behavior at runtime without `if/elif` chains.

```
     AlertDispatcher.dispatch(component_type, severity)
                │
                │ selects strategy
                ▼
     ┌──────────────────────────────────────────┐
     │           <<interface>>                  │
     │           AlertStrategy                  │
     │                                          │
     │  + alert(context: AlertContext) → None   │
     │  + priority → str                        │
     └──┬──────────┬──────────┬──────────┬──────┘
        │          │          │          │
  ┌─────▼──┐ ┌────▼───┐ ┌────▼───┐ ┌────▼───┐
  │  P0    │ │  P1    │ │  P2    │ │  P3    │
  │Critical│ │  High  │ │ Medium │ │  Low   │
  │        │ │        │ │        │ │        │
  │ RDBMS  │ │  API   │ │ Cache  │ │ Default│
  │MCP_HOST│ │ Queue  │ │ NoSQL  │ │        │
  └────────┘ └────────┘ └────────┘ └────────┘
```

**Component Mapping**:
| Component Type | Default Priority | Override |
|---|---|---|
| RDBMS, MCP_HOST | P0 | Severity P0/P1 always wins |
| API, ASYNC_QUEUE, LOAD_BALANCER | P1 | — |
| CACHE, NOSQL | P2 | — |
| Unknown | P3 | — |

---

## 3. Observer Pattern — WebSocket Manager

**File**: `backend/app/websocket/manager.py`

All connected dashboard clients are subscribers. When an incident is created or a state transition occurs, `ws_manager.broadcast()` pushes the event to ALL subscribers simultaneously.

---

## 4. Circuit Breaker

**File**: `backend/app/utils/retry.py`

Prevents cascading failures when a downstream service (e.g., PostgreSQL) goes down.

```
        CLOSED                   OPEN
    (Normal operation) → 5 failures → (Reject all calls)
           ↑                                  │
           │                          30s recovery
           │                                  │
           └──── success ─── HALF_OPEN ←──────┘
                              (Test one call)
```

---

## 5. Producer-Consumer (Kafka Pipeline)

Decouples the high-throughput ingestion path from the slower persistence path. The `asyncio.Queue` between them provides in-process backpressure.

---

## 6. Token Bucket Rate Limiter

Implemented as a Redis Lua script for atomic, distributed rate limiting. The script runs atomically — no race conditions even with multiple backend instances.
