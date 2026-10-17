from __future__ import annotations

from .models import (
    BridgeTranslation,
    ClaimStatus,
    Classification,
    Decision,
    GateDecision,
    GateResult,
    Lane,
)


class FourGates:
    """Truth, autonomy, harm, and integrity gates; all fail closed."""

    SAFE_MODES = {"analysis", "build", "memory", "simulation", "research"}

    def evaluate(
        self,
        classification: Classification,
        bridge: BridgeTranslation,
        *,
        user_approved: bool,
        reversible: bool = True,
    ) -> GateDecision:
        mode = bridge.execution_mode
        truth_passed = not (
            classification.real_world_requested
            and classification.claim_status
            in {ClaimStatus.RESTRICTED, ClaimStatus.RESEARCH, ClaimStatus.SPECULATIVE}
            and mode not in {"simulation", "research"}
        )
        truth = GateResult(
            "truth",
            truth_passed,
            "Claim and evidence labels are explicit."
            if truth_passed
            else "An unverified or symbolic mechanism cannot be presented as real-world capability.",
        )

        autonomy_passed = mode != "actuate"
        autonomy = GateResult(
            "autonomy",
            autonomy_passed,
            "No external actuation or third-party decision is requested."
            if autonomy_passed
            else "External actuation is outside the authorized boundary.",
        )

        harmful_without_bridge = (
            classification.claim_status is ClaimStatus.RESTRICTED
            and (not bridge.approved or mode != "simulation")
        )
        harm_passed = not harmful_without_bridge
        harm = GateResult(
            "harm",
            harm_passed,
            "The operation is bounded to benign software, analysis, research, or simulation."
            if harm_passed
            else "The request is harmful or restricted and has no approved safe simulation bridge.",
        )

        bridge_required = classification.lane is Lane.BRIDGE and mode in {"build", "simulation"}
        integrity_passed = (
            mode in self.SAFE_MODES
            and reversible
            and (not bridge_required or bridge.approved)
        )
        integrity = GateResult(
            "integrity",
            integrity_passed,
            "The action is reversible, versioned, logged, and admitted by policy."
            if integrity_passed
            else "The action is not reversible, not admitted, or lacks an approved bridge contract.",
        )

        results = (truth, autonomy, harm, integrity)
        if not all(item.passed for item in results):
            decision = Decision.BLOCK
        elif classification.real_world_requested or classification.claim_status is ClaimStatus.RESTRICTED:
            decision = Decision.REDIRECT
        else:
            decision = Decision.ALLOW
        return GateDecision(decision=decision, results=results, enforced_mode=mode)

    @staticmethod
    def output_check(output: dict) -> GateResult:
        required = {"claim_status", "evidence_state", "mode"}
        missing = required - set(output)
        return GateResult(
            "output_boundary",
            not missing,
            "Output includes epistemic and execution labels."
            if not missing
            else f"Output is missing required labels: {sorted(missing)}",
        )

