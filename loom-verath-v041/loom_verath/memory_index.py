"""Blinded keyword index for encrypted episodic memory.

The episode bodies are Fernet-encrypted, so the database cannot be searched
without decryption. This module keeps a *blinded* token index alongside the
ciphertext: each row is HMAC(index_key, token) -> episode_id, where index_key
is derived from the memory Fernet key via HKDF and never stored separately.

Properties:
- Sub-linear retrieval: only episodes sharing at least one query token are
  decrypted and scored. Jaccard scoring is unchanged, so indexed search
  returns exactly the same results as the legacy full scan.
- Blinded: the database reveals token-equality patterns (which episodes share
  a token) but never plaintext tokens. Token plaintext is not recoverable
  from the index without the index key.
- Tombstoned episodes are removed from the index at tombstone time.
"""
from __future__ import annotations

import base64
import hmac
import sqlite3
from hashlib import sha256

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .db import Database
from .utils import tokenize

INDEX_KEY_INFO = b"loom-verath/episode-token-index/v1"


def derive_index_key(fernet_key: bytes) -> bytes:
    """Derive the 32-byte blinded-index HMAC key from the memory Fernet key."""
    raw = base64.urlsafe_b64decode(fernet_key)
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=INDEX_KEY_INFO,
    ).derive(raw)


class BlindedTokenIndex:
    """HMAC-blinded inverted index: blinded token -> episode ids."""

    def __init__(self, database: Database, index_key: bytes):
        self.database = database
        if len(index_key) != 32:
            raise ValueError("index_key must be 32 bytes")
        self.index_key = index_key

    def _blind(self, token: str) -> str:
        return hmac.new(self.index_key, token.encode("utf-8"), sha256).hexdigest()

    def index_episode(
        self, connection: sqlite3.Connection, episode_id: str, content: str
    ) -> int:
        """Index one episode's tokens. Must be called inside the caller's transaction."""
        rows = [(self._blind(token), episode_id) for token in tokenize(content)]
        connection.executemany(
            "INSERT OR IGNORE INTO episode_token_index(token_hmac, episode_id)"
            " VALUES (?, ?)",
            rows,
        )
        return len(rows)

    def remove_episode(self, connection: sqlite3.Connection, episode_id: str) -> None:
        """Drop an episode's index rows. Must be called inside the caller's transaction."""
        connection.execute(
            "DELETE FROM episode_token_index WHERE episode_id=?", (episode_id,)
        )

    def candidates(self, query_tokens: set[str]) -> set[str]:
        """Episode ids sharing at least one blinded query token.

        Any episode with Jaccard score > 0 shares a token with the query, so
        this candidate set always contains every episode the full scan would
        have returned.
        """
        if not query_tokens:
            return set()
        blinded = [self._blind(token) for token in query_tokens]
        found: set[str] = set()
        connection = self.database.connection
        for start in range(0, len(blinded), 500):
            chunk = blinded[start : start + 500]
            placeholders = ",".join("?" for _ in chunk)
            rows = connection.execute(
                f"SELECT DISTINCT episode_id FROM episode_token_index"
                f" WHERE token_hmac IN ({placeholders})",
                chunk,
            ).fetchall()
            found.update(row["episode_id"] for row in rows)
        return found

    def row_count(self) -> int:
        return self.database.connection.execute(
            "SELECT COUNT(*) AS count FROM episode_token_index"
        ).fetchone()["count"]
