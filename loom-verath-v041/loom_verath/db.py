from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .utils import utc_now


SCHEMA_VERSION = 4
MIGRATIONS = {
    1: "baseline_runtime_schema",
    2: "research_registry",
    3: "review_gated_codepet_release",
    4: "blinded_token_index_and_ledger_checkpoints",
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    version INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS state_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    old_value_json TEXT,
    new_value_json TEXT NOT NULL,
    version INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    state_json TEXT NOT NULL,
    state_root TEXT NOT NULL,
    ledger_seq INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    recorded_at TEXT NOT NULL,
    session_id TEXT,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT UNIQUE NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ledger_session ON ledger(session_id, seq);
CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    ciphertext BLOB,
    content_hash TEXT NOT NULL,
    importance REAL NOT NULL,
    evidence_state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    tombstoned_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session_id);
CREATE TABLE IF NOT EXISTS crystals (
    crystal_id TEXT PRIMARY KEY,
    summary_ciphertext BLOB NOT NULL,
    source_episode_ids_json TEXT NOT NULL,
    stability REAL NOT NULL,
    confidence REAL NOT NULL,
    evidence_state TEXT NOT NULL,
    supersedes TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS capabilities (
    capability_id TEXT PRIMARY KEY,
    principal TEXT NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    actions_json TEXT NOT NULL,
    resource TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS lineage (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT UNIQUE NOT NULL,
    kernel_id TEXT NOT NULL,
    config_root TEXT NOT NULL,
    state_root TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    record_hash TEXT UNIQUE NOT NULL,
    signature_b64 TEXT NOT NULL,
    public_key_b64 TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bridge_contracts (
    contract_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    contract_json TEXT NOT NULL,
    approved INTEGER NOT NULL,
    approved_by TEXT,
    approved_at TEXT
);
CREATE TABLE IF NOT EXISTS research_records (
    record_id TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_hash TEXT UNIQUE NOT NULL,
    review_status TEXT NOT NULL,
    authority TEXT NOT NULL DEFAULT 'research_only',
    ingested_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS episode_token_index (
    token_hmac TEXT NOT NULL,
    episode_id TEXT NOT NULL,
    PRIMARY KEY (token_hmac, episode_id)
);
CREATE INDEX IF NOT EXISTS idx_token_hmac ON episode_token_index(token_hmac);
CREATE TABLE IF NOT EXISTS ledger_checkpoints (
    seq INTEGER PRIMARY KEY,
    event_hash TEXT NOT NULL,
    merkle_root TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    signature_b64 TEXT NOT NULL,
    public_key_b64 TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        current = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            self.connection.close()
            raise RuntimeError(
                f"Database schema {current} is newer than supported schema {SCHEMA_VERSION}"
            )
        self.connection.executescript(SCHEMA)
        self._migrate()
        self.connection.commit()

    def _migrate(self) -> None:
        current = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
        if current > SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema {current} is newer than supported schema {SCHEMA_VERSION}"
            )
        for version in range(1, SCHEMA_VERSION + 1):
            self.connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, MIGRATIONS[version], utc_now()),
            )
        self.connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def schema_version(self) -> dict[str, int]:
        current = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
        return {"current": current, "supported": SCHEMA_VERSION}

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def close(self) -> None:
        self.connection.close()
