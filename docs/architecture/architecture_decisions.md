# Architecture Decision Records (ADRs)

This document captures the rationale behind the technical trade-offs made in the Incident Management System.

## ADR 001: Use of Kafka for Signal Ingestion
- **Status**: Accepted
- **Context**: The system must handle bursts of 10,000 signals/sec. Direct database writes would cause connection pool exhaustion during peak loads.
- **Decision**: Introduce a message broker (Kafka) between the API and the Processor.
- **Consequences**: 
    - (+) Decouples ingestion latency from processing latency.
    - (+) Provides durability if consumer services are down.
    - (-) Increases system complexity.

## ADR 002: Polyglot Persistence (PostgreSQL + MongoDB)
- **Status**: Accepted
- **Context**: Raw signals are high-volume and unstructured, whereas Work Items require relational integrity and ACID transactions.
- **Decision**: Use MongoDB for raw payloads and PostgreSQL for the structured lifecycle management.
- **Consequences**:
    - (+) MongoDB scales for high-write volume.
    - (+) PostgreSQL ensures strict relational integrity for incident transitions.
    - (-) Management of two database systems.

## ADR 003: State Pattern for Lifecycle Management
- **Status**: Accepted
- **Context**: Transitioning incident status requires complex validation (e.g., mandatory RCA check).
- **Decision**: Implement the State Pattern in `app/engine/workflow.py`.
- **Consequences**:
    - (+) Eliminates complex conditional logic in the API.
    - (+) Makes the lifecycle easily extensible.
    - (+) Centralizes audit logging for state changes.

## ADR 004: Redis-based Token Bucket Rate Limiter
- **Status**: Accepted
- **Context**: Ingestion must be protected from over-utilization.
- **Decision**: Implement a distributed rate limiter using Redis Lua scripts.
- **Consequences**:
    - (+) Sub-millisecond performance overhead.
    - (+) Shared state across all API instances.

## ADR 005: LLM Gateway with Spend Observability
- **Status**: Accepted
- **Context**: External API costs must be monitored and capped.
- **Decision**: Route traffic through a custom Gateway that tracks tokens and cost.
- **Consequences**:
    - (+) Prevents excessive costs via automated rate limiting.
    - (+) Provides real-time visibility into operational spend.
