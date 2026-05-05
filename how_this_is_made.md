# Technical Deep Dive: How This Project Was Built

This document provides a comprehensive overview of the engineering decisions, architecture, and implementation details behind the Incident Management System (IMS).

## 1. Core Architecture: The Decoupled Pipeline

The central challenge of this system was to handle massive bursts of data (10,000 signals/sec) without compromising system stability or data integrity.

### Ingestion Flow
1.  **FastAPI Gateway**: A lightweight entry point that performs immediate Pydantic validation and Token Bucket rate limiting.
2.  **Asynchronous Buffering**: Validated signals are placed into an in-memory `asyncio.Queue` to absorb micro-bursts.
3.  **Durable Transport (Kafka)**: Signals are then pushed to a Kafka topic (`raw-signals`). This ensures that even if downstream processors are slow or down, the data is safely persisted.
4.  **Partitioning**: Data is partitioned by `component_id`. This guarantees that signals for the same service are processed in chronological order while allowing multiple consumers to scale horizontally for parallel processing.

## 2. Polyglot Persistence Strategy

Different data types in this system have different requirements, leading to the use of three distinct databases:

-   **MongoDB (The Data Lake)**: Stores high-volume, unstructured raw signal payloads. MongoDB was chosen for its horizontal write scalability and flexible schema.
-   **PostgreSQL (The Source of Truth)**: Manages structured Work Items and Root Cause Analysis (RCA) records. PostgreSQL provides the ACID transactions necessary for reliable incident lifecycle management.
-   **Redis (The Hot-Path)**: Handles three critical low-latency tasks:
    -   **Rate Limiting**: Atomic Lua scripts manage the distributed Token Bucket.
    -   **Debouncing**: Tracks active signal windows to prevent duplicate incident creation.
    -   **Dashboard Caching**: Stores the current state of the dashboard to avoid expensive relational queries on every UI refresh.

## 3. Implementation of Key Logics

### Sliding-Window Debouncing
To prevent alert fatigue, the `Debouncer` logic (implemented in `backend/app/engine/debouncer.py`) checks if an incident for a specific component has been created within the last 10 seconds.
- If an active window exists, the signal is linked to the existing Work Item, and the counter is incremented.
- If no window exists, a new Work Item is created, and the window is initialized in Redis.

### State Pattern for Lifecycle Management
The incident lifecycle (OPEN → INVESTIGATING → RESOLVED → CLOSED) is managed via the **State Pattern**. This encapsulates the rules for each state into its own class:
- **Validation**: For example, the `ResolvedState` class contains a hard check that prevents a transition to `CLOSED` unless an RCA record is present in the database.
- **Audit Logging**: Every transition automatically creates a record in the `state_transitions` table in PostgreSQL.

### Strategy Pattern for Alerting
Alert routing depends on both the component type and the severity. The `AlertDispatcher` uses the **Strategy Pattern** to swap alerting logic dynamically:
- **P0 Strategy**: Triggers a critical alert (simulated PagerDuty/SMS).
- **P2 Strategy**: Triggers a standard notification (Slack/Console).

## 4. Resilience & Reliability Features

### 4-Layer Backpressure
The system is designed to survive "Signal Storms" through four defensive layers:
1.  **Global Rate Limiting**: Redis-based throttling at the edge.
2.  **In-Memory Queueing**: Buffering inside the Python process.
3.  **Durable Messaging**: Offloading to Kafka.
4.  **Circuit Breakers**: Protecting downstream databases from being overwhelmed during recovery.

### Automatic MTTR Calculation
The Mean Time To Repair (MTTR) is calculated automatically upon RCA submission. The system fetches the `created_at` timestamp of the very first signal that triggered the incident and compares it with the current timestamp of the RCA record creation.

## 5. Observability & Monitoring

The system exports deep visibility metrics to a Prometheus/Grafana stack:
- **Processing Latency**: Tracks how long it takes from ingestion to persistence.
- **Saturation**: Monitors Kafka consumer lag and dropped signal counts.
- **Intelligent Analysis (LLM Gateway)**: All calls for automated analysis are routed through a gateway that monitors token usage and financial spend, allowing for cost-based quotas.

## 6. Verification Suite

-   **Chaos Monkey Simulator**: A standalone script that mocks massive failure events (e.g., RDBMS outages) to verify that the backpressure and recovery mechanisms work as intended.
-   **Unit Tests**: A suite of 56 tests covering everything from state transitions to MTTR math accuracy.

---
*This system represents a robust implementation of modern distributed systems principles, focusing on reliability, scalability, and strict data governance.*
