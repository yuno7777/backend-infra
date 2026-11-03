# Deployment

## Local (this repo, no Docker required — verified path)

1. `python -m venv .venv; pip install -e ".[dev]"`.
2. `scripts/dev/setup_local_postgres.ps1` — downloads pinned portable Postgres (already excluded by ADR-003 from being a build step on hosts that have their own Postgres; if Docker is available, `docker compose up -d postgres` runs the equivalent).
3. Copy `.env.example` → `.env`; the setup script fills DATABASE_URL & generated pepper where safe; required values listed in `.env.example`.
4. `alembic upgrade head` (migrations are the schema source of truth).
5. Start: `uvicorn backend.app.main:app --port 8080` + worker: `python -m backend.app.workers.run` (worker must run separately — never same command as API).
6. Verify: `curl /health`, `curl /ready`, then run the sample job (`scripts/sample_job.ps1`) and audit its completion; run `pytest` seriously before the first write-bearing commit; worker `Ctrl+C` for graceful stop (in-flight attempt completes or is re-queued by recovery sweep).

## Single-node deployment (documented path — not exercised on this host)

- 3 processes: reverse proxy (Caddy / nginx) serving TLS, API (single uvicorn worker per core decision), one worker instance (concurrency from settings), and PostgreSQL system-of-record service.
- Deployment assumptions: single data dir for artifacts on a persistent volume; DB backups via `pg_dump` per documented schedule in OPERATIONS_RUNBOOK; logs journald with 7-14d retention, each entry JSON for easy aggregation.
- HA NOT claimed: one Postgres instance is the SPOF. Multi-region/Kubernetes explicitly out of MVP; documenterc expectations honestly.
- Migration ordering during updates: stop worker → alembic upgrade → restart API+worker (reverse proxy can buffer 502s during the ~seconds window; not zero-downtime guarantees).
- Verification before claiming anything: only claims backed by scripts and benchmark manifest.

## Offline deployment sanity checklist

- [ ] `.env`: DATABASE_URL/APP/TOKEN_SECRET/peppers, log format, port; listed in .env.example.
- [ ] `scripts/dev/setup_local_postgres.ps1` did or compose did for this host.
- [ ] Migrations applied via alembic; then app start.
- [ ] Ready check returned `database: ok`.
- [ ] Reference workload verified through the checklist steps in README.
