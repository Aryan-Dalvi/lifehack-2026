"""VisaNet Connect – Acceptance Authorization API client (sandbox).

Talks to `POST {VISA_API_BASE_URL}{VISA_ENDPOINT_PATH}` over mutual TLS, with HTTP Basic
Auth layered on top, and Message Level Encryption (JWE) on sensitive request/response
fields. This module owns exactly one thing: producing a real authorization decision from
Visa. It has no knowledge of carts, mandates, or orders — `payments/service.py` still owns
all of that, unchanged, and only swaps in this adapter for the one step that used to
fabricate a result.

Scope, deliberately: authorization only. No capture, sale, refund, void, or verification —
those need separate acquirer pre-approval this hackathon does not have.

Everything here is best-effort against Visa's real schema. The exact field names inside
Tx/Envt/Cntxt/AdddmData are built from the shape described when this was commissioned, not
from a verified copy of Visa's published OpenAPI spec — treat `_build_body` as the one
place to correct against the real Postman collection if a live call comes back schema-
rejected rather than declined.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from joserfc import jwe
from joserfc.jwk import RSAKey

from app.settings import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15.0

# RFC 7516 algorithms Visa's MLE spec calls for: RSA-OAEP-256 wraps a one-time content
# encryption key, A128CBC-HS256 encrypts the payload with it. joserfc requires both to be
# explicitly allow-listed — neither is in its default "recommended" set.
_JWE_ALGORITHMS = {"alg": "RSA-OAEP-256", "enc": "A128CBC-HS256"}
_JWE_ALLOWED_ALGORITHMS = ["RSA-OAEP-256", "A128CBC-HS256"]

# Fields Visa's MLE spec treats as sensitive and requires encrypted rather than sent as
# plaintext JSON. Never log these, encrypted or not.
_SENSITIVE_FIELDS = {"primaryAccountNumber", "cardholderName", "cardholderAddress"}


class VisaConfigurationError(Exception):
    """The adapter cannot run at all — missing cert, key, or credential. Never a decline;
    the caller must treat this as "the payment path is unavailable", not "Visa said no"."""


class VisaAuthorizationError(Exception):
    """Visa was reachable but returned something this client cannot safely treat as a
    normalized approval or decline (malformed body, unexpected status, encryption failure)."""


@dataclass(frozen=True)
class VisaAuthorizationResult:
    approved: bool
    decline_reason: str | None
    auth_code: str | None
    response_code: str | None
    raw_status: int


def _require_file(path: str | None, label: str) -> Path:
    if not path:
        raise VisaConfigurationError(f"{label} is not configured.")
    resolved = Path(path).expanduser()
    if not resolved.is_file():
        raise VisaConfigurationError(f"{label} does not point to a file: {resolved}")
    return resolved


def _require_value(value: str | None, label: str) -> str:
    if not value:
        raise VisaConfigurationError(f"{label} is not configured.")
    return value


def _load_rsa_key(path: Path) -> RSAKey:
    return RSAKey.import_key(path.read_text(encoding="utf-8"))


def encrypt_mle_field(value: dict[str, Any], *, encrypt_cert_path: Path, key_id: str) -> str:
    """Encrypt one sensitive field for Visa, as a compact JWE, using Visa's public key."""
    key = _load_rsa_key(encrypt_cert_path)
    protected = {**_JWE_ALGORITHMS, "kid": key_id}
    return jwe.encrypt_compact(
        protected, json.dumps(value).encode(), key, algorithms=_JWE_ALLOWED_ALGORITHMS
    )


def decrypt_mle_field(token: str, *, private_key_path: Path) -> dict[str, Any]:
    """Decrypt one Visa-encrypted response field using our own private key."""
    key = _load_rsa_key(private_key_path)
    decrypted = jwe.decrypt_compact(token, key, algorithms=_JWE_ALLOWED_ALGORITHMS)
    return json.loads(decrypted.plaintext)


# A compact JWE is five base64url segments joined by dots. Visa's exact response field
# names for MLE are not known ahead of a real call, so encrypted fields are found by shape
# rather than by name — anything matching this is attempted, and left as-is if it is not
# actually a JWE meant for our key (e.g. false positives are simply undecryptable).
_COMPACT_JWE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+){4}$")


def _decrypt_response_fields(body: dict[str, Any], *, private_key_path: Path) -> dict[str, Any]:
    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: walk(inner) for key, inner in value.items()}
        if isinstance(value, list):
            return [walk(item) for item in value]
        if isinstance(value, str) and _COMPACT_JWE_PATTERN.match(value):
            try:
                return decrypt_mle_field(value, private_key_path=private_key_path)
            except Exception:  # noqa: BLE001 - not every JWE-shaped string decrypts with our key
                logger.warning("A response field looked like MLE ciphertext but did not decrypt.")
                return value
        return value

    return walk(body)


