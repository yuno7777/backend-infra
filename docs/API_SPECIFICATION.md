# API specification (v1 draft)

Base: `/api/v1`. Content type JSON (UTF-8). Auth: `Authorization: Bearer <token>` (session or API key).

## Conventions

- **Versioning:** URL path major (`/v1`); additive changes only within v1; breaking → `/v2` kept alongside.
- **Pagination:** `?limit<=100 default 25`, `cursor` (opaque base64); responses `data[]`, `page{next_cursor, has_more}`.
- **Errors:** consistent envelope; `error{code, message, details[]}`, plus `request_id` mapped from `X-Request-ID`. Machine codes: `validation_error`, `unauthenticated`, `forbidden`, `not_found`, `conflict`, `idempotency_key_reuse`, `rate_limited`, `invalid_state`, `internal_error`. `429` includes `Retry-After`; `409` on idempotency conflict also carries `Retry-After`.
- **Idempotency:** `Idempotency-Key` header optional on create endpoints; semantics in `JOBS_AND_RELIABILITY.md`.
- **Auth model:** sessions from `POST /auth/login`; workspace API keys `bk_<wsid>_<random>` (shown once; SHA-256 hash stored). Token row stores SHA-256(token+dpepper constant in settings `token_hash_pepper`).
- **Roles:** `owner`(1+ per ws) > `admin` > `member`. Global `is_org_admin` NOT used.

## Endpoints v1

Auth (no auth required except logout/me):
- `POST /auth/register` `{email, password} → 201 {id, email}` (lowercased email, unique; password ≥10 chars)
- `POST /auth/login` `{email, password} → {token, workspace_ids?}` – create personal workspace if none
- `POST /auth/logout` (revoke current session) → 204
- `GET /auth/me → {id, email, workspaces[{id,name,role}]}`

Workspaces & membership:
- `POST /workspaces` `{name} → 201 {id, name, role:"owner"}` (audit `workspace.create`)
- `GET /workspaces` `→ {data:[...]}`
- `GET /workspaces/{id}` (member)
- `POST /workspaces/{id}/members` admin+ `{user_id, role}` (audit) → 201
- `DELETE /workspaces/{id}/members/{user_id}` owner-only (may not demote last owner) → 204
- `GET /workspaces/{id}/api-keys` admin+; `POST .../api-keys` `{name} → 201 {token_once}`; `DELETE .../api-keys/{kid}` admin+ → 204 (soft revoke)

Jobs + reference workload (report generation):
- `POST /jobs` `{type:"report.generate", timeout_s?:n<=3600 default 300, max_attempts?> n in [1..10] default 3, params:{format:"json"|"csv", row_count: 1..100000, seed?: int}, workspace_id? }` (member role; auth dependency resolves workspace context; requires `Idempotency-Key`) → `202 {id, status:"queued", ...}` queue wait + artifact paths only for admin+
- `GET /jobs?type=&status=&limit&cursor` list own workspace jobs
- `GET /jobs/{id}` incl. `result{...}` when succeeded; `attempts[]` for admin+ with error_code per attempt
- `POST /jobs/{id}/cancel` member (owner/admin may cancel running; member may cancel only `queued`) → new state; 409 `invalid_state` when terminal/running-for-member
- `GET /reports/{id}` metadata; `GET /reports/{id}/download` streams artifact with content-disposition & sha256 headers

Audit (owner/admin; personal scope for own user events):
- `GET /audit-events?action=&limit&cursor`

Webhooks (Phase 6; admin+):
- CRUD `POST/GET/DELETE /workspaces/{id}/webhook-endpoints`; `GET /webhook-deliveries?job_id=` history incl. attempts & last response.

Ops:
- `GET /health` liveness (no deps); `GET /ready` readiness checks each dep; `GET /metrics` Prometheus text.

Security notes: register rate-limited by email+IP; login variance by hash-failure constant time; keys never returned again; audit covers register/login-failure/key-create/key-revoke/job-create/job-cancel, webhook changes.

Open questions exported into ADR when resolved: none blocking build.
