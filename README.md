# Backend Infra

API-first backend foundation: versioned HTTP APIs with consistent error contracts, workspace-based tenancy, durable background jobs (Postgres-backed queue), idempotency, audit trail, signed webhooks, and Prometheus observability — with a report-generation reference workload exercising every primitive end to end.

Status, decisions, and exact verification commands: see [`docs/DOCUMENTING.md`](docs/DOCUMENTING.md) (engineering journal, single source of truth).

## Quickstart (no Docker required)

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
powershell -File scripts\dev\setup_local_postgres.ps1   # portable PG 17 on 127.0.0.1:54329 (re-run safely)
Copy-Item .env.example .env
.venv\Scripts\alembic upgrade head
.venv\Scripts\uvicorn backend.app.main:app --port 8080      # terminal 1: API
.venv\Scripts\python -m backend.app.workers.run             # terminal 2: worker
```

Then: `curl http://127.0.0.1:8080/health` → `{"status":"ok"}`, `curl http://127.0.0.1:8080/ready`.

Docker route (hosts with Docker): `docker compose up -d postgres` then the same app steps; see `docs/DEPLOYMENT.md`.

## Repository map

| Path | Contents |
|---|---|
| `backend/app/` | `api/` routers+deps · `core/` settings, logging, errors, metrics · `db/` engine+session · `domain/` state machine · `models/` SQLAlchemy entities · `repositories/` scoped queries · `schemas/` DTOs · `services/` use cases · `workers/` queue tasks+driver |
| `migrations/` | Alembic (schema source of truth) |
| `tests/` | unit + integration (real Postgres) |
| `scripts/` | `dev/` local setup, `sample_job.ps1` |
| `docs/` | journal, architecture, ADRs, runbook |
| `docker/`, `docker-compose.yml` | compose path for hosts that prefer it |

## Key docs

- [Architecture](docs/ARCHITECTURE.md) — boundaries, request/job lifecycles
- [API](docs/API_SPECIFICATION.md) — routes, auth, errors, pagination, idempotency
- [Jobs & reliability](docs/JOBS_AND_RELIABILITY.md) — state machine, retries, recovery
- [Security](docs/SECURITY.md) · [Schema](docs/DATABASE_SCHEMA.md) · [Observability](docs/OBSERVABILITY.md) · [Testing](docs/TESTING_STRATEGY.md) · [Deployment](docs/DEPLOYMENT.md) · [Runbook](docs/OPERATIONS_RUNBOOK.md)
- [Decisions](docs/decisions/) — ADR-001 queue choice · ADR-002 no Redis · ADR-003 local Postgres
