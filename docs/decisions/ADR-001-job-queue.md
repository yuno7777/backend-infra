# ADR-001 — Job queue: Postgres-backed Procrastinate instead of a Redis-brokered worker library

**Status:** Accepted (2026-11-03)
**Context:** Phase 4 requires durable background jobs with retries, timeouts, cancellation, failure inspection, and at-least-once semantics with idempotent effects. Rule 5 of the operating contract forbids adding Redis to look advanced; rule 2 says start with a modular monolith. Host recon (Phase 0): no Docker daemon, no native Redis, no Postgres service — but PostgreSQL is planned as the system of record regardless.

**Options compared.**

| Criterion | Procrastinate (PG queue) | Celery + Redis | Dramatiq + Redis | ARQ + Redis |
|---|---|---|---|---|
| Durability | Queue state stored on the system of record alongside our domain `jobs` table; SKIP LOCKED dequeue | Broker memory is a second store of truth; visibility timeouts approximate durability | Same second-store issue | Same second-store issue |
| Operational complexity | One datastore for API and queue; no broker to run | Redis service required | Redis, self-contained but still a broker | Redis required |
| Retry semantics | Built-in attempt counts, retryable exceptions, periodic jobs; we add domain-level backoff+jitter and timeout wrapper | Mature but heavyweight (Celery is far larger than our need and its config surface is broad) | Simple, close to our needs | Python 3.13 ok, but minimal retry tooling |
| Local development | Same Postgres we already need → zero extra services | Blocked on this host (no Redis, no Docker) | Blocked | Blocked |
| Ecosystem health | Active, maintained, async-first, psycopg3 support | Very mature, huge surface | Active, maintained | Active, maintained |
| Fit to promise | Enqueue-after-commit hooks cover queue/DB consistency (outbox-lite) | Multi-transport最后一次 major redesign costs | Good but Redis | Good but Redis |

**Decision.** Use Procrastinate 3.x as the queue/worker substrate against the same PostgreSQL. Keep the domain-level `jobs` table as the API-facing record of jobs (statuses, attempts, timeouts, results) and let the task layer be a thin driver that maps queue execution to domain state transitions. Cancellation is done by domain status checks + cooperative abort, because the queue cannot kill a running coroutine safely.

**Consequences.**
- At-least-once delivery; consumers must be idempotent (documented in `JOBS_AND_RELIABILITY.md`).
- No separate broker process; A single-node deployment has exactly three processes: API, worker, Postgres.
- Redis may be reintroduced later (cache, rate limits) by ADR when justified.
- Queue visibility/ops tooling reads both the domain `jobs` table and queue tables.

**Rejected** ideas this ADR forbids: adding a second database, Kafka, or a custom broker "future-proofing" without a measured need.