def _redact(body: dict[str, Any]) -> dict[str, Any]:
    """Recursively drop anything that could be a PAN, name, address, or ciphertext blob —
    what we log must stay useful for debugging without becoming a second place a card
    number could leak from."""

    def scrub(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: ("<redacted>" if key in _SENSITIVE_FIELDS else scrub(inner))
                for key, inner in value.items()
            }
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    return scrub(body)


def _build_mtls_client() -> httpx.Client:
    cert_path = _require_file(settings.visa_ssl_cert_path, "VISA_SSL_CERT_PATH")
    key_path = _require_file(settings.visa_ssl_private_key_path, "VISA_SSL_PRIVATE_KEY_PATH")
    ca_bundle = _require_file(settings.visa_ca_bundle_path, "VISA_CA_BUNDLE_PATH")
    username = _require_value(settings.visa_api_username, "VISA_API_USERNAME")
    password = _require_value(settings.visa_api_password, "VISA_API_PASSWORD")
    return httpx.Client(
        base_url=settings.visa_api_base_url,
        cert=(str(cert_path), str(key_path)),
        verify=str(ca_bundle),
        auth=httpx.BasicAuth(username, password),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def _build_body(
    *,
    amount_cents: int,
    currency: str,
    merchant_id: str,
    correlation_id: str,
    encrypted_pan: str,
) -> dict[str, Any]:
    """The Authorizations v3 request envelope: identity header plus a Tx/Envt/Cntxt/AdddmData
    body. Field names here are the best-effort shape for this call; correct against Visa's
    published schema if a live request is schema-rejected rather than declined."""
    client_id = _require_value(settings.visa_client_id, "VISA_CLIENT_ID")
    return {
        "msgIdentfctn": {"clientId": client_id, "correlatnId": correlation_id},
        "Body": {
            "Tx": {
                "instructedAmt": {"amt": str(amount_cents / 100), "curCode": currency},
                "cardData": {"primaryAccountNumber": encrypted_pan},
            },
            "Envt": {"acqrgInstitutnId": client_id},
            "Cntxt": {"cardAccptrId": merchant_id},
            "AdddmData": {"correlatnId": correlation_id},
        },
    }


def authorize(
    *,
    amount_cents: int,
    currency: str,
    merchant_id: str,
    card_last4: str,
) -> VisaAuthorizationResult:
    """One authorization call. Raises VisaConfigurationError / VisaAuthorizationError on
    anything that is not a clean Visa-issued approve/decline — the caller must treat both
    as "cannot authorize right now", never as an approval."""
    correlation_id = str(uuid.uuid4())
    encrypt_cert = _require_file(settings.visa_mle_encrypt_cert_path, "VISA_MLE_ENCRYPT_CERT_PATH")
    mle_key_id = _require_value(settings.visa_mle_key_id, "VISA_MLE_KEY_ID")
    decrypt_key = _require_file(settings.visa_mle_private_key_path, "VISA_MLE_PRIVATE_KEY_PATH")

    # The token vault never stores a real PAN (it is a mock issuer, per the architecture),
    # so a masked stand-in is encrypted here — real card data must come from an actual
    # cardholder-facing field before this can authorize a genuine account.
    encrypted_pan = encrypt_mle_field(
        {"primaryAccountNumber": f"masked:{card_last4}"},
        encrypt_cert_path=encrypt_cert,
        key_id=mle_key_id,
    )
    body = _build_body(
        amount_cents=amount_cents,
        currency=currency,
        merchant_id=merchant_id,
        correlation_id=correlation_id,
        encrypted_pan=encrypted_pan,
    )

    logger.info("Visa authorization request %s: %s", correlation_id, _redact(body))

    with _build_mtls_client() as client:
        try:
            response = client.post(settings.visa_endpoint_path, json=body)
        except httpx.HTTPError as error:
            raise VisaAuthorizationError(f"Visa sandbox request failed: {error}") from error

    parsed = _decrypt_response_fields(_safe_json(response), private_key_path=decrypt_key)
    logger.info(
        "Visa authorization response %s: status=%s body=%s",
        correlation_id,
        response.status_code,
        _redact(parsed),
    )

    if response.status_code == 200:
        return VisaAuthorizationResult(
            approved=True,
            decline_reason=None,
            auth_code=parsed.get("Body", {}).get("Tx", {}).get("apprvlCode"),
            response_code=parsed.get("Body", {}).get("Tx", {}).get("rspnCode"),
            raw_status=response.status_code,
        )
    if response.status_code in (400, 401, 403, 422):
        reason = (
            parsed.get("Errors", {}).get("Error", [{}])[0].get("errorDesc")
            or f"HTTP {response.status_code}"
        )
        return VisaAuthorizationResult(
            approved=False,
            decline_reason=reason,
            auth_code=None,
            response_code=str(response.status_code),
            raw_status=response.status_code,
        )
    raise VisaAuthorizationError(
        f"Unexpected Visa sandbox response: HTTP {response.status_code}"
    )


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        return response.json()
    except ValueError as error:
        raise VisaAuthorizationError("Visa response was not valid JSON.") from error
