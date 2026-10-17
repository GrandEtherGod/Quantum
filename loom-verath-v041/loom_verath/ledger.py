from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any

from .db import Database
from .utils import canonical_json, sha256_hex, utc_now


GENESIS_HASH = "0" * 64


class ChronoScribeLedger:
    """Append-only, SHA-256 hash-chained decision ledger."""

    def __init__(self, database: Database):
        self.database = database
        self._checkpointer = None

    def set_checkpointer(self, checkpointer) -> None:
        """Attach a LedgerCheckpointer for sealed periodic checkpoints.

        With no checkpointer attached, append/verify behave exactly as before.
        """
        self._checkpointer = checkpointer

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        session_id: str | None = None,
        actor: str = "system",
        connection: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        if connection is not None:
            return self._append(connection, event_type, payload, session_id, actor)
        with self.database.transaction() as active:
            return self._append(active, event_type, payload, session_id, actor)

    def _append(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        payload: dict[str, Any],
        session_id: str | None,
        actor: str,
    ) -> dict[str, Any]:
        previous = connection.execute(
            "SELECT event_hash FROM ledger ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        previous_hash = previous["event_hash"] if previous else GENESIS_HASH
        event_id = str(uuid.uuid4())
        recorded_at = utc_now()
        body = {
            "event_id": event_id,
            "recorded_at": recorded_at,
            "session_id": session_id,
            "actor": actor,
            "event_type": event_type,
            "payload": payload,
        }
        event_hash = sha256_hex(previous_hash + canonical_json(body))
        cursor = connection.execute(
            """
            INSERT INTO ledger(
                event_id, recorded_at, session_id, actor, event_type,
                payload_json, previous_hash, event_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                recorded_at,
                session_id,
                actor,
                event_type,
                canonical_json(payload),
                previous_hash,
                event_hash,
            ),
        )
        if self._checkpointer is not None:
            self._checkpointer.maybe_checkpoint(self, connection, cursor.lastrowid)
        return {**body, "seq": cursor.lastrowid, "previous_hash": previous_hash, "event_hash": event_hash}

    def last_hash(self) -> str:
        row = self.database.connection.execute(
            "SELECT event_hash FROM ledger ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return row["event_hash"] if row else GENESIS_HASH

    def events_for_session(self, session_id: str) -> list[dict[str, Any]]:
        rows = self.database.connection.execute(
            "SELECT * FROM ledger WHERE session_id=? ORDER BY seq", (session_id,)
        ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def all_events(self) -> list[dict[str, Any]]:
        rows = self.database.connection.execute("SELECT * FROM ledger ORDER BY seq").fetchall()
        return [self._row_to_event(row) for row in rows]

    def events_from(self, start_seq: int) -> list[dict[str, Any]]:
        rows = self.database.connection.execute(
            "SELECT * FROM ledger WHERE seq >= ? ORDER BY seq", (start_seq,)
        ).fetchall()
        return [self._row_to_event(row) for row in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "seq": row["seq"],
            "event_id": row["event_id"],
            "recorded_at": row["recorded_at"],
            "session_id": row["session_id"],
            "actor": row["actor"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload_json"]),
            "previous_hash": row["previous_hash"],
            "event_hash": row["event_hash"],
        }

    def verify(self) -> dict[str, Any]:
        """Verify the ledger.

        With a checkpointer attached, verification resumes from the latest
        *valid* sealed checkpoint instead of walking the full chain. Trust
        semantics of the fast path: the checkpoint signature authenticates the
        chain head as of seal time, and every event after the checkpoint is
        fully re-walked. History *before* the checkpoint is trusted via the
        checkpoint signature (local-only trust anchor, as with the chain
        itself). Use verify_full() when a complete re-walk is required, e.g.
        after suspected storage-level corruption.
        """
        if self._checkpointer is not None:
            return self._checkpointer.verify(self)
        result = self.verify_range(1, GENESIS_HASH)
        result["mode"] = "full_chain"
        return result

    def verify_full(self) -> dict[str, Any]:
        """Authoritative full-chain walk, ignoring any checkpoints."""
        result = self.verify_range(1, GENESIS_HASH)
        result["mode"] = "full_chain"
        return result

    def verify_range(self, start_seq: int, expected_previous: str) -> dict[str, Any]:
        """Walk the hash chain from start_seq, expecting expected_previous first."""
        checked = 0
        for event in self.events_from(start_seq):
            body = {
                "event_id": event["event_id"],
                "recorded_at": event["recorded_at"],
                "session_id": event["session_id"],
                "actor": event["actor"],
                "event_type": event["event_type"],
                "payload": event["payload"],
            }
            expected_hash = sha256_hex(expected_previous + canonical_json(body))
            if event["previous_hash"] != expected_previous:
                return {
                    "valid": False,
                    "checked": checked,
                    "failed_seq": event["seq"],
                    "reason": "previous_hash_mismatch",
                }
            if event["event_hash"] != expected_hash:
                return {
                    "valid": False,
                    "checked": checked,
                    "failed_seq": event["seq"],
                    "reason": "event_hash_mismatch",
                }
            expected_previous = event["event_hash"]
            checked += 1
        return {"valid": True, "checked": checked, "root": expected_previous}

    def merkle_root(self) -> str:
        hashes = [event["event_hash"] for event in self.all_events()]
        if not hashes:
            return GENESIS_HASH
        while len(hashes) > 1:
            if len(hashes) % 2:
                hashes.append(hashes[-1])
            hashes = [
                sha256_hex(hashes[index] + hashes[index + 1])
                for index in range(0, len(hashes), 2)
            ]
        return hashes[0]

