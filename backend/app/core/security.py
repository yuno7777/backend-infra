from __future__ import annotations

import hashlib
import hmac
import secrets

from pwdlib import PasswordHash

_password_hasher = PasswordHash.recommended()  # argon2id


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        # Constant-ish path for missing hashes: still burn a hash check on a dummy value.
        _password_hasher.verify(password, _password_hasher.hash("dummy-password"))
        return False
    return _password_hasher.verify(password, password_hash)


def new_session_token() -> str:
    """Opaque bearer token for password sessions (returned once)."""
    return secrets.token_hex(32)


def new_api_key_token() -> str:
    """API key token with a recognizable prefix (returned once)."""
    return f"bk_{secrets.token_hex(20)}"


def hash_token(token: str, pepper: str) -> str:
    """Peppered SHA-256 for at-rest storage of bearer tokens and API keys.

    The pepper lives in server configuration only; a leaked database alone
    cannot be replayed against the API.
    """
    return hmac.new(pepper.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def new_webhook_secret() -> str:
    return secrets.token_hex(32)


def new_request_hash() -> str:
    return secrets.token_hex(16)
