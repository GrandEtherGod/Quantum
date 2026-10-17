from __future__ import annotations

from pathlib import Path
from typing import Any

from .harm_gate import HarmGate
from .models import ClaimStatus, Classification, EvidenceState, Lane
from .utils import load_json


REAL_WORLD_MARKERS = (
    "in real life",
    "in the real world",
    "physical effect",
    "actually injure",
    "actually harm",
    "make it real",
    "real weapon",
    "bypass safety",
)

HARM_PATTERNS = (
    r"\bbuild\b.{0,30}\b(?:bomb|weapon|explosive)\b",
    r"\b(?:injure|kill|poison|sabotage|coerce)\b",
    r"\bbypass\b.{0,30}\b(?:guardrail|safety|authorization)\b",
)


class ConceptClassifier:
    def __init__(self, config_dir: Path | None = None, *, harm_gate: HarmGate | None = None):
        config_dir = config_dir or Path(__file__).parent / "config"
        self.rules: list[dict[str, Any]] = load_json(config_dir / "concepts.json")
        # Default gate (no judge) reproduces the original regex-only check.
        self.harm_gate = harm_gate if harm_gate is not None else HarmGate(HARM_PATTERNS)
        self.last_harm_result = None

    def classify(self, text: str) -> Classification:
        normalized = " ".join(text.lower().split())
        real_world_requested = any(marker in normalized for marker in REAL_WORLD_MARKERS)
        harm_result = self.harm_gate.classify_flag(text)
        self.last_harm_result = harm_result
        if harm_result.flagged:
            return Classification(
                concept_id="restricted.real_world_harm",
                mythic_name="Restricted Real-World Harm",
                lane=Lane.BRIDGE,
                evidence_state=EvidenceState.VERIFIED,
                claim_status=ClaimStatus.RESTRICTED,
                engineering_translation="No harmful execution. Offer benign analysis or an abstract safety simulation only.",
                contract_id=None,
                confidence=0.99,
                risk="critical",
                real_world_requested=True,
            )

        best_rule: dict[str, Any] | None = None
        best_score = -1
        for rule in self.rules:
            for alias in rule["aliases"]:
                score = int(rule.get("priority", 0)) * 1000 + len(alias)
                if alias in normalized and score > best_score:
                    best_rule = rule
                    best_score = score
        if best_rule is None:
            best_rule = {
                "concept_id": "loom.general_analysis",
                "mythic_name": "LOOM General Analysis",
                "lane": "FORGE",
                "evidence_state": "supported",
                "claim_status": "buildable_now",
                "engineering_translation": "Perform a bounded analysis and return a provenance-labeled result.",
                "contract_id": None,
                "risk": "low",
            }

        claim_status = ClaimStatus(best_rule["claim_status"])
        if real_world_requested and claim_status in {
            ClaimStatus.SIMULATION,
            ClaimStatus.RESEARCH,
            ClaimStatus.SPECULATIVE,
            ClaimStatus.FICTIONAL,
        }:
            claim_status = ClaimStatus.RESTRICTED
        return Classification(
            concept_id=best_rule["concept_id"],
            mythic_name=best_rule["mythic_name"],
            lane=Lane(best_rule["lane"]),
            evidence_state=EvidenceState(best_rule["evidence_state"]),
            claim_status=claim_status,
            engineering_translation=best_rule["engineering_translation"],
            contract_id=best_rule.get("contract_id"),
            confidence=0.96 if best_score >= 0 else 0.75,
            risk="high" if real_world_requested else best_rule["risk"],
            real_world_requested=real_world_requested,
        )
