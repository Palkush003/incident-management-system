# Architecture Decision Records (ADRs)

This document captures the "why" behind the specific technical trade-offs made in the Incident Management System.

## ADR 001: Use of Kafka for Signal Ingestion
- **Status**: Accepted
- **Context**: The system must handle bursts of 10,000 signals/sec. Direct database writes would cause thread/connection pool exhaustion and cascading failures.
- **Decision**: Introduce a message broker (Kafka) between the API and the Processor.
- **Consequences**: 
    - (+) Decouples ingestion latency from processing latency.
    - (+) Provides 24-hour durability if consumers are down.
    - (-) Increases system complexity (requires Zookeeper/Kafka).
    - (-) Introduces eventual consistency for the audit log.

## ADR 002: Polyglot Persistence (PostgreSQL + MongoDB)
- **Status**: Accepted
- **Context**: Raw signals are high-volume and unstructured. Work Items and RCAs are structured and require ACID transactions.
- **Decision**: Use MongoDB as a "Data Lake" for raw signals and PostgreSQL as the "Source of Truth" for lifecycle management.
- **Consequences**:
    - (+) MongoDB scales horizontally for high-write volume.
    - (+) PostgreSQL ensures strict relational integrity for incident transitions.
    - (-) Operational overhead of managing two database types.

## ADR 003: State Pattern for Lifecycle Management
- **Status**: Accepted
- **Context**: Transitioning an incident from `RESOLVED` to `CLOSED` requires complex validation (e.g., checking if an RCA exists).
- **Decision**: Implement the State Pattern in `app/engine/workflow.py`.
- **Consequences**:
    - (+) Eliminates "Spaghetti Code" conditionals (`if status == ...`).
    - (+) Makes the lifecycle easily extensible (e.g., adding an `ON_HOLD` state).
    - (+) Centralizes audit logging for every transition.

## ADR 004: Redis-based Token Bucket Rate Limiter
- **Status**: Accepted
- **Context**: Ingestion must be protected from DDoS or misconfigured clients.
- **Decision**: Implement a distributed rate limiter using Redis Lua scripts.
- **Consequences**:
    - (+) High performance (sub-millisecond overhead).
    - (+) Shared state across multiple API instances.
    - (+) Supports "Burstiness" while maintaining a strict long-term rate.

## ADR 005: LLM Gateway with Spend Observability
- **Status**: Accepted
- **Context**: AI cost can be unpredictable during a "Signal Storm."
- **Decision**: Route all LLM traffic through a custom `LLMGateway` that tracks tokens and financial spend *before* persisting data.
- **Consequences**:
    - (+) Prevents "Bill Shock" via automated cost-based rate limiting.
    - (+) Provides business-level visibility into AI ROI.
    - (-) Increases latency for RCA generation by ~100ms for tracking logic.
