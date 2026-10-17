from __future__ import annotations

from pathlib import Path
from typing import Any

from .db import Database
from .models import BridgeTranslation, ClaimStatus, Classification, Lane
from .utils import canonical_json, load_json, utc_now


class BridgeContractRegistry:
    def __init__(self, database: Database, config_dir: Path | None = None):
        self.database = database
        config_dir = config_dir or Path(__file__).parent / "config"
        contracts: list[dict[str, Any]] = load_json(config_dir / "bridge_contracts.json")
        self.contracts = {item["contract_id"]: item for item in contracts}
        self._seed_contracts()

    def _seed_contracts(self) -> None:
        with self.database.transaction() as connection:
            for contract_id, contract in self.contracts.items():
                existing = connection.execute(
                    "SELECT version FROM bridge_contracts WHERE contract_id=?", (contract_id,)
                ).fetchone()
                if existing is None:
                    connection.execute(
                        "INSERT INTO bridge_contracts VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            contract_id,
                            contract["version"],
                            canonical_json(contract),
                            int(contract["approved"]),
                            contract.get("approved_by"),
                            utc_now() if contract["approved"] else None,
                        ),
                    )

    def get(self, contract_id: str | None) -> dict[str, Any] | None:
        return self.contracts.get(contract_id) if contract_id else None

    def translate(
        self, classification: Classification, *, requested_mode: str | None = None
    ) -> BridgeTranslation:
        contract = self.get(classification.contract_id)
        if classification.concept_id == "restricted.real_world_harm":
            return BridgeTranslation(
                contract_id=None,
                approved=False,
                engineering_action="blocked",
                execution_mode="blocked",
                claim_label=classification.claim_status.value,
                safety_gate="No approved benign bridge contract exists for the requested harmful action.",
                fallback="Offer general safety analysis without procedural harmful detail.",
            )

        if classification.lane is Lane.FORGE:
            mode = requested_mode if requested_mode in {"build", "analysis", "memory"} else "analysis"
            return BridgeTranslation(
                contract_id=None,
                approved=True,
                engineering_action=classification.engineering_translation,
                execution_mode=mode,
                claim_label=classification.claim_status.value,
                safety_gate="Ordinary software boundary and capability checks apply.",
                fallback="Return a bounded implementation plan.",
            )

        if contract is None:
            return BridgeTranslation(
                contract_id=None,
                approved=False,
                engineering_action="research_only",
                execution_mode="research",
                claim_label=classification.claim_status.value,
                safety_gate="Temple-to-Forge influence requires an approved Bridge Contract.",
                fallback="Preserve the concept as symbolic and define a testable hypothesis.",
            )

        if classification.claim_status is ClaimStatus.RESEARCH or classification.lane is Lane.TEMPLE:
            return BridgeTranslation(
                contract_id=contract["contract_id"],
                approved=bool(contract["approved"]),
                engineering_action=contract["operational_interpretation"],
                execution_mode="research",
                claim_label=classification.claim_status.value,
                safety_gate=contract["safety_gate"],
                fallback=contract["fallback"],
            )

        return BridgeTranslation(
            contract_id=contract["contract_id"],
            approved=bool(contract["approved"]),
            engineering_action=contract["operational_interpretation"],
            execution_mode="simulation",
            claim_label=classification.claim_status.value,
            safety_gate=contract["safety_gate"],
            fallback=contract["fallback"],
        )

