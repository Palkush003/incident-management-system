# Interview Cheat Sheet: The SRE Job Fetcher

If you are asked about this project in an interview, use these "Power Responses" to demonstrate senior-level competency.

## 1. "How do you handle high throughput (10K/s)?"
- **Answer**: "I implemented a multi-layer backpressure strategy. Instead of hitting the DB directly, I use a distributed Token Bucket (Redis) for traffic control, followed by an in-memory buffer, and finally a Kafka durable queue. This ensures that even if our persistence layer lags, we never drop a signal or crash the process."
- **Keywords**: *Backpressure, Decoupling, Durability, Token Bucket.*

## 2. "How do you ensure data consistency in a distributed system?"
- **Answer**: "For the incident lifecycle, I used the **State Pattern**. This ensures that status transitions are strictly enforced at the code level. For example, an incident literally cannot reach a 'CLOSED' state unless the system validates that an RCA record has been committed. This turns a business rule into a technical invariant."
- **Keywords**: *State Machine, Invariants, ACID, Validation.*

## 3. "How do you handle observability?"
- **Answer**: "I don't just log errors; I export system behavior. I integrated a full Prometheus/Grafana stack that tracks P99 processing latency, signal drop rates, and Kafka consumer lag. Most uniquely, I built an **LLM Gateway** that treats AI as a first-class citizen with its own spend and token observability metrics."
- **Keywords**: *SLIs/SLOs, Histograms, LLMOps, Financial Observability.*

## 4. "Tell me about a time you handled a failure." (The Chaos Monkey)
- **Answer**: "I built a Chaos Simulator for this system to proactively find bottlenecks. I simulated a total PostgreSQL outage and observed how the Kafka buffer safely held the signal data until the DB was restored. This allowed me to fine-tune the **Circuit Breaker** settings to prevent a thundering herd during recovery."
- **Keywords**: *Chaos Engineering, Fault Tolerance, Circuit Breaker, Thundering Herd.*

## 5. "Why did you use both SQL and NoSQL?"
- **Answer**: "It's about 'The Right Tool for the Job.' MongoDB handles the high-velocity, write-heavy stream of raw signal payloads (The Data Lake). PostgreSQL handles the relational, transactional state of Work Items (The Source of Truth). This separation allows us to scale ingestion and management independently."
- **Keywords**: *Polyglot Persistence, Separation of Concerns, Horizontal Scaling.*

---
### 💡 Pro Tip for the Interview:
Point the interviewer to the `README.md` and the `docs/sre-philosophy/` folder. Most candidates provide just code; you are providing **System Design and Engineering Rationale**.
