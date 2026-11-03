# Testing strategy

Layers (all runnable natively on this host; no Docker needed):
1. **Unit (domain):** state machine legality, backoff math, retry classification, redaction processor. No IO.
2. **Integration (real Postgres 127.0.0.1:54329 from ADR-003):** migrations from empty DB; repositories; auth flows; tenant isolation matrix; idempotency; job lifecycle incl. retry/timeout/cancel/recovery; webhook signature verification.
3. **API contract:** FastAPI ASGI via httpx with schema-shaped status/auth/auth request validation contract test; OpenAPI generated + structure checks (paths, error envelope).
4. **Failure-recovery:** worker intermission simulation (kill async task mid-run → recovery sweep requeues); DB restart test optional-manual runbook.

Fixtures: session-scoped event loop + Postgres app; per-test database transaction rollback where safe; artifacts dir per test run in `local/tmp-artifacts/`.

Async discipline: pytest-asyncio auto mode; no sleeping-in-tests (polling job state via small helper with deadline).

Honesty rule: integration tests against the live Postgres are never skipped-and-reported-pass — they either run (green/red recorded) or are marked explicit `skip` with reason attached to the run's documentation.

Load testing strategy (Phase 8): script under `scripts/load/` driving submit/get/done mix; outputs `benchmarks/manifest.json` (hardware, run time, version) `benchmarks/run-<timestamp>.json` with p50/p95/p99 for submit and status endpoints, queue drain rate, and error rates. Committed to repo (small files).
