from __future__ import annotations

import base64
import uuid
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from .db import Database
from .ledger import ChronoScribeLedger, GENESIS_HASH
from .state import StateStore
from .utils import canonical_json, sha256_hex, utc_now


class IdentityLineage:
    """Ed25519-signed system lineage anchored to a stable kernel ID."""

    def __init__(
        self,
        data_dir: Path,
        database: Database,
        state: StateStore,
        ledger: ChronoScribeLedger,
    ):
        self.data_dir = data_dir
        self.database = database
        self.state = state
        self.ledger = ledger
        self.key_dir = data_dir / "keys"
        self.key_dir.mkdir(parents=True, exist_ok=True)
        self.private_key_path = self.key_dir / "lineage_ed25519.pem"
        self.private_key = self._load_or_create_key()

    def _load_or_create_key(self) -> Ed25519PrivateKey:
        if self.private_key_path.exists():
            return serialization.load_pem_private_key(
                self.private_key_path.read_bytes(), password=None
            )
        private_key = Ed25519PrivateKey.generate()
        encoded = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.private_key_path.write_bytes(encoded)
        self.private_key_path.chmod(0o600)
        return private_key

    def attest(self, config_root: str, *, reason: str) -> dict[str, Any]:
        last = self.database.connection.execute(
            "SELECT record_hash FROM lineage ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        previous_hash = last["record_hash"] if last else GENESIS_HASH
        record_id = str(uuid.uuid4())
        created_at = utc_now()
        body = {
            "record_id": record_id,
            "kernel_id": self.state.value("system.kernel_id"),
            "config_root": config_root,
            "state_root": self.state.digest(),
            "previous_hash": previous_hash,
            "reason": reason,
            "created_at": created_at,
        }
        record_hash = sha256_hex(previous_hash + canonical_json(body))
        signature = self.private_key.sign(record_hash.encode("ascii"))
        public_raw = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO lineage(
                    record_id, kernel_id, config_root, state_root, previous_hash,
                    record_hash, signature_b64, public_key_b64, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    body["kernel_id"],
                    config_root,
                    body["state_root"],
                    previous_hash,
                    record_hash,
                    base64.b64encode(signature).decode("ascii"),
                    base64.b64encode(public_raw).decode("ascii"),
                    reason,
                    created_at,
                ),
            )
            self.ledger.append(
                "lineage_attested",
                {
                    "record_id": record_id,
                    "record_hash": record_hash,
                    "state_root": body["state_root"],
                    "config_root": config_root,
                    "reason": reason,
                },
                connection=connection,
            )
        return {**body, "record_hash": record_hash}

    def ensure_baseline(self, config_root: str) -> dict[str, Any]:
        row = self.database.connection.execute(
            "SELECT record_hash, state_root, config_root FROM lineage ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return self.attest(config_root, reason="known_good_baseline")
        if row["config_root"] != config_root:
            return self.attest(config_root, reason="configuration_root_changed")
        return {
            "record_hash": row["record_hash"],
            "state_root": row["state_root"],
            "config_root": row["config_root"],
        }

    def verify(self) -> dict[str, Any]:
        rows = self.database.connection.execute("SELECT * FROM lineage ORDER BY seq").fetchall()
        expected_previous = GENESIS_HASH
        checked = 0
        for row in rows:
            body = {
                "record_id": row["record_id"],
                "kernel_id": row["kernel_id"],
                "config_root": row["config_root"],
                "state_root": row["state_root"],
                "previous_hash": row["previous_hash"],
                "reason": row["reason"],
                "created_at": row["created_at"],
            }
            expected_hash = sha256_hex(expected_previous + canonical_json(body))
            if row["previous_hash"] != expected_previous or row["record_hash"] != expected_hash:
                return {
                    "valid": False,
                    "checked": checked,
                    "failed_seq": row["seq"],
                    "reason": "lineage_hash_mismatch",
                }
            try:
                public_key = Ed25519PublicKey.from_public_bytes(
                    base64.b64decode(row["public_key_b64"])
                )
                public_key.verify(
                    base64.b64decode(row["signature_b64"]), row["record_hash"].encode("ascii")
                )
            except Exception:
                return {
                    "valid": False,
                    "checked": checked,
                    "failed_seq": row["seq"],
                    "reason": "signature_invalid",
                }
            expected_previous = row["record_hash"]
            checked += 1
        return {"valid": True, "checked": checked, "root": expected_previous}
