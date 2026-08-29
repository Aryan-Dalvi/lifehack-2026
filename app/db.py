from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.settings import settings


class ClosingConnection(sqlite3.Connection):
    """Make ``with connect()`` release Windows file handles after commit/rollback."""

    def __exit__(self, exc_type, exc_value, traceback):
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        path,
        timeout=10,
        check_same_thread=False,
        factory=ClosingConnection,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def connect() -> sqlite3.Connection:
    return _connect(settings.database_path)


def issuer_connect() -> sqlite3.Connection:
    return _connect(settings.issuer_database_path)


@contextmanager
def transaction(*, issuer: bool = False) -> Iterator[sqlite3.Connection]:
    connection = issuer_connect() if issuer else connect()
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


MAIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS merchants (
    merchant_id TEXT PRIMARY KEY,
    api_key_hash TEXT,
    name TEXT NOT NULL,
    size TEXT NOT NULL CHECK (size IN ('sme', 'enterprise')),
    category TEXT NOT NULL CHECK (category = 'skincare'),
    currency TEXT NOT NULL DEFAULT 'SGD',
    accent_color TEXT NOT NULL DEFAULT '#6f8066',
    status TEXT NOT NULL DEFAULT 'draft',
    persona TEXT NOT NULL DEFAULT 'Calm, precise skincare guide',
    policies_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    currency TEXT NOT NULL,
    image_url TEXT,
    category TEXT NOT NULL CHECK (category = 'skincare'),
    attributes_json TEXT NOT NULL DEFAULT '{}',
    stock INTEGER NOT NULL CHECK (stock >= 0),
    rating_avg REAL,
    rating_count INTEGER,
    rating_source TEXT NOT NULL DEFAULT 'none',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_sources (
    upload_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    source_format TEXT NOT NULL CHECK (source_format IN ('csv', 'xlsx', 'json')),
    source_sha256 TEXT NOT NULL,
    raw_bytes BLOB NOT NULL,
    byte_count INTEGER NOT NULL CHECK (byte_count >= 0),
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    source_metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_source_rows (
    upload_id TEXT NOT NULL REFERENCES catalog_sources(upload_id) ON DELETE CASCADE,
    source_record_id TEXT NOT NULL,
    row_number INTEGER NOT NULL CHECK (row_number >= 1),
    sheet_name TEXT,
    raw_row_json TEXT NOT NULL,
    raw_row_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (upload_id, source_record_id)
);

CREATE TABLE IF NOT EXISTS catalog_clean_runs (
    run_id TEXT PRIMARY KEY,
    upload_id TEXT NOT NULL REFERENCES catalog_sources(upload_id) ON DELETE CASCADE,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id) ON DELETE CASCADE,
    schema_version TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    cleaner_version TEXT NOT NULL,
    taxonomy_version TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    model_name TEXT NOT NULL,
    classifier_source TEXT NOT NULL DEFAULT 'pending',
    status TEXT NOT NULL CHECK (status IN ('cleaning', 'review_ready', 'published', 'failed')),
    mapping_json TEXT NOT NULL DEFAULT '{}',
    mapping_report_json TEXT NOT NULL DEFAULT '{}',
    diagnostics_json TEXT NOT NULL DEFAULT '{}',
    taxonomy_json TEXT NOT NULL DEFAULT '{}',
    summary_json TEXT NOT NULL DEFAULT '{}',
    preview_hash TEXT,
    publish_mode TEXT CHECK (publish_mode IN ('replace', 'upsert')),
    publication_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS catalog_clean_rows (
    run_id TEXT NOT NULL REFERENCES catalog_clean_runs(run_id) ON DELETE CASCADE,
    upload_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    row_number INTEGER NOT NULL CHECK (row_number >= 1),
    status TEXT NOT NULL CHECK (status IN ('ready', 'review_required', 'rejected')),
    locked_facts_json TEXT,
    classification_json TEXT NOT NULL DEFAULT '{}',
    canonical_json TEXT,
    issues_json TEXT NOT NULL DEFAULT '[]',
    classifier_source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, source_record_id),
    FOREIGN KEY (upload_id, source_record_id)
        REFERENCES catalog_source_rows(upload_id, source_record_id)
);

CREATE TABLE IF NOT EXISTS catalog_images (
    image_id TEXT PRIMARY KEY,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id) ON DELETE CASCADE,
    archive_name TEXT NOT NULL,
    entry_name TEXT NOT NULL,
    stem TEXT NOT NULL,
    content_type TEXT NOT NULL,
    byte_count INTEGER NOT NULL CHECK (byte_count > 0),
    sha256 TEXT NOT NULL,
    image_bytes BLOB NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS catalog_images_by_merchant ON catalog_images(merchant_id);

CREATE TRIGGER IF NOT EXISTS catalog_sources_immutable
BEFORE UPDATE ON catalog_sources
BEGIN
    SELECT RAISE(ABORT, 'catalog source records are immutable');
END;

CREATE TRIGGER IF NOT EXISTS catalog_sources_no_delete
BEFORE DELETE ON catalog_sources
BEGIN
    SELECT RAISE(ABORT, 'catalog source records cannot be deleted');
END;

CREATE TRIGGER IF NOT EXISTS catalog_source_rows_immutable
BEFORE UPDATE ON catalog_source_rows
BEGIN
    SELECT RAISE(ABORT, 'catalog source rows are immutable');
END;


CREATE TRIGGER IF NOT EXISTS catalog_source_rows_no_delete
BEFORE DELETE ON catalog_source_rows
BEGIN
    SELECT RAISE(ABORT, 'catalog source rows cannot be deleted');
END;

CREATE TRIGGER IF NOT EXISTS catalog_source_rows_closed_after_staging
BEFORE INSERT ON catalog_source_rows
WHEN EXISTS (SELECT 1 FROM catalog_clean_runs WHERE upload_id=NEW.upload_id)
BEGIN
    SELECT RAISE(ABORT, 'catalog source staging is closed');
END;

CREATE TABLE IF NOT EXISTS addresses (
    address_id TEXT PRIMARY KEY,
    consumer_id TEXT NOT NULL,
    recipient TEXT NOT NULL,
    lines_json TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    country TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    session_token_hash TEXT,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id),
    consumer_id TEXT NOT NULL,
    is_anonymous INTEGER NOT NULL DEFAULT 1,
    category TEXT NOT NULL CHECK (category = 'skincare'),
    active_intent_id TEXT,
    active_cart_id TEXT,
    visible_skus_json TEXT NOT NULL DEFAULT '[]',
    profile_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS mandates (
    mandate_id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('intent', 'cart', 'payment')),
    parent_id TEXT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    version INTEGER NOT NULL DEFAULT 1,
    supersedes TEXT,
    payload_json TEXT NOT NULL,
    cart_hash TEXT,
    signature TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS carts (
    cart_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    intent_id TEXT NOT NULL REFERENCES mandates(mandate_id),
    cart_mandate_id TEXT NOT NULL REFERENCES mandates(mandate_id),
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id),
    items_json TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    shipping_address_id TEXT NOT NULL,
    shipping_fingerprint TEXT NOT NULL,
    cart_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'preview',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_tokens (
    token_id TEXT PRIMARY KEY,
    consumer_id TEXT NOT NULL,
    network_token_last4 TEXT NOT NULL,
    bound_agent_kid TEXT NOT NULL,
    constraints_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    cart_id TEXT NOT NULL,
    status TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    auth_code TEXT,
    issuer TEXT,
    eci TEXT,
    simulated INTEGER NOT NULL DEFAULT 1,
    decline_code TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    transaction_id TEXT NOT NULL UNIQUE REFERENCES transactions(transaction_id),
    session_id TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trust_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    at TEXT NOT NULL,
    stage TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS consumers (
    consumer_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS consumer_tokens (
    token_hash TEXT PRIMARY KEY,
    consumer_id TEXT NOT NULL REFERENCES consumers(consumer_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_consumer_tokens_consumer ON consumer_tokens(consumer_id);

CREATE TABLE IF NOT EXISTS tap_nonces (
    nonce TEXT PRIMARY KEY,
    expires_at INTEGER NOT NULL
);
"""


ISSUER_SCHEMA = """
CREATE TABLE IF NOT EXISTS challenges (
    challenge_id TEXT PRIMARY KEY,
    consumer_id TEXT NOT NULL,
    cart_hash TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    merchant_id TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS issuer_tokens (
    bank_token TEXT PRIMARY KEY,
    challenge_id TEXT NOT NULL UNIQUE,
    issuer TEXT NOT NULL,
    eci TEXT NOT NULL,
    cart_hash TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    merchant_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'issued',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


# Columns added after the first databases were written. SQLite has no ADD COLUMN IF NOT
# EXISTS, so they are applied by inspection — an existing var/sway.db must not have to be
# deleted to pick up authentication.
_ADDED_COLUMNS = (
    ("merchants", "api_key_hash", "TEXT"),
    ("sessions", "session_token_hash", "TEXT"),
    ("sessions", "is_anonymous", "INTEGER NOT NULL DEFAULT 1"),
    ("sessions", "expires_at", "TEXT"),
    ("catalog_clean_runs", "mapping_report_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("catalog_clean_runs", "diagnostics_json", "TEXT NOT NULL DEFAULT '{}'"),
)


def _migrate(connection: sqlite3.Connection) -> None:
    for table, column, declaration in _ADDED_COLUMNS:
        existing = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")


def init_databases(*, reset: bool = False) -> None:
    if reset:
        for path in (settings.database_path, settings.issuer_database_path):
            if path.exists():
                path.unlink()

    with connect() as connection:
        connection.executescript(MAIN_SCHEMA)
        _migrate(connection)
        connection.commit()
    with issuer_connect() as connection:
        connection.executescript(ISSUER_SCHEMA)


def as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def json_load(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)
