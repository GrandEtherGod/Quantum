from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Lane(StrEnum):
    FORGE = "FORGE"
    TEMPLE = "TEMPLE"
    BRIDGE = "BRIDGE"


class EvidenceState(StrEnum):
    VERIFIED = "verified"
    SUPPORTED = "supported"
    PLAUSIBLE = "plausible"
    SPECULATIVE = "speculative"
    SYMBOLIC = "symbolic"


class ClaimStatus(StrEnum):
    BUILDABLE = "buildable_now"
    SIMULATION = "simulation_buildable"
    RESEARCH = "research_hypothesis"
    SPECULATIVE = "speculative_symbolic"
    FICTIONAL = "fictional_mythic"
    RESTRICTED = "disallowed_or_restricted"


class Decision(StrEnum):
    ALLOW = "allow"
    REDIRECT = "redirect"
    BLOCK = "block"


@dataclass(frozen=True)
class Classification:
    concept_id: str
    mythic_name: str
    lane: Lane
    evidence_state: EvidenceState
    claim_status: ClaimStatus
    engineering_translation: str
    contract_id: str | None
    confidence: float
    risk: str
    real_world_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["lane"] = self.lane.value
        value["evidence_state"] = self.evidence_state.value
        value["claim_status"] = self.claim_status.value
        return value


@dataclass(frozen=True)
class BridgeTranslation:
    contract_id: str | None
    approved: bool
    engineering_action: str
    execution_mode: str
    claim_label: str
    safety_gate: str
    fallback: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GateResult:
    gate: str
    passed: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GateDecision:
    decision: Decision
    results: tuple[GateResult, ...]
    enforced_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "results": [item.to_dict() for item in self.results],
            "enforced_mode": self.enforced_mode,
        }


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    action: str
    mode: str
    evidence: float
    coherence: float
    risk: float
    utility: float
    reversibility: float
    summary: str

    @property
    def score(self) -> float:
        raw = (
            self.evidence * 0.25
            + self.coherence * 0.20
            + (1.0 - self.risk) * 0.25
            + self.utility * 0.20
            + self.reversibility * 0.10
        )
        return round(raw, 6)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "score": self.score}


@dataclass
class RuntimeResult:
    session_id: str
    status: str
    classification: Classification
    bridge: BridgeTranslation
    gates: GateDecision
    candidates: list[Candidate]
    selected_candidate_id: str | None
    output: dict[str, Any]
    ledger_hash: str
    lineage_hash: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "classification": self.classification.to_dict(),
            "bridge": self.bridge.to_dict(),
            "gates": self.gates.to_dict(),
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "selected_candidate_id": self.selected_candidate_id,
            "output": self.output,
            "ledger_hash": self.ledger_hash,
            "lineage_hash": self.lineage_hash,
            "warnings": self.warnings,
        }

