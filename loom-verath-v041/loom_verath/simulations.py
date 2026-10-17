from __future__ import annotations

import re
from typing import Any

from .models import BridgeTranslation, Classification
from .utils import canonical_json, sha256_hex


def _number_after(label: str, text: str, default: float) -> float:
    match = re.search(rf"{re.escape(label)}\s*[:=]?\s*(\d+(?:\.\d+)?)", text.lower())
    return float(match.group(1)) if match else default


class SimulationEngine:
    """Deterministic, local-only simulations and blueprint generation."""

    def execute(
        self,
        text: str,
        classification: Classification,
        bridge: BridgeTranslation,
        mode: str,
    ) -> dict[str, Any]:
        if mode == "simulation" and classification.concept_id == "vox.fireball":
            radius = min(max(_number_after("radius", text, 3.0), 0.1), 100.0)
            duration = min(max(_number_after("duration", text, 5.0), 0.1), 60.0)
            intensity = min(max(_number_after("intensity", text, 0.5), 0.0), 1.0)
            artifact = {
                "artifact_type": "thermal_event_visualization",
                "parameters": {
                    "radius_m_visual_scale": radius,
                    "duration_seconds": duration,
                    "normalized_intensity": intensity,
                },
                "external_effects": False,
                "network_used": False,
                "actuator_used": False,
            }
        elif mode == "simulation" and classification.concept_id == "jintai.gate_eight":
            artifact = {
                "artifact_type": "fictional_escalation_state",
                "initial_risk_level": 8,
                "decay_sequence": [8, 6, 4, 2, 0],
                "somatic_instruction": None,
                "warning": "Fictional simulation only; no bodily technique or health claim.",
                "external_effects": False,
            }
        elif mode == "simulation" and classification.concept_id == "shape.tesseract_dome":
            artifact = {
                "artifact_type": "procedural_geometry_blueprint",
                "motif": "tesseract_projection",
                "vertices": 16,
                "edges": 32,
                "dome_radius_units": min(max(_number_after("radius", text, 10.0), 1.0), 1000.0),
                "living_growth_claim": False,
                "external_effects": False,
            }
        elif mode == "research":
            artifact = {
                "artifact_type": "research_protocol",
                "symbolic_source": classification.mythic_name,
                "operational_interpretation": bridge.engineering_action,
                "required_controls": [
                    "predeclared observable",
                    "ordinary alternative explanations",
                    "negative control",
                    "held-out evaluation",
                    "independent replication",
                ],
                "product_authority": False,
            }
        else:
            artifact = {
                "artifact_type": "bounded_work_plan",
                "engineering_translation": bridge.engineering_action,
                "steps": [
                    "validate inputs and capability scope",
                    "execute inside the declared software boundary",
                    "record provenance and evidence labels",
                    "verify output and preserve rollback",
                ],
                "external_effects": False,
            }
        artifact["artifact_hash"] = sha256_hex(canonical_json(artifact))
        return artifact

