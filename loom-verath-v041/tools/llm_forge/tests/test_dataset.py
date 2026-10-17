from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_dataset", ROOT / "build_dataset.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = MODULE.build_records()
        cls.train, cls.validation = MODULE.split_records(cls.records)

    def test_expected_size(self):
        self.assertGreaterEqual(len(self.records), 110)

    def test_unique_ids_and_prompts(self):
        ids = [item["id"] for item in self.records]
        prompts = [item["messages"][1]["content"].strip().lower() for item in self.records]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(prompts), len(set(prompts)))

    def test_conversational_schema(self):
        for item in self.records:
            self.assertEqual([m["role"] for m in item["messages"]], ["system", "user", "assistant"])
            self.assertTrue(all(m["content"].strip() for m in item["messages"]))

    def test_split_has_no_overlap(self):
        train_ids = {item["id"] for item in self.train}
        validation_ids = {item["id"] for item in self.validation}
        self.assertFalse(train_ids & validation_ids)
        self.assertEqual(len(train_ids | validation_ids), len(self.records))

    def test_all_28_layers_covered_twice(self):
        ids = {item["id"] for item in self.records}
        for number in range(28):
            self.assertIn(f"layer-{number:02d}-explain", ids)
            self.assertIn(f"layer-{number:02d}-reverse", ids)

    def test_all_invariants_and_axioms_covered(self):
        ids = {item["id"] for item in self.records}
        for number in range(1, 7):
            self.assertIn(f"invariant-i{number}-design", ids)
            self.assertIn(f"invariant-i{number}-audit", ids)
        for number in range(1, 13):
            self.assertIn(f"axiom-a{number}", ids)

    def test_calibration_examples_present(self):
        assistant_text = "\n".join(item["messages"][2]["content"].lower() for item in self.records)
        for expected in ["tamper-evident", "no verified non-local resonance", "emergency stop", "not necessarily to one", "one arbitrary qubit error"]:
            self.assertIn(expected, assistant_text)


if __name__ == "__main__":
    unittest.main()
