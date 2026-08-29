"""The VisaNet Connect adapter: MLE round-trips correctly, and a broken/unreachable
sandbox can never be mistaken for an approval — no test here talks to the real sandbox.
"""

from __future__ import annotations

import dataclasses
import json

import httpx
import pytest
from joserfc.jwk import RSAKey

from payments import visa_client


def _write_rsa_keypair(tmp_path):
    """A throwaway RSA keypair for tests — never the real sandbox credential."""
    key = RSAKey.generate_key(2048, parameters={"kid": "test-kid"})
    private_pem = tmp_path / "private.pem"
    public_pem = tmp_path / "public.pem"
    private_pem.write_text(key.as_pem(private=True).decode())
    public_pem.write_text(key.as_pem(private=False).decode())
    return private_pem, public_pem


def _configure(monkeypatch, tmp_path, private_pem, public_pem, **overrides) -> None:
    """`Settings` is a frozen dataclass, so it is swapped for a `dataclasses.replace` copy
    rather than mutated field-by-field — the module holds its own `settings` reference."""
    cert_pem = tmp_path / "cert.pem"
    ca_pem = tmp_path / "ca.pem"
    cert_pem.write_text("placeholder — only the path is checked before the transport is swapped")
    ca_pem.write_text("placeholder")
    defaults = {
        "visa_ssl_cert_path": str(cert_pem),
        "visa_ssl_private_key_path": str(private_pem),
        "visa_ca_bundle_path": str(ca_pem),
        "visa_api_username": "user",
        "visa_api_password": "pass",
        "visa_mle_key_id": "test-kid",
        "visa_mle_encrypt_cert_path": str(public_pem),
        "visa_mle_private_key_path": str(private_pem),
        "visa_client_id": "1VISAGCT000001",
    }
    monkeypatch.setattr(
        visa_client, "settings", dataclasses.replace(visa_client.settings, **{**defaults, **overrides})
    )


def test_mle_field_round_trips_through_encrypt_and_decrypt(tmp_path):
    private_pem, public_pem = _write_rsa_keypair(tmp_path)
    payload = {"primaryAccountNumber": "masked:4821"}

    token = visa_client.encrypt_mle_field(payload, encrypt_cert_path=public_pem, key_id="test-kid")
    # A compact JWE: five dot-separated segments, and definitely not the plaintext PAN.
    assert token.count(".") == 4
    assert "4821" not in token

    decrypted = visa_client.decrypt_mle_field(token, private_key_path=private_pem)
    assert decrypted == payload


def test_response_fields_are_decrypted_by_shape_not_by_name(tmp_path):
    """Visa's exact encrypted response field name is not known ahead of a real call, so
    decryption has to find ciphertext by looking like a JWE, not by a fixed key name."""
    private_pem, public_pem = _write_rsa_keypair(tmp_path)
    token = visa_client.encrypt_mle_field(
        {"secret": "value"}, encrypt_cert_path=public_pem, key_id="test-kid"
    )
    body = {"Body": {"Tx": {"somethingVisaNamedThis": token, "rspnCode": "00"}}}

    decrypted = visa_client._decrypt_response_fields(body, private_key_path=private_pem)
    assert decrypted["Body"]["Tx"]["somethingVisaNamedThis"] == {"secret": "value"}
    assert decrypted["Body"]["Tx"]["rspnCode"] == "00"  # untouched, not JWE-shaped


def test_a_string_that_merely_looks_like_a_jwe_is_left_alone(tmp_path):
    private_pem, _public_pem = _write_rsa_keypair(tmp_path)
    fake = "a.b.c.d.e"  # five segments, but not real ciphertext
    result = visa_client._decrypt_response_fields({"field": fake}, private_key_path=private_pem)
    assert result["field"] == fake  # decryption failed, original value kept, no crash


def test_redact_strips_sensitive_fields_but_keeps_everything_else():
    body = {
        "Body": {
            "Tx": {
                "cardData": {"primaryAccountNumber": "should-not-appear", "expiry": "1230"},
                "rspnCode": "00",
            }
        }
    }
    redacted = visa_client._redact(body)
    assert redacted["Body"]["Tx"]["cardData"]["primaryAccountNumber"] == "<redacted>"
    assert redacted["Body"]["Tx"]["cardData"]["expiry"] == "1230"
    assert redacted["Body"]["Tx"]["rspnCode"] == "00"


def test_missing_configuration_raises_configuration_error_not_a_decline(tmp_path, monkeypatch):
    """A misconfigured adapter is an operational fault. It must not present as Visa having
    declined the charge — the caller needs to be able to tell those apart."""
    private_pem, public_pem = _write_rsa_keypair(tmp_path)
    _configure(monkeypatch, tmp_path, private_pem, public_pem, visa_ssl_cert_path=None)
    with pytest.raises(visa_client.VisaConfigurationError):
        visa_client.authorize(
            amount_cents=1000, currency="SGD", merchant_id="m_mysa", card_last4="4821"
        )


def test_approved_response_is_parsed(tmp_path, monkeypatch):
    private_pem, public_pem = _write_rsa_keypair(tmp_path)
    _configure(monkeypatch, tmp_path, private_pem, public_pem)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["msgIdentfctn"]["clientId"] == "1VISAGCT000001"
        assert body["Body"]["Tx"]["instructedAmt"]["curCode"] == "SGD"
        return httpx.Response(
            200, json={"Body": {"Tx": {"apprvlCode": "AB1234", "rspnCode": "00"}}}
        )

    monkeypatch.setattr(
        visa_client,
        "_build_mtls_client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://sandbox.api.visa.com"
        ),
    )

    result = visa_client.authorize(
        amount_cents=3400, currency="SGD", merchant_id="m_mysa", card_last4="4821"
    )
    assert result.approved is True
    assert result.auth_code == "AB1234"


def test_declined_response_never_reports_approved(tmp_path, monkeypatch):
    private_pem, public_pem = _write_rsa_keypair(tmp_path)
    _configure(monkeypatch, tmp_path, private_pem, public_pem)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401, json={"Errors": {"Error": [{"errorDesc": "Card declined"}]}}
        )

    monkeypatch.setattr(
        visa_client,
        "_build_mtls_client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://sandbox.api.visa.com"
        ),
    )

    result = visa_client.authorize(
        amount_cents=3400, currency="SGD", merchant_id="m_mysa", card_last4="4821"
    )
    assert result.approved is False
    assert result.decline_reason == "Card declined"


def test_unexpected_status_raises_rather_than_approves(tmp_path, monkeypatch):
    private_pem, public_pem = _write_rsa_keypair(tmp_path)
    _configure(monkeypatch, tmp_path, private_pem, public_pem)

    monkeypatch.setattr(
        visa_client,
        "_build_mtls_client",
        lambda: httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(500)),
            base_url="https://sandbox.api.visa.com",
        ),
    )

    with pytest.raises(visa_client.VisaAuthorizationError):
        visa_client.authorize(
            amount_cents=3400, currency="SGD", merchant_id="m_mysa", card_last4="4821"
        )
