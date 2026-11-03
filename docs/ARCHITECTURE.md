# Architecture

## Topology (MVP)

Modular monolith: **one API process + one worker process over one PostgreSQL database.** No service mesh, no per-domain microservices.

```text
            ┌──────────────┐         ┌────────────────┐
 clients ──▶│  API (uvicorn│──write──▶│  PostgreSQL    │
            │  FastAPI)    │◀─read───│  system of      │
            └──────┬───────┘         │  record         │
                   │ enqueue (after commit)  │  app tables     │
                   ▼                 │  queue tables   │
            ┌──────────────┐         └───────┬────────┘
            │ Worker (proc.│◀──dequeue (SKIP LOCKED)─┘
            │ procrastinate│─writes─▶ state transitions, results,
            └──────────────┘          audit, webhook deliveries
```

Domain tables (`docs/DATABASE_SCHEMA.md`) are the API-facing truth; Procrastinate's queue tables are transport internals. Clients and handlers never touch the queue tables directly.

## Request lifecycle

`Client → Middleware (request id / structured logging / size limit) → Authentication (session token or API key) → Authorization (workspace membership + role) → Validation (Pydantic) → Service (use case) → Repository (transaction) → Response (consistent envelope)`

- Every response carries `X-Request-ID`; every server log line carries the same `request_id` plus `user_id`, `workspace_id`.
- Errors always use the documented envelope in `API_SPECIFICATION.md`.
- Authorization is enforced in service/dependency layer, never inferred from the client.

## Job lifecycle

States: `queued → running → succeeded | failed | cancelled` (terminal), with `failed` carrying attempt info and error codes. Retryable vs non-retryable classification lives in `domain/jobs.py`. Full contract: `JOBS_AND_RELIABILITY.md`.

Worker responsibilities: attempt bookkeeping, backoff with jitter, hard timeout wrapper (`asyncio.wait_for`), heartbeats (`heartbeat_at`), cooperative cancellation, and a startup **recovery sweep** that re-queues or fails domain jobs stuck in `running` whose lease (heartbeat age) expired after a crash.

## Module boundaries

- `api/` routers stay thin: parse, authorize (via dependencies), call one service, shape response.
- `services/` orchestrate domain + repositories; they own authorization rules, audit emission, idempotency, and enqueue-after-commit decisions.
- `repositories/` own all SQL; scoped by `workspace_id` at write time so cross-tenant filtering is structural.
- `domain/` pure state transitions with no IO — unit-testable.
- `workers/` never serve HTTP; they drive domain state via services.
- `core/` config (pydantic-settings), logging (structlog), error envelope, metrics registry, limiter.

## Security boundary summary

- Identity: password sessions (opaque bearer, hashed at rest) + workspace-scoped API keys (hashed, shown once).
- Tenancy: every tenant-owned row carries `workspace_id`; every repository query is workspace-scoped; ownership preloads throw `404` (not `403`) on foreign resources to avoid existence leaks.
- Audit: `audit_events` for auth/key/job/webhook/cancel and role changes. Details in `SECURITY.md`.

## Not in scope (recorded to keep boundaries honest)

Kubernetes, multi-region, workflow engine, object storage service, outbox table (Procrastinate enqueue-after-commit covers MVP; revisit in Phase 5 with a test), OTel traces (later), UI console.
