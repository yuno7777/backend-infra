# Backend Infra — Engineering Journal (DOCUMENTING.md)

> Single source of truth for status, decisions, and verification results. Update after every phase and meaningful fix. Append fresh verification results; never rewrite historical outcomes.

---

## 1. Objective, scope, users, status

- **Product:** Self-hostable, API-first backend foundation: versioned APIs, auth/tenancy, durable background jobs, idempotency, audit, observability, webhooks, plus one reference workload (report generation).
- **Users:** Backend engineers embedding a reliable foundation under their product; solo developer maintaining it.
- **Scope (MVP):** API versioning + validation + error envelope + OpenAPI; auth (password sessions + API keys); workspaces/memberships/roles; PostgreSQL + SQLAlchemy + Alembic; Postgres-backed durable queue + worker; job state machine with retries/timeouts/cancellation; idempotency keys on job submission; structured logs, request IDs, health/readiness, Prometheus metrics; audit events; signed webhooks with delivery history; local setup scripts; tests.
- **Non-goals (first iteration):** Kubernetes, multi-region, microservices per domain, workflow engine, custom broker, custom crypto, UI-heavy product.
- **Status:** Phase 0 done (below). Phases 1+ tracked in `IMPLEMENTATION_PLAN.md`.

## 2. Phase 0 — environment reconnaissance (actual, 2026-11-03)

| Item | Value |
|---|---|
| OS | Windows 10/11 era host, PowerShell 5.1 (`win32`), workdir `C:\Users\Abhi\Desktop\resume projects\backend-infra` |
| Python | 3.13.15 |
| Node/npm | 24.19.0 / 11.17.0 (present; not needed for MVP) |
| Git | 2.55.0.windows.3 |
| Docker | CLI 29.9.1 present; **daemon NOT running**; Docker Desktop exe missing; leftover `docker-desktop` WSL distro (stopped) |
| PostgreSQL native | **Not installed** (`psql` absent, no service) |
| Redis / Memurai | **Not installed** |
| Ports | 8000 in use by an unrelated user process (python, PID 26776) — API will use **8080**; PG dev port **54329** |
| Repo state | Empty directory → greenfield build; git initialized on `main` |
| Resources | winget available; local dirs writable; containers impractical on this host |

**Consequences recorded as ADRs:**
- ADR-001: Postgres-backed queue (Procrastinate) instead of Celery/ARQ/Dramatiq+Redis.
- ADR-002: Redis excluded from MVP (no justified role once the queue is Postgres-backed; rate limiting is single-node in-process for MVP).
- ADR-003: Local PostgreSQL is provisioned natively on this host via portable EDB binaries (no admin/Docker) by `scripts/dev/setup_local_postgres.ps1`; docker-compose still shipped for hosts that prefer it.

## 3. Architecture summary

Modular monolith: one FastAPI API process + one worker process (same codebase, separate entrypoints), shared PostgreSQL. Details: `ARCHITECTURE.md`. Request flow: middleware (request id/logging) → authn → authz → validation → service → repository/transaction → response. Job flow: `queued → running → succeeded | failed | cancelled` with attempts, backoff+jitter, timeout, heartbeats, crash recovery sweep, DL state.

## 4. Technology choices

| Choice | Alternative(s) considered | Reason |
|---|---|---|
| FastAPI + Pydantic v2 | Flask/Django, Litestar | Async-native, mature, OpenAPI built-in, fits API-first goal |
| SQLAlchemy 2.0 + Alembic | Django ORM, raw SQL | Explicit Core 2.0 style, typed, migrations as source of truth |
| psycopg 3 | psycopg2, asyncpg | Modern, async, maintained; SQLAlchemy async support |
| Procrastinate (Postgres queue) | Celery+Redis, Dramatiq+Redis, ARQ+Redis, RQ | Durability on the system of record, no extra broker this host cannot run, real retry/locking semantics; comparison in ADR-001 |
| pwdlib (argon2id) | passlib[bcrypt] (unmaintained/CPython 3.13 issues) | Maintained hashing lib |
| structlog | stdlib logging | Structured JSON by default in prod, readable console locally |
| No Redis (MVP) | Redis for cache/rate-limit | ADR-002 |
| In-process rate limiter | Redis-backed limiter, nginx limits | Single-node honesty; documented limitation |

