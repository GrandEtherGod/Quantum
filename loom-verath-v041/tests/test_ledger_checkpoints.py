import base64
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from loom_verath import LoomVerathRuntime
from loom_verath.checkpoints import LedgerCheckpointer
from loom_verath.db import Database
from loom_verath.ledger import ChronoScribeLedger


def make_checkpointer(database, interval=10):
    key = Ed25519PrivateKey.generate()
    public_b64 = base64.b64encode(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")
    checkpointer = LedgerCheckpointer(
        database, interval=interval, sign=key.sign, public_key_b64=public_b64
    )
    return checkpointer, key


def _sign_body(key, seq, event_hash, merkle_root, recorded_at):
    from loom_verath.utils import canonical_json

    body = {
        "seq": seq,
        "event_hash": event_hash,
        "merkle_root": merkle_root,
        "recorded_at": recorded_at,
    }
    return base64.b64encode(key.sign(canonical_json(body).encode("ascii"))).decode("ascii")


class LedgerCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp.name) / "test.sqlite3")
        self.ledger = ChronoScribeLedger(self.database)
        self.checkpointer, self.key = make_checkpointer(self.database, interval=10)
        self.ledger.set_checkpointer(self.checkpointer)

    def tearDown(self):
        self.database.close()
        self.temp.cleanup()

    def _append(self, count, event_type="test_event"):
        for index in range(count):
            self.ledger.append(event_type, {"i": index}, actor="tester")

    def test_checkpoint_sealed_at_interval_boundary(self):
        self._append(25)
        row = self.checkpointer.latest_checkpoint()
        self.assertIsNotNone(row)
        self.assertEqual(20, row["seq"])  # last boundary <= 25
        self.assertTrue(row["signature_b64"])
        self.assertTrue(row["public_key_b64"])

    def test_verify_resumes_from_checkpoint(self):
        self._append(25)
        result = self.ledger.verify()
        self.assertTrue(result["valid"], result)
        self.assertEqual("checkpointed", result["mode"])
        self.assertEqual(20, result["checkpoint_seq"])
        self.assertEqual(5, result["checked"])  # only events 21..25 re-walked
        self.assertEqual(self.ledger.last_hash(), result["root"])

    def test_chain_without_checkpoints_still_validates(self):
        database = Database(Path(self.temp.name) / "legacy.sqlite3")
        legacy = ChronoScribeLedger(database)  # no checkpointer attached
        for index in range(15):
            legacy.append("legacy_event", {"i": index}, actor="tester")
        result = legacy.verify()
        self.assertTrue(result["valid"], result)
        self.assertEqual("full_chain", result["mode"])
        self.assertEqual(15, result["checked"])
        database.close()

    def test_tamper_after_checkpoint_fails_at_exact_event(self):
        self._append(25)
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE ledger SET payload_json=? WHERE seq=?",
                ('{"i": "tampered"}', 23),
            )
        result = self.ledger.verify()
        self.assertFalse(result["valid"])
        self.assertEqual(23, result["failed_seq"])
        self.assertEqual("event_hash_mismatch", result["reason"])

    def test_tamper_before_checkpoint_detected_by_full_walk(self):
        # Fast-path trust semantics: pre-checkpoint history is trusted via the
        # checkpoint signature, so a full re-walk is the authority for old
        # payload tampering. verify_full() must catch it at the exact event.
        self._append(25)
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE ledger SET payload_json=? WHERE seq=?",
                ('{"i": "tampered"}', 7),
            )
        result = self.ledger.verify_full()
        self.assertFalse(result["valid"])
        self.assertEqual(7, result["failed_seq"])
        self.assertEqual("event_hash_mismatch", result["reason"])

    def test_forged_checkpoint_falls_back_to_full_walk(self):
        self._append(25)
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE ledger_checkpoints SET signature_b64=?",
                (base64.b64encode(b"forged-signature").decode("ascii"),),
            )
        result = self.ledger.verify()
        self.assertTrue(result["valid"], result)
        self.assertEqual("full_chain", result["mode"])
        self.assertEqual("invalid_signature", result["checkpoint"])
        self.assertEqual(25, result["checked"])

    def test_checkpoint_binding_failure_falls_back_to_full_walk(self):
        # Transplant scenario: a validly-signed checkpoint whose event_hash
        # does not match this chain's event at that seq. Re-sign after the
        # edit so the signature stays valid and only binding fails.
        self._append(25)
        row = self.database.connection.execute(
            "SELECT seq, event_hash, merkle_root, recorded_at FROM ledger_checkpoints"
            " ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        forged_hash = "0" * 64
        new_signature = _sign_body(
            self.key, row["seq"], forged_hash, row["merkle_root"], row["recorded_at"]
        )
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE ledger_checkpoints SET event_hash=?, signature_b64=?",
                (forged_hash, new_signature),
            )
        result = self.ledger.verify()
        self.assertTrue(result["valid"], result)
        self.assertEqual("full_chain", result["mode"])
        self.assertEqual("binding_failed", result["checkpoint"])

    def test_runtime_wires_checkpointer(self):
        runtime = LoomVerathRuntime(self.temp.name + "-rt")
        try:
            self.assertIsNotNone(runtime.checkpointer)
            checkpoint = runtime.checkpointer.checkpoint(runtime.ledger)
            self.assertGreater(checkpoint["seq"], 0)
            result = runtime.ledger.verify()
            self.assertTrue(result["valid"], result)
            self.assertEqual("checkpointed", result["mode"])
            self.assertTrue(runtime.verify()["valid"])
        finally:
            runtime.close()


if __name__ == "__main__":
    unittest.main()
