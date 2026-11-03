# Operations runbook

Prereqs: access to host + environment values; all paths relative to repo root.

## Migrations (apply / inspect / rollback)
- Apply: `alembic upgrade head` (drives worker downgrades; see DEPLOYMENT migration ordering)
- Inspect: `alembic current`, `alembic history --verbose`
- Rollback LAST APP ONLY (danger: delete-table verified via -??): `alembic downgrade -1` then re-apply; destructive rollback NOT safe on live data; restore from backup instead.

## Stuck jobs (queued beyond SLO)
1. `GET /metrics` → check `bf_queue_pending` and `bf_jobs_state_total{to="retry"}`.
2. If `pending > 0 and worker offline`: restart worker (`python -m backend.app.workers.run`); startup recovery sweep re-inherits heartbeat-stale `running` rows.
3. Worker running but queue stalls: inspect worker logs for task mapping errors (`unknown task` means queue/plugin config drift; requeue manually via scripts/ops/requeue.py).

## Failed jobs
- Inspect `GET /jobs/{id}` (admin-level includes attempts + error codes per attempt).
- fanout to `idempotent resubmission`: posting the same request with the same `Idempotency-Key` after a `failed` terminal attempt is allowed configuration; verify policy in JOBS_AND_RELIABILITY if uncertain.

## Readiness failing (`/ready` 503)
- DB `SELECT 1` failing with timeout → check `PGDATA` service; restart Postgres binary process. Worker restart not required.
- Slow reader (connections exhausted) → pool limit exhausted: raise `BF_DB_POOL_SIZE`; documented default 10 (connect pool usage must remain within DB max_connections).

## Webhook storm throttle
- Look at `webhook_deliveries` state counts; if a target floods failures, POST `POST /workspaces/{id}/webhook-endpoints/{id}/deactivate` (planned Phase 6 route) via admin token.

## Queue / DB incident: worker cannot dequeue
- Verify procrastinate tables exist (alembic current + SELECT COUNT(*) on procrastinate_jobs); check `procrastinate_app` config version mismatch (worker vs API schema change) requires both restarts.

## Downtime window policy
- Single-node restarts: worker first offline (drain), then API; `docker compose down/up` on compose hosts; scripts/dev/stop for native dashboard parity (none — process Ctrl+C; no service manager here).
- Rollback code: restore previous version; schema migrations FORWARD-only — after a rollback, run `alembic downgrade -1` ONLY if the migration exists and is reversible and data loss-free (w/ pg_dump safety), else restore backup.