## 5. Repository structure and module boundaries

```text
backend/app/
  api/        routers + auth/audit/limiter/idempotency dependencies (HTTP only)
  core/       settings, logging, errors, metrics, limiter, secrets
  db/         engine, session, base
  domain/     job state machine + domain enums/constraints (no IO)
  models/     SQLAlchemy entities
  repositories/ query layer, owned-by-workspace scoping
  schemas/    Pydantic DTOs
  services/   use-case orchestration (auth, jobs, reports, webhooks, audit)
  workers/    procrastinate app + tasks + retry/timeout/recovery driver
  main.py     ASGI app factory
migrations/   Alembic (schema source of truth)
tests/        unit + integration (real Postgres)
scripts/dev/  local provisioning + start scripts
docs/         journal + architecture + ADRs
docker/, docker-compose.yml, .env.example, README.md
```

Business rules live in `services/`/`domain/`; routers stay thin; repositories own SQL.

## 6. Implementation phases and status

| Phase | Scope | Status |
|---|---|---|
| 0 Reconnaissance | env report, stack constraints, ADR seeds | **Verified** (recorded above) |
| 1 Architecture & requirements | scope, API draft, state machine, ADRs, plan | **Implemented** |
| 2 App foundation | settings, startup, DB, migrations, errors, logging, health | **Implemented; tests pass** |
| 3 Identity & access | registration/login, sessions, API keys, memberships, tenant isolation, audit | **Implemented; tests pass** |
| 4 Durable jobs | submission, worker, retries, timeout, cancellation, recovery, report workload | Not started |
| 5 Idempotency & reliability | idempotency keys, enqueue/commit semantics | Not started |
| 6 Limits & webhooks | rate limiting, signed webhooks + delivery history | Not started |
| 7 Observability | metrics, correlation, runbooks | Not started |
| 8 Hardening & delivery | load tests, security tests, compose, deployment docs | Not started |

## 7. Implemented feature checklist

(Only list what code does today.)

- [x] Versioned health/readiness endpoints, request IDs, consistent error envelope, request-size limit.
- [x] User registration/login/logout, bearer sessions, API keys, workspace membership and role checks.
- [x] Workspace-scoped access for session and API-key principals; audit records for identity actions.

## 8. Schema/migration history & important ADRs

- ADR-001 queue choice; ADR-002 no Redis; ADR-003 portable Postgres (see `docs/decisions/`).
- Migrations: initial schema migration is present and applied by the test fixture.

## 9. Bugs, root causes, resolutions

- `require_role` initially used an `Annotated` dependency alias as a default value; FastAPI passed the alias object at runtime. Replaced it with `Depends(get_workspace_context)`; full suite passes.

## 10. Verification log (exact commands + outcomes)

Append-only. Format: date — command — outcome.

- 2026-11-03 — recon: `python --version` → 3.13.15; `docker info` → daemon error (npipe missing); `psql` absent; redis absent; port 8000 occupied by user process.
- 2026-11-03 — `curl -sI https://get.enterprisedb.com/postgresql/postgresql-17.8-1-windows-x64-binaries.zip` → 200, application/zip, 334,282,538 bytes.

## 11. Known limitations & security caveats

- Docker daemon unavailable on this dev host; integration tests must run against the native portable Postgres, and compose path is documented but unverified here.
- 8000/8080: user's unrelated process owns 8000; platform uses 8080.
- Local dev Postgres cluster is unauthenticated-to-LAN but password-auth (scram) on loopback-only port 54329; not a production cluster.
- No performance/scale claims made — load tests come in Phase 8 with recorded hardware context.

## 12. Next actions & current blocker

- Next: finish Phase 1 docs/ADRs → Phase 2 foundation code → apply initial migration → first API tests.
- Next: implement and verify the durable job/report workload (Phase 4), then idempotency and delivery reliability.
- Blocker: no current blocker for the verified foundation/auth slice. Docker/Compose integration remains unverified on this host.
