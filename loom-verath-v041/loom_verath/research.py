from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .db import Database
from .ledger import ChronoScribeLedger
from .utils import canonical_json, sha256_hex, utc_now


class ResearchValidationError(ValueError):
    pass


class HFieldRegistry:
    """Strict ingestion for quantum experiment metadata with no product authority."""

    REQUIRED = {
        "record_id", "experiment_id", "created_at_utc", "circuit_hash_sha256",
        "gate_count", "circuit_depth", "qubit_count", "shots", "counts",
        "provider", "backend", "simulator_or_hardware", "status", "review_status",
    }
    ENUMS = {
        "simulator_or_hardware": {"simulator", "hardware"},
        "status": {"queued", "running", "completed", "failed", "cancelled"},
        "review_status": {"unreviewed", "reviewed", "flagged", "approved"},
    }

    def __init__(self, database: Database, ledger: ChronoScribeLedger):
        self.database = database
        self.ledger = ledger

    @staticmethod
    def _timestamp(value: Any, name: str) -> None:
        if not isinstance(value, str):
            raise ResearchValidationError(f"{name} must be an ISO-8601 string")
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ResearchValidationError(f"{name} must be ISO-8601") from exc

    def validate(self, record: dict[str, Any]) -> dict[str, Any]:
        missing = sorted(self.REQUIRED - record.keys())
        if missing:
            raise ResearchValidationError(f"Missing required fields: {', '.join(missing)}")
        for key, choices in self.ENUMS.items():
            if record[key] not in choices:
                raise ResearchValidationError(f"{key} must be one of {sorted(choices)}")
        self._timestamp(record["created_at_utc"], "created_at_utc")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(record["circuit_hash_sha256"])):
            raise ResearchValidationError("circuit_hash_sha256 must contain 64 hexadecimal characters")
        for key in ("gate_count", "circuit_depth", "qubit_count", "shots"):
            if not isinstance(record[key], int) or isinstance(record[key], bool) or record[key] < 0:
                raise ResearchValidationError(f"{key} must be a non-negative integer")
        if record["shots"] < 1:
            raise ResearchValidationError("shots must be positive")
        counts = record["counts"]
        if not isinstance(counts, dict) or not counts or any(not isinstance(v, int) or v < 0 for v in counts.values()):
            raise ResearchValidationError("counts must be a non-empty map of non-negative integers")
        if record["status"] == "completed" and sum(counts.values()) != record["shots"]:
            raise ResearchValidationError("completed record counts must sum to shots")
        probabilities = record.get("probabilities")
        if probabilities is not None:
            if not isinstance(probabilities, dict) or any(not isinstance(v, (int, float)) or v < 0 or v > 1 for v in probabilities.values()):
                raise ResearchValidationError("probabilities must map outcomes to values in [0, 1]")
            if abs(sum(probabilities.values()) - 1.0) > 1e-6:
                raise ResearchValidationError("probabilities must sum to 1")
        warnings = []
        if "synchronicity_score" in record:
            warnings.append("synchronicity_score is exploratory and is not evidence of an H-field")
            if not record.get("null_model_batch_id"):
                raise ResearchValidationError("synchronicity_score requires null_model_batch_id")
        if record["simulator_or_hardware"] == "hardware" and not record.get("calibration_timestamp_utc"):
            raise ResearchValidationError("hardware records require calibration_timestamp_utc")
        return {"valid": True, "record_id": record["record_id"], "authority": "research_only", "warnings": warnings}

    def validate_file(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ResearchValidationError("record JSON must be an object")
        return self.validate(value)

    def ingest_file(self, path: Path, *, actor: str) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as handle:
            record = json.load(handle)
        validation = self.validate(record)
        payload = canonical_json(record)
        payload_hash = sha256_hex(payload)
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO research_records VALUES (?, ?, ?, ?, ?, 'research_only', ?)",
                (record["record_id"], record["experiment_id"], payload, payload_hash, record["review_status"], utc_now()),
            )
            self.ledger.append("research_record_ingested", {
                "record_id": record["record_id"], "experiment_id": record["experiment_id"],
                "payload_hash": payload_hash, "review_status": record["review_status"],
                "authority": "research_only",
            }, actor=actor, connection=connection)
        return {**validation, "payload_hash": payload_hash, "stored": True}

    def count(self) -> int:
        return int(self.database.connection.execute("SELECT COUNT(*) FROM research_records").fetchone()[0])
