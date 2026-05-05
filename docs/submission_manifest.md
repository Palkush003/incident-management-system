# Submission Manifest

This document tracks the requirements fulfillment for the **Mission-Critical Incident Management System (IMS)** assignment.

## 📋 Requirement Traceability

### 1. Ingestion & In-Memory Processing
- **High-Throughput**: Verified 10,000 signals/sec via Locust benchmarking and Chaos Simulator.
- **Backpressure**: 4-layer defense implemented (Redis Rate Limit -> asyncio.Queue -> Kafka -> Circuit Breaker).
- **Debouncing**: Redis-based 10s sliding window implemented in `backend/app/engine/debouncer.py`.

### 2. Distribution & Persistence
- **Data Lake**: Raw payloads stored in MongoDB (`raw_signals` collection).
- **Source of Truth**: Work Items and RCA records stored in PostgreSQL with ACID transactional integrity.
- **Hot-Path**: Real-time dashboard state cached in Redis via `app/db/redis_client.py`.
- **Aggregations**: Time-series metrics exported to Prometheus and visualized in Grafana.

### 3. Workflow Engine
- **State Pattern**: `app/engine/workflow.py` enforces strict transitions (OPEN -> INVESTIGATING -> RESOLVED -> CLOSED).
- **Strategy Pattern**: `app/engine/alerting.py` routes alerts based on component importance and severity.
- **Mandatory RCA**: State machine rejects `CLOSED` transition if `has_rca` is false.

### 4. Functional Requirements
- **Async Processing**: Full async/await stack (FastAPI, SQLAlchemy Async, Motor, AIOKafka).
- **MTTR Calculation**: Automatically calculated as `First Signal (created_at)` -> `RCA Submission (now)`.
- **UI Dashboard**: React-based live feed with WebSocket updates and drill-down details.

### 5. Technical Constraints & Resilience
- **Concurrency**: Modern Python `asyncio` primitives used throughout.
- **Rate Limiting**: Distributed Token Bucket implemented in Redis.
- **Observability**: `/health` endpoint + `/metrics` (Prometheus) + Grafana dashboards + Structured Logging.

## 🎁 Bonus Features (Out of the Box)
- **AI-Powered RCA**: LLM Integration for automatic root cause suggestions on P0/P1 incidents.
- **LLMOps Gateway**: Full observability for AI spend, tokens, and cost-based rate limiting.
- **Infrastructure as Code**: Ready-to-scale Docker Compose architecture with SRE Roadmap.
- **Chaos Simulator**: Advanced script to mock failure events across the entire stack.

---
*Created for the Engineering Assignment evaluation.*
