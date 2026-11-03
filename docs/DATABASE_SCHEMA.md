# Database schema

PostgreSQL 17. UUID PKs (`uuid_v4`); `timestamptz` everywhere; FKs explicit; UTC (`now()` normalized).

Entity matrix (MVP scope only — rule 7: no speculative tables; documented why per row):

| Table | Exists because | Constraints / notes |
|---|---|---|
| `users` | identity | unique `email` (citext); `password_hash` nullable null for API-key-only accounts; `is_active` |
| `workspaces` | tenancy unit | `name` nonempty; audit-following `created_by` FK users |
| `memberships` | roles | PK (`workspace_id`,`user_id`); role enum `owner/admin/member`; unique user-per-ws |
| `sessions` | password login tokens | `token_hash` unique sha256; `expires_at`; `revoked_at` nullable; no plaintext |
| `api_keys` | programmatic auth | unique `token_hash`; `workspace_id` FK; `created_by`; `revoked_at`; expiry via `expires_at` |
| `jobs` | durable job record | `type`; `status` enum queued/running/succeeded/failed/cancelled; `params`/`result`/`error` jsonb; `max_attempts`; `attempts`; `timeout_seconds`; `created_by`; `idempotency_key_id` FK unique-per-ws; `heartbeat_at`/`next_attempt_at`/`terminal_at` |
| `job_attempts` | failure forensics | per attempt rows: n, started_at, finished_at, error_code, error_detail truncated jsonb |
| `reports` | reference workload data | job_id unique FK; params; artifact_path (relative to data dir, uuid-named); row_count; sha256; format enum |
| `idempotency_keys` | duplicate-write guard | PK id; unique (`workspace_id`, `header_key`); `request_hash`; `response_status`; `response_body`; `state` in_progress/completed |
| `audit_events` | audit trail | FK workspace, actor_user, job FK nullable; `action`, `resource_type`, `resource_id`, `detail` jsonb; indexed (workspace_id, created_at desc) |
| `webhook_endpoints` | signed delivery | url validated; secret (random 32B, shown at creation), events[], active |
| `webhook_deliveries` | history | FK endpoint+event id; attempt n; signature; response_code, error, `succeeded_at`, `failed_at`; state enum pending/delivering/delivered/failed |

Deletion behaviour: users soft-deactivate; sessions/api_keys revoked flag; workspaces lack cascade deletes in MVP (no cascade rules) — cross-bound data deletion is a documented non-goal for iteration 1.

Sensitive fields & encryption at rest decision: token/secret `hashes` only (sha256+pepper stored); webhook signing secret stored plaintext server-side (needed to sign) with treat-as-confidential note; file artifacts sha256 recorded for integrity.

Indexes: FKs indexed; `jobs (workspace_id, created_at desc)`, `jobs (workspace_id, status)`, `sessions/a p_i keys (token_hash)`; `audit (workspace_id, created_at desc)`; `webhook_deliveries (state) for due deliveries (partial index where state in pending/delivering`).

Migrations: Alembic at `migrations/versions`; forward-only policy (each new migration; no in-place edits to applied migrations); invasive command documented in OPERATIONS_RUNBOOK.
