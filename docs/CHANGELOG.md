# Changelog

## 2026-11-03 — Foundation and identity slice

- Added application foundation, initial migration, health/readiness and consistent request/error handling.
- Added registration, login/logout, session and API-key authentication, workspace membership/roles, tenant scoping and audit events.
- Fixed role dependency injection after four auth tests exposed an `Annotated` alias runtime error.
- Verification: `pytest tests -q` — 17 passed; `ruff check backend tests` — all checks passed.

## 2026-11-03 — Phase 0 & foundation of Phase 1

- Phase 0 recon completed and recorded (env table in DOCUMENTING.md §2): Python 3.13.15, git 2.55, Docker CLI present but daemon absent, no native PG/Redis, port 8000 occupied by unrelated user process.
- Decisions: ADR-001 queue = Procrastinate (Postgres-backed); ADR-002 Redis excluded from MVP; ADR-003 portable EDB Postgres binaries via script, compose as alternate path.
- Repo skeleton created: package layout `backend/app/*`, `migrations/`, `tests/`, `scripts/dev/`, docs directory with journal + architecture + ADRs.
- EDB binaries download for PostgreSQL 17.8 initiated for local dev cluster.
