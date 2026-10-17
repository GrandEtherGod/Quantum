"""Harm-gate benchmark (fact-check report §8).

Runs LOOM's regex Harm gate (ConceptClassifier) over:
  - the 100 JBB-Behaviors goals (harmful; expected: flagged),
  - a locally-authored benign set (expected: allowed),
  - a locally-authored over-refusal set (expected: allowed).

Reports recall on JBB-100 (overall + per category), false-positive rate on the
benign set, over-refusal rate, and per-prompt latency/throughput. Classifier
only: no model inference, no response generation.

Usage: python3 tools/benchmark_harm_gate.py
Writes verification/harm-gate-benchmark.json
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

TREE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TREE))

from loom_verath.classifier import ConceptClassifier  # noqa: E402
from loom_verath.models import ClaimStatus  # noqa: E402


def main() -> dict:
    fixtures_path = TREE / "verification" / "harm-gate-fixtures.json"
    fixtures = json.loads(fixtures_path.read_text())
    classifier = ConceptClassifier()

    def evaluate(prompt: str) -> tuple[bool, float]:
        started = time.perf_counter()
        classification = classifier.classify(prompt)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        flagged = classification.claim_status is ClaimStatus.RESTRICTED
        return flagged, elapsed_ms

    # Warm up once (regex compilation etc.).
    evaluate("warm up the classifier")

    results: dict[str, list] = {"harmful": [], "benign": [], "over_refusal": []}
    latencies: list[float] = []

    for entry in fixtures["harmful_jbb100"]:
        flagged, elapsed = evaluate(entry["prompt"])
        latencies.append(elapsed)
        results["harmful"].append(
            {
                "index": entry["index"],
                "behavior": entry["behavior"],
                "category": entry["category"],
                "flagged": flagged,
            }
        )
    for entry in fixtures["benign"]:
        flagged, elapsed = evaluate(entry["prompt"])
        latencies.append(elapsed)
        results["benign"].append({"prompt": entry["prompt"], "flagged": flagged})
    for entry in fixtures["over_refusal"]:
        flagged, elapsed = evaluate(entry["prompt"])
        latencies.append(elapsed)
        results["over_refusal"].append({"prompt": entry["prompt"], "flagged": flagged})

    harmful = results["harmful"]
    recall = sum(1 for r in harmful if r["flagged"]) / len(harmful)
    categories: dict[str, dict[str, int]] = {}
    for record in harmful:
        bucket = categories.setdefault(record["category"], {"flagged": 0, "total": 0})
        bucket["total"] += 1
        bucket["flagged"] += int(record["flagged"])
    per_category = {
        name: {"recall": round(b["flagged"] / b["total"], 4), "flagged": b["flagged"], "total": b["total"]}
        for name, b in sorted(categories.items())
    }
    missed = [
        {"index": r["index"], "behavior": r["behavior"]}
        for r in harmful
        if not r["flagged"]
    ]
    benign_fp = sum(1 for r in results["benign"] if r["flagged"])
    over_refused = sum(1 for r in results["over_refusal"] if r["flagged"])

    ordered = sorted(latencies)
    report = {
        "gate": "ConceptClassifier regex harm patterns (claim_status == RESTRICTED)",
        "fixtures": str(fixtures_path),
        "n_harmful": len(harmful),
        "n_benign": len(results["benign"]),
        "n_over_refusal": len(results["over_refusal"]),
        "recall_jbb100": round(recall, 4),
        "flagged_jbb100": sum(1 for r in harmful if r["flagged"]),
        "per_category_recall": per_category,
        "false_positive_rate_benign": round(benign_fp / len(results["benign"]), 4),
        "over_refusal_rate": round(over_refused / len(results["over_refusal"]), 4),
        "latency_ms": {
            "median": round(statistics.median(ordered), 4),
            "p95": round(ordered[int(0.95 * len(ordered)) - 1], 4),
            "max": round(ordered[-1], 4),
        },
        "throughput_prompts_per_sec": round(1000.0 / statistics.median(ordered), 1),
        "missed_behaviors": missed,
        "false_positives_benign": [r["prompt"] for r in results["benign"] if r["flagged"]],
        "over_refused_prompts": [r["prompt"] for r in results["over_refusal"] if r["flagged"]],
        "interpretation": (
            "Regex/registry gate only. Recall is bounded by the fixed pattern list; "
            "paraphrase, multilingual, obfuscation and indirect-injection robustness "
            "are NOT measured here. Compare against Llama Guard 4 / WildGuard before "
            "claiming robustness (report §8)."
        ),
    }
    out_path = TREE / "verification" / "harm-gate-benchmark.json"
    out_path.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in {"missed_behaviors", "false_positives_benign", "over_refused_prompts"}}, indent=2))
    print(f"\nwrote {out_path}")
    return report


if __name__ == "__main__":
    main()
