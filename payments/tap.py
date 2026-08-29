from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.db import transaction
from app.errors import api_error
from app.settings import settings

_INPUT_RE = re.compile(
    r'^sig1=\("@method" "@authority" "@path" "content-digest"\)'
    r';created=(?P<created>\d+);expires=(?P<expires>\d+);keyid="(?P<keyid>[^"]+)"'
    r';alg="ed25519";nonce="(?P<nonce>[^"]+)";tag="(?P<tag>[^"]+)"$'
)
_SIGNATURE_RE = re.compile(r"^sig1=:(?P<signature>[A-Za-z0-9+/=]+):$")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def content_digest(body: bytes) -> str:
    digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
    return f"sha-256=:{digest}:"


def _load_or_create_private_key(path: Path | None = None) -> Ed25519PrivateKey:
    key_path = path or settings.signing_key_path
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return serialization.load_pem_private_key(key_path.read_bytes(), password=None)

    key = Ed25519PrivateKey.generate()
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    return key


def public_key() -> Ed25519PublicKey:
    return _load_or_create_private_key().public_key()


def sign_record(value: dict[str, Any]) -> str:
    signature = _load_or_create_private_key().sign(canonical_json(value))
    return base64.urlsafe_b64encode(signature).decode().rstrip("=")


def verify_record(value: dict[str, Any], signature: str) -> bool:
    try:
        padded = signature + "=" * (-len(signature) % 4)
        public_key().verify(base64.urlsafe_b64decode(padded), canonical_json(value))
    except (InvalidSignature, ValueError, TypeError, binascii.Error):
        return False
    return True


def _signature_base(
    method: str,
    authority: str,
    path: str,
    digest: str,
    signature_params: str,
) -> bytes:
    lines = [
        f'"@method": {method.lower()}',
        f'"@authority": {authority}',
        f'"@path": {path}',
        f'"content-digest": {digest}',
        f'"@signature-params": {signature_params}',
    ]
    return "\n".join(lines).encode()


def sign_tap_request(
    *,
    method: str,
    path: str,
    body: bytes,
    tag: str,
    authority: str = "localhost:8000",
    ttl_seconds: int = 60,
) -> dict[str, str]:
    if tag not in {"agent-browser-auth", "agent-payer-auth"}:
        raise ValueError("Unsupported TAP intent tag")
    created = int(time.time())
    expires = created + ttl_seconds
    nonce = secrets.token_urlsafe(18)
    params = (
        '("@method" "@authority" "@path" "content-digest")'
        f';created={created};expires={expires};keyid="{settings.agent_kid}"'
        f';alg="ed25519";nonce="{nonce}";tag="{tag}"'
    )
    digest = content_digest(body)
    signature = _load_or_create_private_key().sign(
        _signature_base(method, authority, path, digest, params)
    )
    return {
        "Content-Digest": digest,
        "Signature-Input": f"sig1={params}",
        "Signature": f"sig1=:{base64.b64encode(signature).decode()}:",
    }


def verify_tap_request(
    *,
    method: str,
    authority: str,
    path: str,
    body: bytes,
    headers: dict[str, str],
    expected_tag: str,
    record_nonce: bool = True,
) -> dict[str, Any]:
    signature_input = headers.get("signature-input") or headers.get("Signature-Input")
    signature_header = headers.get("signature") or headers.get("Signature")
    supplied_digest = headers.get("content-digest") or headers.get("Content-Digest")
    if not signature_input or not signature_header or not supplied_digest:
        raise api_error(401, "SIGNATURE_INVALID", "A signed agent request is required.")

    input_match = _INPUT_RE.match(signature_input)
    signature_match = _SIGNATURE_RE.match(signature_header)
    if not input_match or not signature_match:
        raise api_error(401, "SIGNATURE_INVALID", "The TAP signature fields are malformed.")

    values = input_match.groupdict()
    now = int(time.time())
    if int(values["created"]) > now + 5 or int(values["expires"]) < now:
        raise api_error(401, "SIGNATURE_INVALID", "The signed request has expired.")
    if values["keyid"] != settings.agent_kid or values["tag"] != expected_tag:
        raise api_error(401, "SIGNATURE_INVALID", "The agent key or intent tag is not allowed.")
    expected_digest = content_digest(body)
    if not secrets.compare_digest(expected_digest, supplied_digest):
        raise api_error(401, "SIGNATURE_INVALID", "The request body digest does not match.")

    params = signature_input.removeprefix("sig1=")
    try:
        public_key().verify(
            base64.b64decode(signature_match.group("signature")),
            _signature_base(method, authority, path, supplied_digest, params),
        )
    except Exception as exc:
        raise api_error(401, "SIGNATURE_INVALID", "The agent signature could not be verified.") from exc

    if record_nonce:
        try:
            with transaction() as connection:
                connection.execute("DELETE FROM tap_nonces WHERE expires_at < ?", (now,))
                connection.execute(
                    "INSERT INTO tap_nonces(nonce, expires_at) VALUES (?, ?)",
                    (values["nonce"], int(values["expires"])),
                )
        except sqlite3.IntegrityError as exc:
            raise api_error(401, "NONCE_REPLAY", "This signed request was already used.") from exc

    return {
        "verified": True,
        "keyid": values["keyid"],
        "tag": values["tag"],
        "nonce": values["nonce"],
        "created": int(values["created"]),
        "expires": int(values["expires"]),
    }
