# Implementation plan

Status vocabulary: Not started / In progress / Implemented / Tested / Verified. Update rows as work completes; record verification commands in `DOCUMENTING.md` §10.

## Phase 1 — Requirements & architecture (current)
Deliverables: MVP scope, API draft, auth/tenant model, job state machine, ADR-001..003, architecture, test strategy.
Exit: this document set complete and consistent.

## Phase 2 — Application foundation
- `core/settings.py` (pydantic-settings, `.env`), failure-fast on missing values.
- `db/` async engine + session factory; `connect_args` capped pool sizing.
- Alembic wired to app models; `001_initial` migration.
- Error envelope + handlers; request-ID + logging middleware; `/health` (liveness), `/ready` (DB check), `/metrics`.
- pytest fixtures: event loop, DB bring-up, ASGI client.
Exit: empty database migrates cleanly; liveness/readiness tests pass from documented commands.

## Phase 3 — Identity & access
- Register/login/logout; argon2id hashing via pwdlib; opaque session tokens (hashed, expiry, rotation).
- API keys (creation returns plaintext once, hash stored, `last_used_at`).
- Workspaces + memberships + roles (owner/admin/member); ownership dependency discipline; audit events for auth-sensitive actions.
Exit: cross-tenant isolation tests prove guessing IDs / tampered params cannot read or mutate foreign resources.

## Phase 4 — Durable jobs + reference workload
- Domain `jobs` + `job_attempts`; state machine with illegal-transition rejection.
- Enqueue-after-commit; consumer `report.generate` writes an artifact to `data/artifacts/` (path validated), sets result metadata (rows, bytes, sha256).
- Retry policy: retryable vs non-retryable, deferred backoff (exponential + jitter), max attempts → terminal failed; timeouts via wait_for wrapper marked `timed_out` error; cancellation (cooperative, terminal `cancelled` with reason); recovery sweep for crashed workers.
Exit: tested paths = success, failure, retry, timeout, cancel, duplicate submit guarded (Phase 5 key), worker kill mid-run recovery.
## Phase 5 — Idempotency & event reliability
- `idempotency_keys` unique (workspace_id, key); request-hash conflict → 409 with `Conflict:Idempotency-Key-reuse`; completed responses replayed byte-for-byte status/body/headers; in-flight → 409 + Retry-After.
- Enqueue commitment: enqueue only when row commit succeeded (post-commit hook); duplicate-delay test.
Exit: duplicate requests and transient queue/DB failures behave deterministically; documented.

## Phase 6 — Rate limits & webhooks
- In-process fixed-window limiter per user; `429` + `Retry-After`; per-plan defaults from settings.
- `webhook_endpoints` + `webhook_deliveries`; HMAC-SHA256 signature headers (`timestamp`, `signature`), attempt schedule with exponential backoff, terminal failure state with history; delivery driven by worker (job lifecycle hooks).
Exit: each feature has contract, tests, config, ops notes; only features the workload exercises are built (cache deliberately absent, ADR-002).

## Phase 7 — Observability & operations
- Prometheus metrics: HTTP hist (method/route/status), job transitions, webhook attempts, queue depth gauge, limiter rejects.
- Structured logs w/ redaction; correlation IDs across API and worker.
- Runbooks: stuck queue, failed jobs, migration failure, broken readiness, webhook blast.
Exit: a developer can diagnose a failed request/job end-to-end from documented signals.

## Phase 8 — Hardening & delivery
- Load test scripts + versioned manifest (p50/p95/p99, throughput, error rate; stated hardware).
- Security tests (ownership matrix in tests), secret redaction test, dependency-restart resilience notes.
- Compose verified path; single-node deployment doc; backup/restore via pg_dump scripts.
Exit: clean clone start → migrate → run workload → tests → clean shutdown, no undocumented manual steps.

## Dependency graph

2 → 3 → 4 → 5 → (6,7 parallel) → 8. Phases never skip exits; journal updated each time.
