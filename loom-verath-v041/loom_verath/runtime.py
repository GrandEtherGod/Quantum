from __future__ import annotations

import json
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from .bridge import BridgeContractRegistry
from .capabilities import CapabilityBroker
from .checkpoints import LedgerCheckpointer
from .classifier import HARM_PATTERNS, ConceptClassifier
from .db import Database
from .errors import InvariantViolation, ReplayUnavailable
from .evaluator import OuroborosEvaluator
from .four_gates import FourGates
from .harm_gate import HarmGate, ModelHarmJudge
from .identity import IdentityLineage
from .layers import LayerRegistry
from .ledger import ChronoScribeLedger
from .memory import ChrysalisMemory
from .model_loop import ModelCandidateProposer
from .models import BridgeTranslation, Decision, EvidenceState, RuntimeResult
from .phitheta import PhiThetaEngine
from .simulations import SimulationEngine
from .research import HFieldRegistry
from .state import StateStore
from .utils import canonical_json, load_json, sha256_hex
from .version import VERSION


class LoomVerathRuntime:
    """Single-instance trustworthy-core implementation of LOOM × VERATH."""

    def __init__(
        self,
        data_dir: str | Path = ".runtime",
        *,
        model_provider=None,
        model_consent: bool = False,
        harm_judge: ModelHarmJudge | None = None,
    ):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database = Database(self.data_dir / "loom_verath.sqlite3")
        self.ledger = ChronoScribeLedger(self.database)
        self.state = StateStore(self.database, self.ledger)
        self._migrate_runtime_version()
        self.config_dir = Path(__file__).parent / "config"
        self.config_root = self._compute_config_root()
        self.harm_judge = harm_judge
        classifier_kwargs: dict[str, Any] = {}
        if harm_judge is not None:
            classifier_kwargs["harm_gate"] = HarmGate(HARM_PATTERNS, judge=harm_judge)
        self.classifier = ConceptClassifier(self.config_dir, **classifier_kwargs)
        self.bridge_registry = BridgeContractRegistry(self.database, self.config_dir)
        self.layers = LayerRegistry(self.config_dir)
        self.identity = IdentityLineage(
            self.data_dir, self.database, self.state, self.ledger
        )
        self.identity.ensure_baseline(self.config_root)
        self.checkpointer = self._attach_checkpointer()
        self.memory = ChrysalisMemory(self.data_dir, self.database, self.ledger)
        self.gates = FourGates()
        self.phitheta = PhiThetaEngine()
        self.capabilities = CapabilityBroker(self.database, self.ledger)
        self.simulations = SimulationEngine()
        self.research = HFieldRegistry(self.database, self.ledger)
        self._kernel_capability = self.capabilities.issue(
            principal="loom-kernel",
            actions={
                "simulation.execute",
                "analysis.render",
                "memory.search",
                "memory.write",
                "runtime.introspect",
            },
            resource="*",
            ttl_seconds=86400,
            risk="low",
            human_approved=True,
        )
        self.evaluator = OuroborosEvaluator(
            self.state, self.ledger, self.identity, self.config_root
        )
        self._model_consent_given = model_consent
        self.model_proposer = (
            ModelCandidateProposer(model_provider, consent=model_consent)
            if model_provider is not None
            else None
        )

    def _attach_checkpointer(self) -> LedgerCheckpointer:
        """Seal periodic Ed25519-signed ledger checkpoints with the identity key."""
        import base64

        from cryptography.hazmat.primitives import serialization

        public_raw = self.identity.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        checkpointer = LedgerCheckpointer(
            self.database,
            sign=self.identity.private_key.sign,
            public_key_b64=base64.b64encode(public_raw).decode("ascii"),
        )
        self.ledger.set_checkpointer(checkpointer)
        return checkpointer

    @staticmethod
    def _version_tuple(value: str) -> tuple[int, ...]:
        try:
            return tuple(int(part) for part in value.split("."))
        except (AttributeError, ValueError) as exc:
            raise InvariantViolation(f"Invalid stored runtime version: {value!r}") from exc

    def _migrate_runtime_version(self) -> None:
        current = self.state.value("runtime.version")
        if current == VERSION:
            return
        if self._version_tuple(current) > self._version_tuple(VERSION):
            raise InvariantViolation(
                f"Runtime state {current} is newer than executable version {VERSION}"
            )
        self.state.set("runtime.version", VERSION, actor="schema_migration")

    def _compute_config_root(self) -> str:
        config = {
            "concepts": load_json(self.config_dir / "concepts.json"),
            "bridge_contracts": load_json(self.config_dir / "bridge_contracts.json"),
            "layers": load_json(self.config_dir / "layers.json"),
            "codepet_proposal_schema": load_json(self.config_dir / "codepet_proposal.schema.json"),
            "mechanic_stages": load_json(self.config_dir / "mechanic_stages.json"),
            "runtime_version": self.state.value("runtime.version"),
        }
        return sha256_hex(canonical_json(config))

    def _evaluate(
        self,
        text: str,
        *,
        requested_mode: str | None,
        user_approved: bool,
        execute_memory: bool,
        enforce_capability: bool,
        allow_model: bool = False,
    ) -> dict[str, Any]:
        classification = self.classifier.classify(text)
        bridge = self.bridge_registry.translate(
            classification, requested_mode=requested_mode
        )
        candidates = self.phitheta.diverge(classification, bridge)
        model_record: dict[str, Any] | None = None
        if allow_model and self.model_proposer is not None:
            model_candidates, model_record = self.model_proposer.propose(
                text, classification, bridge, candidates
            )
            candidates = candidates + model_candidates
        decisions = {}
        for candidate in candidates:
            candidate_bridge = replace(bridge, execution_mode=candidate.mode)
            decisions[candidate.candidate_id] = self.gates.evaluate(
                classification,
                candidate_bridge,
                user_approved=user_approved,
                reversible=True,
            )
        selected = self.phitheta.converge(candidates, decisions)
        if selected is None:
            primary_decision = decisions[candidates[0].candidate_id]
            output = {
                "artifact_type": "blocked_decision",
                "reason": "All candidate actions failed one or more safety gates.",
                "fallback": bridge.fallback,
                "claim_status": classification.claim_status.value,
                "evidence_state": classification.evidence_state.value,
                "lane": classification.lane.value,
                "mode": "blocked",
                "contract_id": bridge.contract_id,
            }
            output["artifact_hash"] = sha256_hex(canonical_json(output))
            return {
                "classification": classification,
                "bridge": bridge,
                "candidates": candidates,
                "decisions": decisions,
                "selected": None,
                "selected_bridge": bridge,
                "gates": primary_decision,
                "output": output,
                "authorization": None,
                "model_record": model_record,
            }

        selected_bridge = replace(
            bridge,
            execution_mode=selected.mode,
            engineering_action=(
                bridge.engineering_action
                if selected.candidate_id == "phi-primary"
                else selected.action
            ),
        )
        decision = decisions[selected.candidate_id]
        lowered = text.lower()
        if classification.concept_id == "chrysalis.memory" and "crystallize" in lowered:
            capability_action, capability_resource = "memory.write", "memory"
        elif classification.concept_id == "chrysalis.memory" and (
            "retrieve" in lowered or "remember" in lowered
        ):
            capability_action, capability_resource = "memory.search", "memory"
        elif selected_bridge.execution_mode == "simulation":
            capability_action, capability_resource = "simulation.execute", "simulation"
        else:
            capability_action, capability_resource = "analysis.render", "analysis"
        authorization = (
            self.capabilities.authorize(
                self._kernel_capability, capability_action, capability_resource
            )
            if enforce_capability
            else None
        )
        if classification.concept_id == "chrysalis.memory" and execute_memory:
            if "crystallize" in lowered:
                artifact = self.memory.consolidate(
                    threshold=float(self.state.value("memory.consolidation_threshold"))
                )
                artifact = {"artifact_type": "memory_consolidation", **artifact}
                selected_bridge = replace(selected_bridge, execution_mode="memory")
            elif "retrieve" in lowered or "remember" in lowered:
                artifact = {
                    "artifact_type": "memory_search",
                    "results": self.memory.search(text, limit=5),
                }
                selected_bridge = replace(selected_bridge, execution_mode="memory")
            else:
                artifact = self.simulations.execute(
                    text, classification, selected_bridge, selected.mode
                )
        else:
            artifact = self.simulations.execute(
                text, classification, selected_bridge, selected.mode
            )
        output = {
            **artifact,
            "claim_status": classification.claim_status.value,
            "evidence_state": classification.evidence_state.value,
            "lane": classification.lane.value,
            "mode": selected_bridge.execution_mode,
            "contract_id": selected_bridge.contract_id,
        }
        output["artifact_hash"] = sha256_hex(
            canonical_json({key: value for key, value in output.items() if key != "artifact_hash"})
        )
        return {
            "classification": classification,
            "bridge": bridge,
            "candidates": candidates,
            "decisions": decisions,
            "selected": selected,
            "selected_bridge": selected_bridge,
            "gates": decision,
            "output": output,
            "authorization": authorization,
            "model_record": model_record,
        }

    def run(
        self,
        text: str,
        *,
        actor: str = "founder",
        requested_mode: str | None = None,
        user_approved: bool = False,
        importance: float = 0.7,
    ) -> RuntimeResult:
        if not text or not text.strip():
            self.ledger.append(
                "input_rejected",
                {"reason": "empty_input"},
                actor=actor,
            )
            raise ValueError("Input cannot be empty.")
        session_id = str(uuid.uuid4())
        command_event = self.ledger.append(
            "command_received",
            {
                "input_hash": sha256_hex(text),
                "input_length": len(text),
                "requested_mode": requested_mode,
                "user_approved": user_approved,
            },
            session_id=session_id,
            actor=actor,
        )
        episode_id = self.memory.add_episode(
            text,
            session_id=session_id,
            kind="command",
            importance=importance,
            evidence_state=EvidenceState.SUPPORTED,
            actor=actor,
        )
        evaluated = self._evaluate(
            text,
            requested_mode=requested_mode,
            user_approved=user_approved,
            execute_memory=True,
            enforce_capability=True,
            allow_model=True,
        )
        classification = evaluated["classification"]
        bridge = evaluated["bridge"]
        candidates = evaluated["candidates"]
        decisions = evaluated["decisions"]
        selected = evaluated["selected"]
        selected_bridge: BridgeTranslation = evaluated["selected_bridge"]
        gate_decision = evaluated["gates"]
        output = evaluated["output"]
        authorization = evaluated["authorization"]

        self.ledger.append(
            "claim_classified",
            classification.to_dict(),
            session_id=session_id,
            actor="classifier",
        )
        self.ledger.append(
            "bridge_translation",
            bridge.to_dict(),
            session_id=session_id,
            actor="bridge",
        )
        self.ledger.append(
            "phitheta_evaluated",
            {
                "candidates": [candidate.to_dict() for candidate in candidates],
                "gate_decisions": {
                    candidate_id: decision.to_dict()
                    for candidate_id, decision in decisions.items()
                },
                "selected_candidate_id": selected.candidate_id if selected else None,
            },
            session_id=session_id,
            actor="phitheta",
        )
        if evaluated["model_record"] is not None:
            self.ledger.append(
                "model_proposal",
                evaluated["model_record"],
                session_id=session_id,
                actor="model_loop",
            )

        if selected is not None and authorization is not None:
            self.ledger.append(
                "capability_authorized",
                authorization,
                session_id=session_id,
                actor="capability_broker",
            )

        output_gate = self.gates.output_check(output)
        if not output_gate.passed:
            output = {
                "artifact_type": "blocked_output",
                "reason": output_gate.rationale,
                "claim_status": classification.claim_status.value,
                "evidence_state": classification.evidence_state.value,
                "lane": classification.lane.value,
                "mode": "blocked",
                "contract_id": selected_bridge.contract_id,
            }
            output["artifact_hash"] = sha256_hex(canonical_json(output))

        status = (
            "blocked"
            if selected is None or gate_decision.decision is Decision.BLOCK
            else "redirected"
            if gate_decision.decision is Decision.REDIRECT
            else "completed"
        )
        output_hash = sha256_hex(canonical_json(output))
        action_event = self.ledger.append(
            "action_completed" if status != "blocked" else "action_blocked",
            {
                "status": status,
                "episode_id": episode_id,
                "command_event_id": command_event["event_id"],
                "selected_candidate_id": selected.candidate_id if selected else None,
                "mode": output["mode"],
                "output_hash": output_hash,
                "output_gate": output_gate.to_dict(),
            },
            session_id=session_id,
            actor="runtime",
        )
        lineage = self.identity.attest(
            self.config_root, reason=f"session:{session_id}:{status}"
        )
        completion = self.ledger.append(
            "runtime_completed",
            {
                "status": status,
                "action_event_hash": action_event["event_hash"],
                "lineage_hash": lineage["record_hash"],
                "output_hash": output_hash,
            },
            session_id=session_id,
            actor="runtime",
        )
        return RuntimeResult(
            session_id=session_id,
            status=status,
            classification=classification,
            bridge=bridge,
            gates=gate_decision,
            candidates=candidates,
            selected_candidate_id=selected.candidate_id if selected else None,
            output=output,
            ledger_hash=completion["event_hash"],
            lineage_hash=lineage["record_hash"],
        )

    def replay(self, session_id: str) -> dict[str, Any]:
        events = self.ledger.events_for_session(session_id)
        if not events:
            raise ReplayUnavailable(f"No ledger events exist for session {session_id}.")
        command = self.memory.command_for_session(session_id)
        if command is None:
            raise ReplayUnavailable("The encrypted command episode is unavailable or was deleted.")
        command_event = next(
            (event for event in events if event["event_type"] == "command_received"), None
        )
        action_event = next(
            (
                event
                for event in events
                if event["event_type"] in {"action_completed", "action_blocked"}
            ),
            None,
        )
        if command_event is None or action_event is None:
            raise ReplayUnavailable("The session is missing required command or action events.")
        evaluated = self._evaluate(
            command,
            requested_mode=command_event["payload"].get("requested_mode"),
            user_approved=bool(command_event["payload"].get("user_approved")),
            execute_memory=False,
            enforce_capability=False,
            allow_model=False,
        )
        mode = action_event["payload"]["mode"]
        model_selected = str(
            action_event["payload"].get("selected_candidate_id") or ""
        ).startswith("model-")
        deterministic = (mode not in {"memory"}) and not model_selected
        replay_hash = sha256_hex(canonical_json(evaluated["output"])) if deterministic else None
        expected_hash = action_event["payload"]["output_hash"]
        return {
            "session_id": session_id,
            "ledger_chain_valid": self.ledger.verify()["valid"],
            "event_sequence": [event["event_type"] for event in events],
            "deterministic": deterministic,
            "model_selected": model_selected,
            "expected_output_hash": expected_hash,
            "replayed_output_hash": replay_hash,
            "output_match": replay_hash == expected_hash if deterministic else None,
            "replayed_output": evaluated["output"] if deterministic else None,
        }

    def verify(self) -> dict[str, Any]:
        ledger = self.ledger.verify()
        lineage = self.identity.verify()
        state = self.state.assert_invariants()
        sqlite_check = self.database.connection.execute("PRAGMA integrity_check").fetchone()[0]
        database_schema = self.database.schema_version()
        return {
            "valid": ledger["valid"] and lineage["valid"] and state["valid"] and sqlite_check == "ok" and database_schema["current"] == database_schema["supported"],
            "ledger": ledger,
            "lineage": lineage,
            "state": state,
            "sqlite_integrity": sqlite_check,
            "database_schema": database_schema,
            "config_root": self.config_root,
            "merkle_root": self.ledger.merkle_root(),
        }

    def introspect(self) -> dict[str, Any]:
        verification = self.verify()
        capability_count = self.database.connection.execute(
            "SELECT COUNT(*) AS count FROM capabilities WHERE revoked_at IS NULL"
        ).fetchone()["count"]
        approved_contracts = sum(
            1 for contract in self.bridge_registry.contracts.values() if contract["approved"]
        )
        report = {
            "name": "LOOM × VERATH Trustworthy Core",
            "version": self.state.value("runtime.version"),
            "status": "healthy" if verification["valid"] else "degraded",
            "kernel_id": self.state.value("system.kernel_id"),
            "config_root": self.config_root,
            "invariants": {
                "I1": "single StateStore mutation path",
                "I2": "bounded phi coupling",
                "I3": "append-only hash-chained Chrono-Scribe",
                "I4": "monotonic ethics and guardrail constraints",
                "I5": "Ed25519-signed kernel lineage",
                "I6": "structured introspection without private chain-of-thought",
            },
            "components": [
                "state_substrate",
                "chrono_scribe",
                "identity_lineage",
                "chrysalis_memory",
                "concept_classifier",
                "bridge_contracts",
                "four_gates",
                "capability_broker",
                "phitheta_engine",
                "simulation_engine",
                "ouroboros_evaluator",
                "layer_registry",
                "h_field_research_registry",
                "codepet_review_loop",
                "model_provider_boundary",
                "local_review_service",
                "mechanic_acceptance_runner",
                "bionemo_research_adapter",
            ],
            "memory": self.memory.stats(),
            "active_capabilities": capability_count,
            "bridge_contracts": {
                "total": len(self.bridge_registry.contracts),
                "approved": approved_contracts,
            },
            "layers": self.layers.summary(),
            "research_records": self.research.count(),
            "verification": verification,
            "boundary": {
                "real_world_actuation": False,
                "external_network": False,
                "biomedical_control": False,
                "speculative_claims_control_forge": False,
                "codepet_workspace_write": "explicit_change_hash_approval_required",
                "external_provider_calls": bool(
                    self.model_proposer is not None and self.model_proposer.provider.external
                ),
                "model_in_loop": self.model_proposer is not None,
                "harm_gate_judge": self.harm_judge is not None,
                "test_network_os_enforced": False,
                "bionemo_live_access": "separate_explicit_network_opt_in; research_only",
            },
        }
        if self.model_proposer is not None:
            report["components"].append("model_loop")
        return report

    def close(self) -> None:
        self.database.close()

    def __enter__(self) -> "LoomVerathRuntime":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
