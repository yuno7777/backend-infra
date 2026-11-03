# Security

## Threat model (single-node MVP)

Assets: credentials/tokens, cross-tenant data, job results. Adversaries: internet clients (if exposed), malicious tenant users, job/webhook payload injection. Out of scope: hostile kernel/host, physical access.

## Identity & tokens

- Passwords hashed with argon2id (pwdlib); registration/login rate-limited; login failures never disclose whether email exists (single generic message).
- Sessions: opaque 256-bit tokens returned once; DB stores SHA-256(token + server-side pepper) with expiry; logout revokes. No JWT in MVP (revocation + simplicity; revisit for service-to-service scale).
- API keys: `bk_...` random token; plaintext shown exactly once at creation; DB stores SHA-256(+pepper); per-workspace scoping; revocation is soft; `last_used_at` tracked.
- Both token types map to the same auth dependency carrying `(user, workspace, role)`.

## Authorization & tenant isolation

- All tenant data carries `workspace_id`. Repositories always filter by it (structural isolation). Ownership preloads return HTTP 404 for foreign resources (no existence oracle).
- Role precedence: owner > admin > member; membership required for every workspace-scoped route; only owner manages owners; admin manages members/keys/webhooks.
- Authorization enforced server-side (dependencies + service checks) — never client-hidden-only.

## Transport & inputs

- Request size cap middleware (default 1MB); JSON-strict parsing; Pydantic validation; path traversal protection for artifact download (basename check within data dir).
- Local dev deviates from prod only in TLS termination (localhost); prod deployment doc mandates TLS at reverse proxy.

## Secrets & logging

- `.env` gitignored; `.env.example` contains only placeholders. No credentials in logs; structlog redacts token/password/secret fields via processor allowlist-denylist; audit content keyed by IDs, not raw payloads.
- Webhook secrets: random 32-byte, returned once; stored server-side (needed to sign) — documented as sensitive-at-rest; rotation = delete+create.

## Audit trail

`audit_events` records: registration, login (success/failure), logout, workspace create, membership grant/remove, api-key create/revoke, job submit/cancel, webhook create/rotate/delete. Actor, workspace, resource ids, action, detail JSON, timestamp. Readable by workspace admins; personal audit filter for own events.
