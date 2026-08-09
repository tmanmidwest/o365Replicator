"""Password/secret hashing and credential token generation (stdlib only).

Uses PBKDF2-HMAC-SHA256 so there are no native build dependencies. Secrets are
never stored in plaintext — only salted hashes — and raw values are shown to the
user exactly once at creation time.
"""

import base64
import hashlib
import hmac
import secrets

_ITERATIONS = 200_000
_ALGO = "pbkdf2_sha256"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def hash_secret(raw: str) -> str:
    """Return a self-describing PBKDF2 hash string: algo$iterations$salt$digest."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt, _ITERATIONS)
    return f"{_ALGO}${_ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_secret(raw: str, stored: str) -> bool:
    """Constant-time verify a raw value against a stored PBKDF2 hash."""
    try:
        algo, iters, salt_b64, digest_b64 = stored.split("$")
        if algo != _ALGO:
            return False
        salt = _b64d(salt_b64)
        expected = _b64d(digest_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", raw.encode("utf-8"), salt, int(iters))
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError):
        return False


# --- Opaque credential tokens ---------------------------------------------------

def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def new_oauth_access_token() -> str:
    return secrets.token_urlsafe(32)


def new_client_id() -> str:
    return "o365c_" + secrets.token_hex(12)


def new_client_secret() -> str:
    return "o365s_" + secrets.token_urlsafe(32)


def new_api_key() -> tuple[str, str]:
    """Return (full_key, display_prefix). Only the hash of full_key is persisted."""
    body = secrets.token_urlsafe(32)
    full = f"o365k_{body}"
    return full, full[:14]  # e.g. "o365k_AbC12345" shown for identification


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
