import tempfile
import unittest

from loom_verath import LoomVerathRuntime


class OuroborosEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = LoomVerathRuntime(self.temp.name)

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def test_rejects_guardrail_weakening(self):
        result = self.runtime.evaluator.propose_and_apply(
            {"system.ethics_lambda": 0.1}, actor="tester"
        )
        self.assertFalse(result["accepted"])
        self.assertEqual(0.8, self.runtime.state.value("system.ethics_lambda"))

    def test_structural_change_requires_human_approval(self):
        denied = self.runtime.evaluator.propose_and_apply(
            {"system.max_recursion": 6}, actor="tester", human_approved=False
        )
        self.assertFalse(denied["accepted"])
        accepted = self.runtime.evaluator.propose_and_apply(
            {"system.max_recursion": 6}, actor="tester", human_approved=True
        )
        self.assertTrue(accepted["applied"])
        self.assertEqual(6, self.runtime.state.value("system.max_recursion"))
        self.assertTrue(self.runtime.verify()["valid"])

    def test_tunable_change_has_rollback_snapshot(self):
        result = self.runtime.evaluator.propose_and_apply(
            {"system.phi_coupling": 0.62}, actor="tester"
        )
        self.assertTrue(result["applied"])
        self.assertIn("rollback_snapshot_id", result)
        self.assertEqual(0.62, self.runtime.state.value("system.phi_coupling"))


if __name__ == "__main__":
    unittest.main()

