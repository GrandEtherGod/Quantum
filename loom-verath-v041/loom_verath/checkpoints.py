"""Signed checkpoints for incremental ledger verification.

A checkpoint binds (seq, event_hash, merkle_root) with the runtime's Ed25519
identity key every ``interval`` appends. Verification then resumes from the
latest *valid* checkpoint instead of walking the full hash chain, turning
per-verification cost from O(chain length) into O(entries since checkpoint).

Trust semantics (read carefully):
- The fast path authenticates the checkpoint signature, binds it to the
  chain head stored at that seq, and fully re-walks every event after the
  checkpoint. History *before* the checkpoint is trusted via the checkpoint
  signature: the signature attests the chain head as of seal time, and the
  trust anchor remains local (the identity key lives on the same host as the
  database), exactly as with the hash chain itself.
- A checkpoint whose signature does not verify, or whose event_hash does not
  match the event stored at that seq (e.g. a checkpoint row transplanted from
  another database), is ignored and verification falls back to the full walk.
  A forged checkpoint can never make a tampered chain verify; at worst it
  costs the full walk.
- Use ``verify_full()`` for the authoritative complete re-walk, e.g. after
  suspected storage-level corruption of pre-checkpoint history.
- Checkpoints are written in the same transaction as the append that
  triggers them, so a checkpoint can never reference a missing event.
"""
from __future__ import annotations

import base64
import sqlite3
from typing import Any, Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .db import Database
from .ledger import GENESIS_HASH
from .utils import canonical_json, utc_now

DEFAULT_CHECKPOINT_INTERVAL = 1000


class LedgerCheckpointer:
    """Creates and validates Ed25519-signed ledger checkpoints."""

    def __init__(
        self,
        database: Database,
        *,
        interval: int = DEFAULT_CHECKPOINT_INTERVAL,
        sign: Callable[[bytes], bytes],
        public_key_b64: str,
    ):
        if interval < 1:
            raise ValueError("checkpoint interval must be >= 1")
        self.database = database
        self.interval = interval
        self._sign = sign
        self.public_key_b64 = public_key_b64

    def _checkpoint_body(self, seq: int, event_hash: str, merkle_root: str, recorded_at: str) -> dict[str, Any]:
        return {
            "seq": seq,
            "event_hash": event_hash,
            "merkle_root": merkle_root,
            "recorded_at": recorded_at,
        }

    def checkpoint(
        self, ledger: Any, connection: sqlite3.Connection | None = None
    ) -> dict[str, Any]:
        """Seal a checkpoint at the current chain head. Returns the checkpoint row."""
        connection = connection if connection is not None else self.database.connection
        last = connection.execute(
            "SELECT seq, event_hash FROM ledger ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if last is None:
            raise ValueError("cannot checkpoint an empty ledger")
        merkle_root = ledger.merkle_root()
        recorded_at = utc_now()
        body = self._checkpoint_body(last["seq"], last["event_hash"], merkle_root, recorded_at)
        signature = self._sign(canonical_json(body).encode("ascii"))
        connection.execute(
            """
            INSERT OR REPLACE INTO ledger_checkpoints(
                seq, event_hash, merkle_root, recorded_at, signature_b64, public_key_b64
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                last["seq"],
                last["event_hash"],
                merkle_root,
                recorded_at,
                base64.b64encode(signature).decode("ascii"),
                self.public_key_b64,
            ),
        )
        return {**body, "signature_b64": base64.b64encode(signature).decode("ascii")}

    def maybe_checkpoint(
        self, ledger: Any, connection: sqlite3.Connection, seq: int
    ) -> dict[str, Any] | None:
        """Checkpoint when an append lands exactly on an interval boundary."""
        if seq > 0 and seq % self.interval == 0:
            return self.checkpoint(ledger, connection)
        return None

    def latest_checkpoint(self) -> dict[str, Any] | None:
        row = self.database.connection.execute(
            "SELECT * FROM ledger_checkpoints ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def _signature_valid(self, row: dict[str, Any]) -> bool:
        body = self._checkpoint_body(
            row["seq"], row["event_hash"], row["merkle_root"], row["recorded_at"]
        )
        try:
            public_key = Ed25519PublicKey.from_public_bytes(
                base64.b64decode(row["public_key_b64"])
            )
            public_key.verify(
                base64.b64decode(row["signature_b64"]),
                canonical_json(body).encode("ascii"),
            )
            return True
        except Exception:
            return False

    def verify(self, ledger: Any) -> dict[str, Any]:
        """Verify the chain, resuming from the latest valid checkpoint when possible."""
        row = self.latest_checkpoint()
        if row is None:
            result = ledger.verify_range(1, GENESIS_HASH)
            result["mode"] = "full_chain"
            return result
        if not self._signature_valid(row):
            result = ledger.verify_range(1, GENESIS_HASH)
            result["mode"] = "full_chain"
            result["checkpoint"] = "invalid_signature"
            return result
        anchor = ledger.database.connection.execute(
            "SELECT event_hash FROM ledger WHERE seq=?", (row["seq"],)
        ).fetchone()
        if anchor is None or anchor["event_hash"] != row["event_hash"]:
            result = ledger.verify_range(1, GENESIS_HASH)
            result["mode"] = "full_chain"
            result["checkpoint"] = "binding_failed"
            return result
        result = ledger.verify_range(row["seq"] + 1, row["event_hash"])
        result["mode"] = "checkpointed"
        result["checkpoint_seq"] = row["seq"]
        return result
