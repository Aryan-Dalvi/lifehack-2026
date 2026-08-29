from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    web_base_url: str = os.getenv("WEB_BASE_URL", "http://localhost:5173")
    merchant_hard_ceiling_cents: int = int(os.getenv("MERCHANT_HARD_CEILING_CENTS", "50000"))


settings = Settings()

