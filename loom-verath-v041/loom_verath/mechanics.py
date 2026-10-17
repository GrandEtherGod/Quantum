"""Typed text/gesture inputs and deterministic geometry; no device actuation."""
from __future__ import annotations

import itertools
import math
import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MechanicCommand:
    source: str
    mechanic: str
    text: str
    mode: str = "simulation"

    def to_dict(self) -> dict:
        return asdict(self)


class VoxParser:
    """Small explicit grammar. Speech recognition is a separate future adapter."""

    @staticmethod
    def parse(text: str) -> MechanicCommand:
        if not isinstance(text, str) or len(text) > 512:
            raise ValueError("VOX input must be text of at most 512 characters")
        match = re.fullmatch(r"(dome|fireball)(?: radius (\d+(?:\.\d+)?))?", text.strip().lower())
        if not match:
            raise ValueError("VOX grammar: dome [radius N] or fireball [radius N]")
        mechanic, raw = match.groups()
        radius = float(raw or (10 if mechanic == "dome" else 3))
        if not math.isfinite(radius) or not 0.1 <= radius <= 100:
            raise ValueError("Radius must be finite and in [0.1, 100]")
        command = (f"Build a tesseract dome radius {radius}" if mechanic == "dome"
                   else f"Create a fireball with VOX and Shape Power radius {radius}")
        return MechanicCommand("vox_text", mechanic, command)


class JintaiHands:
    """Normalized hand-controller events. No camera or anatomical model implied."""

    @staticmethod
    def parse(event: dict) -> MechanicCommand:
        if not isinstance(event, dict) or set(event) != {"gesture", "confidence", "radius"}:
            raise ValueError("Hand event requires exactly gesture, confidence, radius")
        if event["gesture"] not in {"open_palm", "closed_fist"}:
            raise ValueError("Unsupported gesture")
        for name in ("confidence", "radius"):
            value = event[name]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if not 0.85 <= event["confidence"] <= 1:
            raise ValueError("Gesture confidence must be in [0.85, 1]")
        command = VoxParser.parse(f"{'dome' if event['gesture'] == 'open_palm' else 'fireball'} radius {event['radius']}")
        return MechanicCommand("jintai_controller_simulation", command.mechanic, command.text)


def tesseract_geometry(radius: float = 10) -> dict:
    if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not math.isfinite(radius) or not 0.1 <= radius <= 100:
        raise ValueError("Geometry radius must be in [0.1, 100]")
    vertices = [list(vertex) for vertex in itertools.product((-1, 1), repeat=4)]
    edges = [[i, j] for i, a in enumerate(vertices) for j, b in enumerate(vertices)
             if i < j and sum(x != y for x, y in zip(a, b)) == 1]
    # Perspective projection from 4D to 3D. Radius is a display scale only.
    projected = [[round(radius * x / (3 - v[3]), 6) for x in v[:3]] for v in vertices]
    return {"artifact_type": "tesseract_geometry", "vertices_4d": vertices,
            "vertices_3d": projected, "edges": edges, "radius_display_units": radius,
            "lane": "BRIDGE", "claim_status": "simulation_buildable",
            "external_effects": False, "actuator_used": False}
