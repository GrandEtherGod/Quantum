import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from loom_verath import LoomVerathRuntime
from loom_verath.bionemo import BioNeMoResearch, protein_request, validate_response, validate_protein_request
from loom_verath.build_pipeline import MechanicBuild
from loom_verath.mechanics import VoxParser, JintaiHands, tesseract_geometry


class MechanicTests(unittest.TestCase):
    def test_hand_event_requires_confidence_and_finite_values(self):
        for value in (0.84, 1.1, math.nan, math.inf, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                JintaiHands.parse({"gesture": "open_palm", "confidence": value, "radius": 4})

    def test_voice_grammar_rejects_unbounded_or_injected_input(self):
        for text in ("dome radius -1", "dome radius 101", "fireball; rm -rf /", "open Gate 8", "dome radius nan"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                VoxParser.parse(text)

    def test_tesseract_edges_are_four_regular(self):
        geometry = tesseract_geometry(4)
        self.assertEqual(16, len(geometry["vertices_4d"]))
        self.assertEqual(32, len(geometry["edges"]))
        for vertex in range(16):
            self.assertEqual(4, sum(vertex in edge for edge in geometry["edges"]))
        self.assertEqual(geometry, tesseract_geometry(4))
        self.assertFalse(geometry["actuator_used"])


class BioNeMoAndStagesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = LoomVerathRuntime(self.temp.name)
        self.bio = BioNeMoResearch(self.runtime)

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    @staticmethod
    def fixture():
        # Deliberately minimal protocol fixture, not a predicted biological structure.
        return {"structures": [{"format": "mmcif", "structure": "data_protocol_fixture\n_atom_site.id 1\n"}], "confidence_scores": [0.5]}

    def test_sequence_and_profile_validation(self):
        for seq in ("", "acde", "ABCD", "A" * 4097, "AC DE", None):
            with self.subTest(seq=str(seq)[:20]), self.assertRaises(ValueError):
                protein_request(seq)
        payload = protein_request("ACDE")
        payload["polymers"].append({"id": "B", "molecule_type": "protein", "sequence": "ACDE"})
        with self.assertRaises(ValueError):
            validate_protein_request(payload)

    def test_prepare_does_not_call_network_or_log_sequence(self):
        sequence = "MTEYKLVVVGACGVGKSALTIQLIQNHFVDEYDPT"
        with patch("loom_verath.bionemo._post") as network:
            result = self.bio.prepare(sequence)
            network.assert_not_called()
        self.assertFalse(result["inference_run"])
        self.assertNotIn(sequence, json.dumps(self.runtime.ledger.all_events()))

    def test_network_opt_in_is_required_even_with_key(self):
        with patch.dict(os.environ, {"NGC_API_KEY": "protocol-test-key"}), patch("loom_verath.bionemo._post") as network:
            with self.assertRaises(ValueError):
                self.bio.predict(protein_request("ACDE"))
            network.assert_not_called()

    def test_missing_credential_blocks_before_network(self):
        with patch.dict(os.environ, {}, clear=True), patch("loom_verath.bionemo._post") as network:
            with self.assertRaises(ValueError):
                self.bio.predict(protein_request("ACDE"), allow_network=True)
            network.assert_not_called()

    def test_protocol_success_saves_all_structures_and_revokes_capability(self):
        with patch.dict(os.environ, {"NGC_API_KEY": "protocol-test-key"}), patch("loom_verath.bionemo._post", return_value=self.fixture()):
            result = self.bio.predict(protein_request("ACDE"), allow_network=True)
        self.assertFalse(result["product_authority"])
        self.assertEqual("research_only", result["authority"])
        self.assertEqual("predicted_unreviewed", result["status"])
        path = Path(result["structures"][0]["path"])
        self.assertTrue(path.exists())
        self.assertEqual(0o600, path.stat().st_mode & 0o777)
        self.assertTrue(Path(result["raw_response_path"]).exists())
        rows = self.runtime.database.connection.execute("SELECT revoked_at FROM capabilities WHERE principal='bionemo-research'").fetchall()
        self.assertTrue(all(r["revoked_at"] for r in rows))
        self.assertNotIn("protocol-test-key", json.dumps(self.runtime.ledger.all_events()))
        self.assertTrue(self.runtime.verify()["valid"])

    def test_failed_provider_revokes_and_creates_no_output(self):
        with patch.dict(os.environ, {"NGC_API_KEY": "protocol-test-key"}), patch("loom_verath.bionemo._post", side_effect=ValueError("failed")):
            with self.assertRaises(ValueError):
                self.bio.predict(protein_request("ACDE"), allow_network=True)
        self.assertFalse((self.runtime.data_dir / "bionemo").exists())
        events = self.runtime.ledger.all_events()
        self.assertTrue(any(e["event_type"] == "bionemo_prediction_failed" for e in events))
        self.assertEqual("capability_revoked", events[-1]["event_type"])

    def test_malformed_provider_response_is_rejected(self):
        for response in ({}, {"structures": []}, {"structures": [{"format": "mmcif", "structure": "data_no_atoms"}], "confidence_scores": [0.5]},
                         self.fixture() | {"confidence_scores": [math.nan]}, self.fixture() | {"confidence_scores": [True]}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                validate_response(response)

    def test_full_local_stages_pass_but_design_is_incomplete(self):
        with patch("loom_verath.bionemo._post") as network:
            result = MechanicBuild(self.runtime).run()
            network.assert_not_called()
        states = {r["stage"]: r["status"] for r in result["stages"]}
        self.assertTrue(result["local_acceptance_passed"])
        self.assertFalse(result["entire_design_complete"])
        self.assertEqual(result, json.loads(Path(result["report_path"]).read_text()))
        self.assertEqual(7, list(states.values()).count("passed"))
        self.assertEqual("blocked", states["bio_live"])
        self.assertEqual("blocked", states["bio_validation"])
        self.assertTrue(self.runtime.verify()["valid"])

    def test_failed_stage_blocks_dependent_mechanics(self):
        build = MechanicBuild(self.runtime)
        check = build._check
        def failure(name, run_id):
            if name == "vox":
                raise ValueError("injected failure")
            return check(name, run_id)
        with patch.object(build, "_check", side_effect=failure):
            result = build.run()
        states = {r["stage"]: r["status"] for r in result["stages"]}
        self.assertFalse(result["local_acceptance_passed"])
        self.assertEqual("failed", states["vox"])
        self.assertEqual("blocked", states["hands"])
        self.assertEqual("blocked", states["witness"])

    def test_prefix_and_unknown_stage(self):
        build = MechanicBuild(self.runtime)
        with self.assertRaises(ValueError):
            build.run(through="missing")
        result = build.run(through="memory")
        self.assertEqual(["passed", "passed"], [r["status"] for r in result["stages"][:2]])
        self.assertTrue(all(r["status"] == "pending" for r in result["stages"][2:]))


if __name__ == "__main__":
    unittest.main()
