import json
import tempfile
import unittest
import uuid
from pathlib import Path

from loom_verath import LoomVerathRuntime
from loom_verath.codepet import CodePetWorkspace
from loom_verath.research import ResearchValidationError
from loom_verath.site_guide import SiteGuide


def valid_research_record() -> dict:
    return {
        "record_id": str(uuid.uuid4()),
        "experiment_id": "experiment-001",
        "created_at_utc": "2026-09-01T00:00:00Z",
        "circuit_hash_sha256": "a" * 64,
        "gate_count": 4,
        "circuit_depth": 3,
        "qubit_count": 2,
        "shots": 100,
        "counts": {"00": 51, "11": 49},
        "probabilities": {"00": 0.51, "11": 0.49},
        "provider": "local",
        "backend": "fixture",
        "simulator_or_hardware": "simulator",
        "status": "completed",
        "review_status": "unreviewed",
    }


class IntegratedLayerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = LoomVerathRuntime(self.root / "runtime")

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def test_all_28_layers_have_explicit_authority(self):
        registry = self.runtime.layers.to_dict()
        self.assertEqual(28, registry["summary"]["total"])
        self.assertEqual(list(range(28)), [item["layer"] for item in registry["layers"]])
        self.assertEqual("research_only", self.runtime.layers.get(15)["status"])
        self.assertEqual("forge_only", registry["summary"]["runtime_authority"])

    def test_zpe_cannot_become_runtime_power_authority(self):
        result = self.runtime.run("Power the system forever with ZPE thermodynamic severance")
        self.assertEqual("research.zpe_severance", result.classification.concept_id)
        self.assertEqual("research", result.output["mode"])
        self.assertFalse(result.bridge.approved)

    def test_h_field_validation_and_ingestion_remain_research_only(self):
        record = valid_research_record()
        path = self.root / "record.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        result = self.runtime.research.ingest_file(path, actor="tester")
        self.assertTrue(result["valid"])
        self.assertEqual("research_only", result["authority"])
        self.assertEqual(1, self.runtime.research.count())
        self.assertEqual("research_record_ingested", self.runtime.ledger.all_events()[-1]["event_type"])

    def test_h_field_rejects_post_hoc_score_without_null_model(self):
        record = valid_research_record()
        record["synchronicity_score"] = 0.99
        with self.assertRaises(ResearchValidationError):
            self.runtime.research.validate(record)

    def test_codepet_is_file_native_and_review_gated(self):
        workspace = self.root / "project"
        workspace.mkdir()
        (workspace / "main.py").write_text("print('hello')\n", encoding="utf-8")
        pet = CodePetWorkspace(workspace)
        initialized = pet.initialize()
        proposal = pet.propose("Add a greeting function")
        self.assertEqual("review_gated", initialized["mode"])
        self.assertEqual("awaiting_review", proposal["state"])
        self.assertFalse(proposal["authority"]["write"])
        self.assertTrue((workspace / ".codepet" / "observations" / "workspace_manifest.json").exists())

    def test_site_guide_requires_consent_and_exports_no_answers(self):
        guide = SiteGuide()
        with self.assertRaises(ValueError):
            guide.questionnaire("field", consent=False)
        questions = guide.questionnaire("field", consent=True)
        self.assertEqual(3, len(questions["questions"]))
        exported = self.root / "field.txt"
        guide.export("field", exported)
        text = exported.read_text(encoding="utf-8")
        self.assertIn("Evidence status: Research hypothesis", text)
        self.assertIn("no visitor responses", text)


if __name__ == "__main__":
    unittest.main()
