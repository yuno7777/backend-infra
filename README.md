# Backend Infra

An API-first backend foundation built with FastAPI and PostgreSQL. The project uses a modular monolith: the API and worker run as separate processes from one codebase, with PostgreSQL as the system of record.

| Project status | Details |
| --- | --- |
| Implemented | Application foundation, authentication, API keys, workspace roles, tenant scoping, and identity audit records |
| In progress | Durable background jobs and the report-generation workload |
| Runtime | Python 3.13, FastAPI, SQLAlchemy, Alembic, PostgreSQL |

The [engineering journal](docs/DOCUMENTING.md) tracks implementation status, decisions, verification, and known limitations.

## Capabilities

- Versioned HTTP API with request IDs, a consistent error format, health and readiness endpoints, and request-size limits
- User registration, login, logout, and bearer-token sessions
- Workspace membership and role checks
- API-key creation, authentication, and revocation
- Workspace-scoped authorization for sessions and API keys
- PostgreSQL persistence, Alembic migrations, and audit records for identity operations

Job, idempotency, webhook, and report-generation components are not yet complete end-to-end features. The worker workload is the next implementation phase.

## Architecture

The API and worker share application code and a PostgreSQL database. PostgreSQL is also the planned queue backend, avoiding a separate broker in the initial deployment. Redis is not part of the current design.

See [Architecture](docs/ARCHITECTURE.md) and the [architecture decisions](docs/decisions/) for details.

## Local setup

The Windows development setup uses a portable PostgreSQL 17 cluster on loopback. The provisioning script downloads the PostgreSQL binaries on first use. Docker is not required for local development.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
powershell -ExecutionPolicy Bypass -File scripts\dev\setup_local_postgres.ps1
Copy-Item .env.example .env
```

Generate a value for `TOKEN_HASH_PEPPER`:

```powershell
.venv\Scripts\python -c "import secrets; print(secrets.token_hex(32))"
```

Set that value in `.env`, then apply the schema and start the API:

```powershell
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8080
```

Available endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Process liveness |
| `GET /ready` | Readiness, including database connectivity |
| `GET /docs` | Interactive OpenAPI documentation |

The API listens at `http://127.0.0.1:8080` with these commands. See [Deployment](docs/DEPLOYMENT.md) for the container setup. Docker and Compose have not been verified on the development host.

## Authentication and workspaces

Identity routes are under `/v1/auth`. Workspace and membership routes are under `/v1/workspaces`. Protected endpoints use bearer authentication. Session-authenticated workspace requests require an `X-Workspace-Id` header. API keys are bound to a workspace and role.

Refer to the [API specification](docs/API_SPECIFICATION.md) for request and response details.

## Verification

Run the test suite with the local PostgreSQL instance available and `.env` configured:

```powershell
.venv\Scripts\python -m pytest tests -q
.venv\Scripts\python -m ruff check backend tests
```

Latest verified baseline: 17 tests passed and Ruff reported no issues. Docker integration and load behavior remain unverified.

## Repository map

```text
backend/app/       API, configuration, database, domain, models, and services
migrations/        Alembic schema migrations
scripts/dev/       Local PostgreSQL provisioning
tests/             Unit and PostgreSQL-backed integration tests
docs/              Architecture, API, operations, decisions, and engineering journal
docker/            Container assets
```

## Roadmap

| Phase | Work |
| --- | --- |
| 1. Background jobs | Report submission, durable queueing, worker execution, progress, status, and result retrieval |
| 2. Job reliability | Retry policy, timeouts, cancellation, deduplication, crash recovery, and failure inspection |
| 3. Event delivery | Signed webhooks, retry history, and single-node rate limiting where justified |
| 4. Operations | Job and request metrics, structured logs, correlation, and runbooks |
| 5. Hardening | Security review, failure-path coverage, deployment checks, Compose verification, and reproducible load tests |

The report-generation job is the next vertical slice. It will exercise persistence, queueing, worker execution, retry behavior, status tracking, and result storage together.

## Project documents

- [API specification](docs/API_SPECIFICATION.md)
- [Database schema](docs/DATABASE_SCHEMA.md)
- [Jobs and reliability](docs/JOBS_AND_RELIABILITY.md)
- [Security](docs/SECURITY.md)
- [Operations runbook](docs/OPERATIONS_RUNBOOK.md)
- [Engineering journal](docs/DOCUMENTING.md)
- [Changelog](docs/CHANGELOG.md)
