import json
import tempfile
import unittest

from loom_verath import LoomVerathRuntime
from loom_verath.errors import ConcurrentWrite, InvariantViolation


class StateAndLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = LoomVerathRuntime(self.temp.name)

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def test_six_core_state_invariants(self):
        kernel_id = self.runtime.state.value("system.kernel_id")
        with self.assertRaises(InvariantViolation):
            self.runtime.state.set("system.kernel_id", "replacement")
        self.assertEqual(kernel_id, self.runtime.state.value("system.kernel_id"))

        with self.assertRaises(InvariantViolation):
            self.runtime.state.set("system.phi_coupling", 1.1)
        with self.assertRaises(InvariantViolation):
            self.runtime.state.set("system.ethics_lambda", 0.79)
        with self.assertRaises(InvariantViolation):
            self.runtime.state.set("system.max_recursion", 8)
        with self.assertRaises(InvariantViolation):
            self.runtime.state.set("policy.real_world_actuation", True)
        self.assertTrue(self.runtime.state.assert_invariants()["valid"])

    def test_compare_and_swap_rejects_stale_write(self):
        _, version = self.runtime.state.get("system.phi_coupling")
        self.runtime.state.set("system.phi_coupling", 0.62, expected_version=version)
        with self.assertRaises(ConcurrentWrite):
            self.runtime.state.set("system.phi_coupling", 0.63, expected_version=version)

    def test_snapshot_and_approved_rollback(self):
        snapshot = self.runtime.state.create_snapshot(actor="tester")
        original = self.runtime.state.value("system.phi_coupling")
        self.runtime.state.set("system.phi_coupling", 0.72, actor="tester")
        with self.assertRaises(InvariantViolation):
            self.runtime.state.rollback(
                snapshot["snapshot_id"], actor="tester", human_approved=False
            )
        result = self.runtime.state.rollback(
            snapshot["snapshot_id"], actor="tester", human_approved=True
        )
        self.assertIn("system.phi_coupling", result["changed_keys"])
        self.assertEqual(original, self.runtime.state.value("system.phi_coupling"))

    def test_ledger_detects_payload_tampering(self):
        event = self.runtime.ledger.append("test_event", {"value": 1}, actor="tester")
        self.assertTrue(self.runtime.ledger.verify()["valid"])
        self.runtime.database.connection.execute(
            "UPDATE ledger SET payload_json=? WHERE event_id=?",
            (json.dumps({"value": 2}), event["event_id"]),
        )
        self.runtime.database.connection.commit()
        verification = self.runtime.ledger.verify()
        self.assertFalse(verification["valid"])
        self.assertEqual("event_hash_mismatch", verification["reason"])

    def test_merkle_root_is_stable_without_new_events(self):
        root_one = self.runtime.ledger.merkle_root()
        root_two = self.runtime.ledger.merkle_root()
        self.assertEqual(root_one, root_two)
        self.assertEqual(64, len(root_one))


if __name__ == "__main__":
    unittest.main()

