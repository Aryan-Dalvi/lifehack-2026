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


settings = Settings()

