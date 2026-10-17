from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import load_json


class LayerRegistry:
    """Machine-readable separation between canonical language and runtime authority."""

    def __init__(self, config_dir: Path | None = None):
        root = config_dir or Path(__file__).parent / "config"
        records: list[dict[str, Any]] = load_json(root / "layers.json")
        if [item["layer"] for item in records] != list(range(28)):
            raise ValueError("Layer registry must contain exactly L0 through L27 in order")
        self.records = tuple(records)

    def get(self, layer: int) -> dict[str, Any]:
        if not 0 <= layer < len(self.records):
            raise KeyError(f"Unknown layer L{layer}")
        return dict(self.records[layer])

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for item in self.records:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return {"total": len(self.records), "by_status": counts, "runtime_authority": "forge_only"}

    def to_dict(self) -> dict[str, Any]:
        return {"summary": self.summary(), "layers": [dict(item) for item in self.records]}
