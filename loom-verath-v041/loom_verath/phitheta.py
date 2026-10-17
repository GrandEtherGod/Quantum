from __future__ import annotations

from .models import (
    BridgeTranslation,
    Candidate,
    Classification,
    Decision,
    EvidenceState,
    GateDecision,
    Lane,
)


EVIDENCE_SCORES = {
    EvidenceState.VERIFIED: 0.95,
    EvidenceState.SUPPORTED: 0.82,
    EvidenceState.PLAUSIBLE: 0.68,
    EvidenceState.SPECULATIVE: 0.35,
    EvidenceState.SYMBOLIC: 0.25,
}

RISK_SCORES = {"low": 0.1, "medium": 0.35, "high": 0.7, "critical": 1.0}


class PhiThetaEngine:
    """Phi generates bounded alternatives; Theta ranks admissible candidates."""

    def diverge(
        self, classification: Classification, bridge: BridgeTranslation
    ) -> list[Candidate]:
        evidence = EVIDENCE_SCORES[classification.evidence_state]
        if bridge.approved:
            execution_evidence = max(evidence, 0.8)
        elif bridge.execution_mode == "research":
            execution_evidence = max(evidence, 0.65)
        else:
            execution_evidence = evidence
        risk = RISK_SCORES.get(classification.risk, 0.5)
        primary = Candidate(
            candidate_id="phi-primary",
            action=bridge.engineering_action,
            mode=bridge.execution_mode,
            evidence=execution_evidence,
            coherence=0.9,
            risk=(
                0.2
                if bridge.execution_mode == "simulation" and bridge.approved
                else 0.1
                if bridge.execution_mode == "research"
                else risk
            ),
            utility=0.9,
            reversibility=1.0 if bridge.execution_mode in {"analysis", "simulation", "research"} else 0.8,
            summary="Execute the approved engineering translation within its declared boundary.",
        )
        analysis = Candidate(
            candidate_id="phi-analysis",
            action="Return a bounded analysis with explicit evidence and claim labels.",
            mode="analysis",
            evidence=max(evidence, 0.7),
            coherence=0.82,
            risk=0.05,
            utility=0.65,
            reversibility=1.0,
            summary="Explain the concept, boundary, and next buildable step without external effects.",
        )
        candidates = [primary, analysis]
        if classification.lane is not Lane.FORGE:
            candidates.append(
                Candidate(
                    candidate_id="phi-research",
                    action="Define a falsifiable research or simulation protocol with negative controls.",
                    mode="research",
                    evidence=0.55,
                    coherence=0.78,
                    risk=0.08,
                    utility=0.7,
                    reversibility=1.0,
                    summary="Preserve the symbolic source while translating it into a testable hypothesis.",
                )
            )
        return candidates

    @staticmethod
    def converge(
        candidates: list[Candidate], decisions: dict[str, GateDecision]
    ) -> Candidate | None:
        admissible = [
            candidate
            for candidate in candidates
            if decisions[candidate.candidate_id].decision is not Decision.BLOCK
        ]
        if not admissible:
            return None
        return max(admissible, key=lambda candidate: (candidate.score, candidate.candidate_id))
