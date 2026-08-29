from __future__ import annotations

import json
import os
from pathlib import Path

from app.auth import hash_password, new_secret, token_digest
from app.db import connect, init_databases, transaction, utc_now
from app.settings import settings

SEED_FILE = Path(__file__).with_name("mysa_catalog.json")

# Where the demo merchant key is left for the operator to copy into the admin UI. Under
# var/, which is gitignored, so a working key never reaches the repo.
MERCHANT_KEY_FILE = settings.database_path.parent / "merchant-key.txt"

DEMO_CONSUMER_EMAIL = "demo@mysa.test"


def seed_if_empty() -> None:
    with connect() as connection:
        exists = connection.execute("SELECT 1 FROM merchants LIMIT 1").fetchone()
    if exists:
        return
    seed()


def _demo_merchant_key() -> str:
    """The demo merchant's API key: taken from the environment, else generated once."""
    from_env = os.getenv("DEMO_MERCHANT_KEY")
    if from_env:
        return from_env
    if MERCHANT_KEY_FILE.exists():
        existing = MERCHANT_KEY_FILE.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    return new_secret("mk")


def _demo_consumer_password() -> str:
    return os.getenv("DEMO_CONSUMER_PASSWORD", "mysa-demo-password")


def seed() -> None:
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    merchant = data["merchant"]
    now = utc_now()
    api_key = _demo_merchant_key()
    password = _demo_consumer_password()
    with transaction() as connection:
        connection.execute(
            "INSERT INTO merchants(merchant_id,api_key_hash,name,size,category,currency,"
            "accent_color,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                merchant["merchant_id"],
                token_digest(api_key),
                merchant["name"],
                merchant["size"],
                merchant["category"],
                merchant["currency"],
                merchant["accent_color"],
                merchant["status"],
                now,
            ),
        )
        for product in data["products"]:
            connection.execute(
                "INSERT INTO products(sku,merchant_id,title,description,price_cents,currency,image_url,"
                "category,attributes_json,stock,rating_avg,rating_count,rating_source,created_at,updated_at) "
                "VALUES (?,?,?,?,?,'SGD',?,'skincare',?,?,?,?, 'merchant_feed',?,?)",
                (
                    product["sku"],
                    merchant["merchant_id"],
                    product["title"],
                    product["description"],
                    product["price_cents"],
                    product["image_url"],
                    json.dumps(product["attributes"]),
                    product["stock"],
                    product["rating_avg"],
                    product["rating_count"],
                    now,
                    now,
                ),
            )
        connection.execute(
            "INSERT INTO consumers(consumer_id,email,password_hash,display_name,created_at) "
            "VALUES ('usr_demo',?,?,'N. Shopper',?)",
            (DEMO_CONSUMER_EMAIL, hash_password(password), now),
        )
        connection.execute(
            "INSERT INTO addresses(address_id,consumer_id,recipient,lines_json,postal_code,country,is_default) "
            "VALUES ('adr_demo','usr_demo','N. Shopper',?,'118420','SG',1)",
            (json.dumps(["14 Prince George's Park", "#05-21"]),),
        )

    MERCHANT_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MERCHANT_KEY_FILE.write_text(api_key, encoding="utf-8")


def reset() -> None:
    init_databases(reset=True)
    seed()


if __name__ == "__main__":
    reset()
    print("Sway databases reset and Mysa Skin seeded.")
    print(f"  merchant API key -> {MERCHANT_KEY_FILE} (paste into the admin page)")
    print(f"  demo shopper     -> {DEMO_CONSUMER_EMAIL} / {_demo_consumer_password()}")
