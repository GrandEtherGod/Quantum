import tempfile
import unittest

from loom_verath import LoomVerathRuntime
from loom_verath.models import EvidenceState
from loom_verath.utils import tokenize


def full_scan_search(runtime, query, limit=5):
    """Reference implementation: the pre-0.4.1 full-scan search, verbatim logic."""
    query_tokens = tokenize(query)
    rows = runtime.database.connection.execute(
        "SELECT * FROM episodes WHERE tombstoned_at IS NULL ORDER BY created_at DESC"
    ).fetchall()
    scored = []
    for row in rows:
        content = runtime.memory._decrypt(row["ciphertext"])
        content_tokens = tokenize(content)
        union = query_tokens | content_tokens
        score = len(query_tokens & content_tokens) / len(union) if union else 0.0
        if score > 0.0:
            scored.append((row["episode_id"], round(score, 6), row["importance"]))
    scored.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return [(episode_id, score) for episode_id, score, _ in scored[:limit]]


class BlindedIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = LoomVerathRuntime(self.temp.name)

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def _seed(self, count, prefix="episode"):
        for index in range(count):
            self.runtime.memory.add_episode(
                f"{prefix} {index} about lunar crystal protocol thermal dome marker{index % 7}",
                session_id=f"s-{index % 5}",
                kind="note",
                importance=0.5,
                evidence_state=EvidenceState.SUPPORTED,
                actor="tester",
            )

    def test_indexed_search_matches_full_scan(self):
        self._seed(60)
        for query in ("lunar crystal", "thermal dome", "marker3 protocol", "nonexistent xyzzy"):
            indexed = [
                (r["episode_id"], r["score"])
                for r in self.runtime.memory.search(query, limit=5)
            ]
            reference = full_scan_search(self.runtime, query, limit=5)
            self.assertEqual(reference, indexed, f"mismatch for query {query!r}")

    def test_tombstoned_episodes_leave_search_and_index(self):
        episode_id = self.runtime.memory.add_episode(
            "secret lunar rendezvous at midnight",
            session_id="s-tomb",
            kind="note",
            actor="tester",
        )
        self.assertTrue(self.runtime.memory.search("lunar rendezvous"))
        self.assertTrue(
            self.runtime.memory.tombstone(episode_id, actor="tester", reason="test")
        )
        self.assertEqual([], self.runtime.memory.search("lunar rendezvous"))
        rows = self.runtime.database.connection.execute(
            "SELECT COUNT(*) AS count FROM episode_token_index WHERE episode_id=?",
            (episode_id,),
        ).fetchone()["count"]
        self.assertEqual(0, rows)

    def test_index_stores_no_plaintext(self):
        self._seed(10)
        rows = self.runtime.database.connection.execute(
            "SELECT token_hmac FROM episode_token_index"
        ).fetchall()
        self.assertTrue(rows)
        for row in rows:
            token_hmac = row["token_hmac"]
            self.assertEqual(64, len(token_hmac))
            int(token_hmac, 16)  # valid hex
        blob = " ".join(row["token_hmac"] for row in rows)
        for plaintext in ("lunar", "crystal", "protocol", "thermal"):
            self.assertNotIn(plaintext, blob)

    def test_candidate_set_is_sublinear(self):
        self._seed(2000)
        candidates = self.runtime.memory.token_index.candidates({"lunar"})
        # 'lunar' appears in every episode here, so use a rare token instead
        rare = self.runtime.memory.token_index.candidates({"marker3"})
        self.assertLess(len(rare), 2000 // 7 + 50)
        self.assertGreater(len(rare), 0)
        self.assertLessEqual(len(candidates), 2000)

    def test_legacy_database_backfills_index_on_open(self):
        self._seed(20)
        # Simulate a pre-0.4.1 database: wipe the index rows.
        with self.runtime.database.transaction() as connection:
            connection.execute("DELETE FROM episode_token_index")
        self.runtime.close()
        reopened = LoomVerathRuntime(self.temp.name)
        try:
            results = reopened.memory.search("lunar crystal")
            self.assertTrue(results)
            count = reopened.database.connection.execute(
                "SELECT COUNT(*) AS count FROM episode_token_index"
            ).fetchone()["count"]
            self.assertGreater(count, 0)
        finally:
            reopened.close()

    def test_empty_query_returns_nothing(self):
        self._seed(5)
        self.assertEqual([], self.runtime.memory.search(""))
        self.assertEqual([], self.runtime.memory.search("!!!"))


if __name__ == "__main__":
    unittest.main()
