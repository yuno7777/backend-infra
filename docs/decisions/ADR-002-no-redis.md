# ADR-002 — Redis is excluded from the MVP

**Status:** Accepted (2026-11-03)
**Context:** The operating contract allows Redis "only for a defined purpose" (cache, broker, rate-limit counters, coordination). Recon found no running Redis and no Docker on this host. The queue decision (ADR-001) removes the broker role.

**Decision.** MVP ships without Redis.
- Cache: nothing in the reference workload justifies one yet; PostgreSQL-backed query workloads stay within a single round-trip.
- Broker: Procrastinate (ADR-001).
- Rate limiting: honest single-node in-process fixed-window limiter, documented as per-process; revisit with Redis (or a shared store) when multi-instance deployment becomes a real requirement (Phase 6 decision doc).

**Consequences.** Fewer services to run and test honestly; `.env.example` and compose have no Redis service; the deployment doc stays consistent with what runs here. Any future introduction of Redis must come with an ADR describing the measured need.
