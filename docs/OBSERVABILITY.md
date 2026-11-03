# Observability

## Logs

structlog; JSON in prod (`LOG_FORMAT=json`), console-pretty in dev. Every log line includes `request_id` (or `job_id` in worker context), `user_id`/`workspace_id` when known, level, event, timestamp. Redaction processor denies keys: password, token, secret, signature, authorization.

## Request correlation

Middleware generates/propagates `X-Request-ID` (also copied to response); binds structlog contextvar. Worker tasks bind `job_id` the same way, enabling cross-process correlation when the API logged a submit and the worker logs progress.

## Metrics (Prometheus, `/metrics`)

| Metric | Type | Labels |
|---|---|---|
| `bf_http_requests_total` | counter | method, route template, status |
| `bf_http_request_seconds` | histogram | method, route |
| `bf_jobs_submitted_total` | counter | type |
| `bf_jobs_state_total` | counter | type, from, to (transition outcome e.g. retry/failed) |
| `bf_jobs_retry_backoff_seconds` | gauge (last computed) | attempt |
| `bf_webhook_attempts_total` | counter | outcome |
| `bf_rate_limited_total` | counter | route |

Queue depth gauge `bf_queue_pending` (domain queued count) scraped with modest frequency to hold DB cost low.

## Health

- `/health` liveness: process is up (no deps).
- `/ready` readiness: DB `SELECT 1` within tight timeout; failure → 503 with per-dependency detail. Worker offline is surfaced via queue age metric, not readiness (documented).

## SLO definitions (stated, measured in Phase 8)

- Availability of API endpoints (excluding planned worker-lag): 99.5% monthly, measured by orchestration heartbeat.
- p50 ≤ 25ms, p99 ≤ 250ms for `GET /jobs/{id}` at local single-node baseline (to be verified by the load test run recorded in `benchmarks/`).
- Job end-to-end: p95 submit→succeeded ≤ 10s for report.generate at reference size.

## Tracing (later)

OpenTelemetry deferred (documented extension; request/job IDs provide MVP correlation).
