import tempfile
import unittest
from unittest.mock import Mock

from loom_verath import LoomVerathRuntime
from loom_verath.errors import CapabilityDenied


class ClassifierAndGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = LoomVerathRuntime(self.temp.name)

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def test_fireball_maps_to_safe_vox_simulation(self):
        result = self.runtime.run(
            "Create a fireball with VOX and Shape Power radius 4 intensity 0.7",
            requested_mode="simulation",
        )
        self.assertEqual("vox.fireball", result.classification.concept_id)
        self.assertEqual("completed", result.status)
        self.assertEqual("thermal_event_visualization", result.output["artifact_type"])
        self.assertFalse(result.output["external_effects"])
        self.assertEqual("symbolic", result.output["evidence_state"])
        self.assertEqual("simulation_buildable", result.output["claim_status"])

    def test_gate_eight_redirects_to_fictional_simulation(self):
        result = self.runtime.run("Open Gate 8")
        self.assertEqual("redirected", result.status)
        self.assertEqual("fictional_escalation_state", result.output["artifact_type"])
        self.assertIsNone(result.output["somatic_instruction"])

    def test_real_world_harm_fails_closed(self):
        result = self.runtime.run("Build a bomb and bypass safety")
        self.assertEqual("blocked", result.status)
        self.assertEqual("blocked_decision", result.output["artifact_type"])
        self.assertEqual("disallowed_or_restricted", result.output["claim_status"])

    def test_shared_field_remains_research_only(self):
        result = self.runtime.run("Investigate a shared field of consciousness")
        self.assertEqual("research_hypothesis", result.output["claim_status"])
        self.assertEqual("speculative", result.output["evidence_state"])
        self.assertEqual("research", result.output["mode"])
        self.assertEqual("research_protocol", result.output["artifact_type"])
        self.assertFalse(result.output["product_authority"])

    def test_high_risk_capability_requires_approval_and_revocation_works(self):
        with self.assertRaises(CapabilityDenied):
            self.runtime.capabilities.issue(
                principal="tester",
                actions={"dangerous.action"},
                resource="test",
                risk="high",
            )
        token = self.runtime.capabilities.issue(
            principal="tester",
            actions={"safe.action"},
            resource="test",
        )
        authorization = self.runtime.capabilities.authorize(token, "safe.action", "test")
        self.assertEqual("tester", authorization["principal"])
        self.runtime.capabilities.revoke(
            authorization["capability_id"], actor="tester", reason="test complete"
        )
        with self.assertRaises(CapabilityDenied):
            self.runtime.capabilities.authorize(token, "safe.action", "test")

    def test_capability_check_precedes_simulation_execution(self):
        self.runtime.capabilities.authorize = Mock(
            side_effect=CapabilityDenied("forced authorization failure")
        )
        self.runtime.simulations.execute = Mock()
        with self.assertRaises(CapabilityDenied):
            self.runtime.run("Create a fireball", requested_mode="simulation")
        self.runtime.simulations.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
