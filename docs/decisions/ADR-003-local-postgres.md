# ADR-003 — Local PostgreSQL via portable EDB binaries (no Docker, no admin), compose shipped as the portable alternative

**Status:** Accepted (2026-11-03)
**Context:** Phase 0 recon: no Docker daemon, no native Postgres service. Integration tests must run against a real PostgreSQL (contract rule), not stubbed substitutes.

**Decision.**
1. `scripts/dev/setup_local_postgres.ps1` (and a bash twin later if needed) downloads the official EnterpriseDB *portable binaries zip* (version pinned in the script), extracts the bundle into `local/pgsql/` (gitignored), creates `local/pgdata/` via `initdb` with scram auth for user `backend_infra`, and starts a loopback-only cluster on port 54329. Password is generated into `local/pg-password.txt` (gitignored) and synced into `.env`.
2. `docker-compose.yml` remains the documented path for hosts with Docker (postgres 17-alpine), giving `scripts/dev` parity without a daemon requirement here.
3. Nothing in `local/` is ever committed; credentials never enter git or docs.

**Consequences.** Integration tests run against real PostgreSQL — local fidelity including the locking semantics the queue needs. The binaries live under `local/postgres`; upgrading means re-downloading, and the data folder is disposable dev data. Not a production cluster; `DEPLOYMENT.md` covers the real single-node deployment.
