import tempfile
import unittest

from loom_verath import LoomVerathRuntime
from loom_verath.models import EvidenceState


class MemoryAndIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = LoomVerathRuntime(self.temp.name)

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def test_episode_is_encrypted_searchable_and_deletable(self):
        secret_text = "CHRYSALIS remembers the lunar crystal protocol"
        episode_id = self.runtime.memory.add_episode(
            secret_text,
            session_id="session-memory",
            kind="note",
            importance=0.9,
            evidence_state=EvidenceState.SUPPORTED,
            actor="tester",
        )
        row = self.runtime.database.connection.execute(
            "SELECT ciphertext FROM episodes WHERE episode_id=?", (episode_id,)
        ).fetchone()
        self.assertNotIn(secret_text.encode(), row["ciphertext"])
        results = self.runtime.memory.search("lunar protocol")
        self.assertEqual(secret_text, results[0]["content"])
        self.assertTrue(
            self.runtime.memory.tombstone(
                episode_id, actor="tester", reason="user deletion request"
            )
        )
        self.assertEqual([], self.runtime.memory.search("lunar protocol"))
        tombstone = self.runtime.database.connection.execute(
            "SELECT ciphertext, tombstoned_at FROM episodes WHERE episode_id=?", (episode_id,)
        ).fetchone()
        self.assertIsNone(tombstone["ciphertext"])
        self.assertIsNotNone(tombstone["tombstoned_at"])

    def test_high_signal_episode_crystallizes(self):
        for index in range(3):
            self.runtime.memory.add_episode(
                f"stable project truth {index} about memory provenance",
                session_id=f"s-{index}",
                kind="note",
                importance=0.9,
                actor="tester",
            )
        result = self.runtime.memory.consolidate(threshold=0.7, actor="tester")
        self.assertTrue(result["created"])
        self.assertEqual(3, result["source_episode_count"])
        self.assertEqual(1, self.runtime.memory.stats()["active_crystals"])

    def test_kernel_identity_persists_across_restart(self):
        kernel_id = self.runtime.state.value("system.kernel_id")
        self.assertTrue(self.runtime.identity.verify()["valid"])
        self.runtime.close()
        self.runtime = LoomVerathRuntime(self.temp.name)
        self.assertEqual(kernel_id, self.runtime.state.value("system.kernel_id"))
        self.assertTrue(self.runtime.identity.verify()["valid"])


if __name__ == "__main__":
    unittest.main()

