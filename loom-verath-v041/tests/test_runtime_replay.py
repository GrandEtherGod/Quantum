import tempfile
import unittest

from loom_verath import LoomVerathRuntime


class RuntimeReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = LoomVerathRuntime(self.temp.name)

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def test_end_to_end_session_replays_exactly(self):
        command = "Create a fireball radius 5 duration 2 intensity 0.4"
        result = self.runtime.run(command, requested_mode="simulation")
        replay = self.runtime.replay(result.session_id)
        self.assertTrue(replay["ledger_chain_valid"])
        self.assertTrue(replay["deterministic"])
        self.assertTrue(replay["output_match"])
        self.assertIn("claim_classified", replay["event_sequence"])
        self.assertIn("runtime_completed", replay["event_sequence"])

    def test_ledger_does_not_store_raw_command(self):
        command = "private lunar phrase 8c57c19e"
        self.runtime.run(command)
        rows = self.runtime.database.connection.execute(
            "SELECT payload_json FROM ledger"
        ).fetchall()
        self.assertFalse(any(command in row["payload_json"] for row in rows))

    def test_empty_input_is_rejected_and_logged(self):
        with self.assertRaises(ValueError):
            self.runtime.run("   ")
        self.assertEqual("input_rejected", self.runtime.ledger.all_events()[-1]["event_type"])

    def test_introspection_and_full_verification(self):
        result = self.runtime.run("Design a bounded software workflow")
        self.assertEqual("completed", result.status)
        introspection = self.runtime.introspect()
        self.assertEqual("healthy", introspection["status"])
        self.assertFalse(introspection["boundary"]["real_world_actuation"])
        self.assertTrue(introspection["verification"]["valid"])


if __name__ == "__main__":
    unittest.main()

