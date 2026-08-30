from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_env_file(path: Path = ROOT / ".env") -> None:
    """Load .env into os.environ. Real environment variables always win.

    Settings below is a dataclass, so its field defaults are read once when the class
    body executes on import — this has to run before that, not lazily.
    """
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:  # keep the app runnable on a venv without python-dotenv
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            os.environ.setdefault(key, value.strip().strip("\"'"))
    else:
        load_dotenv(path, override=False)


_load_env_file()


@dataclass(frozen=True)
class Settings:
    database_path: Path = Path(os.getenv("DATABASE_PATH", ROOT / "var" / "sway.db"))
    issuer_database_path: Path = Path(
        os.getenv("ISSUER_DATABASE_PATH", ROOT / "var" / "issuer.db")
    )
    signing_key_path: Path = Path(
        os.getenv("AGENT_PRIVATE_KEY_PATH", ROOT / "var" / "agent-ed25519.pem")
    )
    agent_kid: str = os.getenv("AGENT_KID", "sway-demo-agent-1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    demo_mode: bool = os.getenv("DEMO_MODE", "1") != "0"
    signature_enforce: bool = os.getenv("SIGNATURE_ENFORCE", "enforce") == "enforce"
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    # Prefix the storefront resolves catalog image URLs against. The default matches the
    # web app's own API base, so an <img> served from the site reaches the API through the
    # same proxy every other call already uses.
    catalog_image_base_url: str = os.getenv("CATALOG_IMAGE_BASE_URL", "/api")
    web_base_url: str = os.getenv("WEB_BASE_URL", "http://localhost:5173")
    merchant_hard_ceiling_cents: int = int(os.getenv("MERCHANT_HARD_CEILING_CENTS", "50000"))

    # One-click demo sign-in for the seeded store. When on, GET /merchant/demo-store hands
    # out the seeded merchant's API key to anyone who asks, so that a judge (or a teammate,
    # or a phone) can open the admin page without finding a key first.
    #
    # That is a deliberate trade, and it is only ever the seeded demo store: the key is read
    # from var/merchant-key.txt, which exists only where `python -m seed.reset` has run. Set
    # DEMO_LOGIN_ENABLED=0 for any deployment where the demo store holds anything real.
    demo_login_enabled: bool = os.getenv("DEMO_LOGIN_ENABLED", "1") != "0"
    demo_merchant_id: str = os.getenv("DEMO_MERCHANT_ID", "m_mysa")

    # Receipt email. With no SMTP host configured the mailer writes to a local outbox
    # instead of sending, so a demo machine with no mail server still shows the shopper
    # exactly what would have landed in their inbox.
    smtp_host: str | None = os.getenv("SMTP_HOST") or None
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str | None = os.getenv("SMTP_USERNAME") or None
    smtp_password: str | None = os.getenv("SMTP_PASSWORD") or None
    smtp_starttls: bool = os.getenv("SMTP_STARTTLS", "1") != "0"
    smtp_timeout_seconds: float = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
    receipt_from_email: str = os.getenv("RECEIPT_FROM_EMAIL", "receipts@sway.demo")
    receipt_from_name: str = os.getenv("RECEIPT_FROM_NAME", "Sway Receipts")
    receipt_outbox_path: Path = Path(os.getenv("RECEIPT_OUTBOX_PATH", ROOT / "var" / "outbox"))

    # "simulator" (default, always safe) or "visa" (real VisaNet Connect sandbox call).
    # Never default this to "visa" — an unreachable or misconfigured sandbox must never
    # silently become the payment path the demo runs on.
    payment_adapter: str = os.getenv("PAYMENT_ADAPTER", "simulator")
    visa_api_base_url: str = os.getenv("VISA_API_BASE_URL", "https://sandbox.api.visa.com")
    visa_endpoint_path: str = os.getenv("VISA_ENDPOINT_PATH", "/acs/v3/payments/authorizations")
    visa_ssl_cert_path: str | None = os.getenv("VISA_SSL_CERT_PATH") or None
    visa_ssl_private_key_path: str | None = os.getenv("VISA_SSL_PRIVATE_KEY_PATH") or None
    visa_ca_bundle_path: str | None = os.getenv("VISA_CA_BUNDLE_PATH") or None
    visa_api_username: str | None = os.getenv("VISA_API_USERNAME") or None
    visa_api_password: str | None = os.getenv("VISA_API_PASSWORD") or None
    visa_mle_key_id: str | None = os.getenv("VISA_MLE_KEY_ID") or None
    visa_mle_private_key_path: str | None = os.getenv("VISA_MLE_PRIVATE_KEY_PATH") or None
    # Visa's own public key/cert, used to encrypt outbound MLE fields (distinct from our
    # private key above, which only decrypts what Visa encrypted back to us). Downloaded
    # from the Encryption section of the Visa Developer Center project, not generated here.
    visa_mle_encrypt_cert_path: str | None = os.getenv("VISA_MLE_ENCRYPT_CERT_PATH") or None
    visa_client_id: str | None = os.getenv("VISA_CLIENT_ID") or None


settings = Settings()

