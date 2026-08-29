"""Identity and tenant isolation.

Three separate credentials, deliberately not interchangeable:

* **Merchant API key** (`X-Merchant-Key`) — issued once at onboarding, proves control of one
  merchant. Required for every read or write of that merchant's private configuration and
  catalog. A key for merchant A is a 403 on merchant B, never a 404-shaped guess.
* **Consumer token** (`Authorization: Bearer …`) — issued by register/login, proves who the
  shopper is. Optional: browsing works without one.
* **Session token** (`X-Session-Token`) — minted per shopping session, proves you are the
  client that opened it. Required by every session-scoped endpoint, so one shopper cannot
  read or drive another shopper's session even while both are anonymous.

Secrets are never stored in the clear. Tokens are random 256-bit values kept as SHA-256
digests; passwords use scrypt with a per-row salt. Comparisons are constant-time.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from app.db import connect, utc_now
from app.errors import api_error
from app.ids import new_id

CONSUMER_TOKEN_TTL_DAYS = 7
SESSION_TTL_HOURS = 12

# Credential-guessing throttle. In-process and therefore per-worker: enough to stop a script
# hammering one account, not a substitute for a shared limiter behind a real deployment.
ATTEMPT_WINDOW_SECONDS = 300
# Guessing one account's password is the thing to stop hard. Signing several people up from
# one network — a shared office, a demo booth, a conference NAT — is ordinary, so that limit
# is looser: it exists to blunt scripted enumeration, not to turn a crowd away.
PASSWORD_ATTEMPT_LIMIT = 8
SIGNUP_ATTEMPT_LIMIT = 30
_attempts: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(bucket: str, limit: int = PASSWORD_ATTEMPT_LIMIT) -> None:
    """Allow a burst, then refuse. Raises 429 once the window is full."""
    now = time.monotonic()
    seen = _attempts[bucket]
    while seen and now - seen[0] > ATTEMPT_WINDOW_SECONDS:
        seen.popleft()
    if len(seen) >= limit:
        raise api_error(
            429, "TOO_MANY_ATTEMPTS", "Too many attempts. Wait a few minutes and try again."
        )
    seen.append(now)


def clear_rate_limits() -> None:
    """Drop every bucket. For tests, which share one process and would otherwise accumulate."""
    _attempts.clear()


def reset_rate_limit(bucket: str) -> None:
    """Clear a bucket after a success, so ordinary use never accumulates toward a lockout."""
    _attempts.pop(bucket, None)


# A password does not have to be strong here, but it must not be one of the handful an
# attacker tries first. Length is checked by the request model.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwertyuiop", "qwerty123", "iloveyou", "letmein1", "welcome1", "admin123",
    "abc12345", "passw0rd", "football", "baseball", "sunshine", "princess",
}


def assert_usable_password(password: str) -> None:
    if password.lower() in COMMON_PASSWORDS:
        raise api_error(400, "WEAK_PASSWORD", "That password is too common. Choose another.")
    if len(set(password)) < 4:
        raise api_error(400, "WEAK_PASSWORD", "That password is too repetitive. Choose another.")

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


# --------------------------------------------------------------------------- secrets


def new_secret(prefix: str) -> str:
    """A fresh bearer secret. Returned to the caller once; only its digest is stored."""
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, expected_hex = stored.split("$", 2)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt_hex),
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return secrets.compare_digest(derived.hex(), expected_hex)


def _bearer(header_value: str | None) -> str | None:
    if not header_value:
        return None
    parts = header_value.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return header_value.strip()


# --------------------------------------------------------------------------- merchant


def assert_merchant(merchant_id: str, api_key: str | None) -> None:
    """Authorise a caller to act as `merchant_id`, or raise.

    A merchant with no key on record is treated as locked, not open: an unkeyed row is a
    seeding or migration gap, and failing closed is the only safe reading of it.
    """
    if not api_key:
        raise api_error(
            401, "MERCHANT_AUTH_REQUIRED", "Provide your merchant API key in X-Merchant-Key."
        )
    with connect() as connection:
        row = connection.execute(
            "SELECT api_key_hash FROM merchants WHERE merchant_id=?", (merchant_id,)
        ).fetchone()
    if not row:
        raise api_error(404, "NO_MERCHANT", "The merchant was not found.")
    stored = row["api_key_hash"]
    if not stored or not secrets.compare_digest(token_digest(api_key), stored):
        raise api_error(
            403, "MERCHANT_FORBIDDEN", "That API key does not grant access to this merchant."
        )


def require_merchant(api_key: str | None) -> str:
    """Resolve which merchant an API key belongs to, or raise.

    `assert_merchant` answers "may this key act as *that* merchant?", which needs the caller
    to already know who they are. A merchant signing in knows only their key, so this answers
    the other question: the key alone identifies the store. Without it the admin page has no
    way to tell one merchant from another, which is why it used to hard-code a single one.

    The digest is unique in practice, but a duplicate would make identity ambiguous, so a
    non-unique key resolves to nobody rather than to an arbitrary row.
    """
    if not api_key:
        raise api_error(
            401, "MERCHANT_AUTH_REQUIRED", "Provide your merchant API key in X-Merchant-Key."
        )
    with connect() as connection:
        rows = connection.execute(
            "SELECT merchant_id FROM merchants WHERE api_key_hash=?", (token_digest(api_key),)
        ).fetchall()
    if len(rows) != 1:
        raise api_error(401, "MERCHANT_AUTH_REQUIRED", "That merchant API key is not valid.")
    return rows[0]["merchant_id"]


def is_merchant(merchant_id: str, api_key: str | None) -> bool:
    """Soft variant of assert_merchant: answers the question instead of raising.

    Used where a route serves both the public and the merchant themselves — a storefront read
    shows published products to anyone, and the merchant's own unpublished rows to them.
    """
    if not api_key:
        return False
    with connect() as connection:
        row = connection.execute(
            "SELECT api_key_hash FROM merchants WHERE merchant_id=?", (merchant_id,)
        ).fetchone()
    if not row or not row["api_key_hash"]:
        return False
    return secrets.compare_digest(token_digest(api_key), row["api_key_hash"])


# --------------------------------------------------------------------------- consumer


def consumer_from_token(authorization: str | None) -> str | None:
    """Resolve a consumer token to a consumer_id, or None when browsing anonymously.

    An unreadable or expired token is anonymous rather than an error, so a stale token in a
    browser degrades to anonymous browsing instead of locking the shopper out of the store.
    """
    token = _bearer(authorization)
    if not token:
        return None
    with connect() as connection:
        row = connection.execute(
            "SELECT consumer_id, expires_at FROM consumer_tokens WHERE token_hash=?",
            (token_digest(token),),
        ).fetchone()
    if not row:
        return None
    if datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC):
        return None
    return row["consumer_id"]


def require_consumer(authorization: str | None) -> str:
    consumer_id = consumer_from_token(authorization)
    if not consumer_id:
        raise api_error(401, "LOGIN_REQUIRED", "Sign in to continue.")
    return consumer_id


def assert_consumer(consumer_id: str, authorization: str | None) -> None:
    """Authorise a caller to act as `consumer_id`, or raise."""
    actual = require_consumer(authorization)
    if not secrets.compare_digest(actual, consumer_id):
        raise api_error(403, "CONSUMER_FORBIDDEN", "That account is not yours.")


def revoke_consumer_token(connection: sqlite3.Connection, authorization: str | None) -> None:
    """Revoke only the token presented — signing out here should not sign out elsewhere."""
    token = _bearer(authorization)
    if token:
        connection.execute(
            "DELETE FROM consumer_tokens WHERE token_hash=?", (token_digest(token),)
        )


def issue_consumer_token(connection: sqlite3.Connection, consumer_id: str) -> str:
    token = new_secret("ct")
    expires = (datetime.now(UTC) + timedelta(days=CONSUMER_TOKEN_TTL_DAYS)).isoformat()
    connection.execute(
        "INSERT INTO consumer_tokens(token_hash,consumer_id,created_at,expires_at) "
        "VALUES (?,?,?,?)",
        (token_digest(token), consumer_id, utc_now(), expires),
    )
    return token


def anonymous_consumer_id() -> str:
    """A per-session identity for a shopper who has not signed in.

    Anonymous is not shared: every anonymous session gets its own id, so two anonymous
    shoppers are as isolated from each other as two signed-in ones.
    """
    return new_id("anon")


# --------------------------------------------------------------------------- session


def assert_session(session_id: str, session_token: str | None) -> sqlite3.Row:
    """Authorise a caller to drive `session_id`, returning the session row."""
    if not session_token:
        raise api_error(
            401, "SESSION_TOKEN_REQUIRED", "Provide the session token in X-Session-Token."
        )
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
    if not row:
        raise api_error(404, "NO_SESSION", "The shopping session was not found.")
    stored = row["session_token_hash"]
    if not stored or not secrets.compare_digest(token_digest(session_token), stored):
        raise api_error(403, "SESSION_FORBIDDEN", "That token does not open this session.")
    # sqlite3.Row membership tests values, not column names, so ask for the names directly.
    columns = set(row.keys())
    expires_at = row["expires_at"] if "expires_at" in columns else None
    if expires_at and datetime.fromisoformat(expires_at) <= datetime.now(UTC):
        raise api_error(401, "SESSION_EXPIRED", "This shopping session has expired.")
    return row


def session_expiry() -> str:
    return (datetime.now(UTC) + timedelta(hours=SESSION_TTL_HOURS)).isoformat()
