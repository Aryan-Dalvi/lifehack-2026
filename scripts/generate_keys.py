from __future__ import annotations

from app.settings import settings
from payments.tap import public_key

if __name__ == "__main__":
    key = public_key()
    print(f"Generated local Ed25519 agent key at {settings.signing_key_path}")
    print(f"Registered key id: {settings.agent_kid}; public key length: {len(key.public_bytes_raw())} bytes")

