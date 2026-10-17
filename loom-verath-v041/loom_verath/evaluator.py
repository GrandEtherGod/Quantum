from __future__ import annotations

from typing import Any

from .errors import InvariantViolation
from .identity import IdentityLineage
from .ledger import ChronoScribeLedger
from .state import StateStore


class OuroborosEvaluator:
    """Eval-gated configuration improvement; never edits its own gate."""

    ALLOWED_KEYS = {
        "system.phi_coupling",
        "system.ethics_lambda",
        "system.max_recursion",
        "system.guardrail_revision",
        "memory.consolidation_threshold",
    }
    STRUCTURAL_KEYS = {"system.max_recursion", "system.guardrail_revision"}

    def __init__(
        self,
        state: StateStore,
        ledger: ChronoScribeLedger,
        identity: IdentityLineage,
        config_root: str,
    ):
        self.state = state
        self.ledger = ledger
        self.identity = identity
        self.config_root = config_root

    def propose_and_apply(
        self, patch: dict[str, Any], *, actor: str, human_approved: bool = False
    ) -> dict[str, Any]:
        unknown = sorted(set(patch) - self.ALLOWED_KEYS)
        if unknown:
            return {"accepted": False, "applied": False, "reasons": [f"unsupported keys: {unknown}"]}
        structural = sorted(set(patch) & self.STRUCTURAL_KEYS)
        if structural and not human_approved:
            return {
                "accepted": False,
                "applied": False,
                "reasons": [f"human approval required for structural keys: {structural}"],
            }
        reasons: list[str] = []
        for key, value in patch.items():
            current = self.state.value(key)
            try:
                self.state._validate_transition(key, current, value)
            except InvariantViolation as exc:
                reasons.append(str(exc))
        if reasons:
            self.ledger.append(
                "change_proposal_rejected",
                {"keys": sorted(patch), "reasons": reasons},
                actor=actor,
            )
            return {"accepted": False, "applied": False, "reasons": reasons}

        snapshot = self.state.create_snapshot(actor=actor)
        self.ledger.append(
            "change_proposal_accepted",
            {
                "keys": sorted(patch),
                "human_approved": human_approved,
                "rollback_snapshot_id": snapshot["snapshot_id"],
            },
            actor=actor,
        )
        versions: dict[str, int] = {}
        for key, value in patch.items():
            versions[key] = self.state.set(key, value, actor=actor)
        lineage = self.identity.attest(self.config_root, reason="eval_gated_change")
        return {
            "accepted": True,
            "applied": True,
            "versions": versions,
            "rollback_snapshot_id": snapshot["snapshot_id"],
            "lineage_hash": lineage["record_hash"],
        }

