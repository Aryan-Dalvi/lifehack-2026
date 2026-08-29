from __future__ import annotations

import json
from pathlib import Path

from app.db import connect, init_databases, transaction, utc_now

SEED_FILE = Path(__file__).with_name("mysa_catalog.json")


def seed_if_empty() -> None:
    with connect() as connection:
        exists = connection.execute("SELECT 1 FROM merchants LIMIT 1").fetchone()
    if exists:
        return
    seed()


def seed() -> None:
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    merchant = data["merchant"]
    now = utc_now()
    with transaction() as connection:
        connection.execute(
            "INSERT INTO merchants(merchant_id,name,size,category,currency,accent_color,status,created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                merchant["merchant_id"],
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
            "INSERT INTO addresses(address_id,consumer_id,recipient,lines_json,postal_code,country,is_default) "
            "VALUES ('adr_demo','usr_demo','N. Shopper',?,'118420','SG',1)",
            (json.dumps(["14 Prince George's Park", "#05-21"]),),
        )


def reset() -> None:
    init_databases(reset=True)
    seed()


if __name__ == "__main__":
    reset()
    print("Sway databases reset and Mysa Skin seeded.")

