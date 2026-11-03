# Jobs & reliability

## State machine

```
queued ──dequeue──▶ running ──▶ succeeded
   ▲                  │  ──▶ failed (terminal: max attempts exhausted / non-retryable / timeout)
   │                  ──▶ deferred (attempt pending; maps back to queued w/ next_attempt_at)
cancelled ◀── (queued | running)  ◀── cancellation request
```

Illegal transitions rejected at domain layer (`InvalidJobTransition`), unit-tested. Terminal states: succeeded, failed, cancelled.

## Guarantees (honest)

- **Delivery:** at-least-once. Workers may crash mid-run; recovery sweep (startup + every 60s) marks heartbeat-stale `running` jobs as interrupted → re-queue with attempt++.
- **Effects:** consumers must be idempotent; the report consumer writes to a UUID artifact path per attempt and only promotes the file (and its sha256 into the job result) after the final write succeeds.
- **No exactly-once claims.**

## Retry policy

- Retryable: infra failures (queue/DB/IO). Consumer returns `RetryLater` with optional delay. Non-retryable codes (validation, permanent internal) short-circuit to failed.
- Backoff: `2^(n-1) * 5s + jitter(0..5s)`, clamped to 60s. Max attempts: 3 default (job param 1..10).
- Timeout: hard `timeout_seconds` per attempt via asyncio wait_for wrapper → `timed_out` error, retryable by default (separate attempt).

## Cancellation

- `cancel` only transitions queued/running. Running consumer checks cancel flag between row batches (cooperative) and finalizes `cancelled` without retry.

## Idempotency (duplicates in, one effect out)

- `Idempotency-Key` on create endpoints. Unique `(workspace_id, key)`. Second identical request (same request hash) during flight → `409` + `Retry-After`; after success → replays stored response verbatim. Same key with different body → `409 idempotency_key_reuse`. Expired keys (config TTL, default 24h) can be reused for a new request only after success records pruned by janitor task later (MVP keeps full history).

## Enqueue assurance (outbox-lite)

Job row + enrollment happen in one transaction; enqueue of the queue message occurs strictly **after** COMMIT via post-commit hook (Procrastinate). Worker crash between enqueue and domain state update is absorbed by recovery sweep. This satisfies Phase 5's queue/DB consistency without a separate outbox table; an explicit outbox is a documented later extension if relational events beyond jobs are needed.

## Failure inspection

- `job_attempts` rows per attempt (started/finished/error_code/detail), surfaced to admins via `GET /jobs/{id}`; queue-side internals stay internal (Procrastinate tables are transport, not API truth).

## Recovery (real ops)

- Worker SIGTERM → stops accepting new leases, running jobs get grace-period to finish or wait_for cancellation point then lose lease → recovery sweep re-runs them.
- Postgres outage makes `/ready` fail and the queue naturally halts; reconnects recover via SQLAlchemy `pool_pre_ping`.

## Cleanup

- `succeeded` job artifacts retained indefinitely MVP; a retention janitor is a documented later extension, not silently assumed.
