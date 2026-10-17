from __future__ import annotations

from pathlib import Path
from typing import Any


CATALOG: dict[str, dict[str, str]] = {
    "field": {"title": "Field research", "status": "Research hypothesis", "transcript": "Field language names exploratory correlations. It does not establish a new physical field or grant operational authority."},
    "thesis": {"title": "The LOOM thesis", "status": "Architecture specification", "transcript": "LOOM separates buildable software, symbolic vocabulary, and testable bridge experiments so evidence and authority remain visible."},
    "systems": {"title": "Systems architecture", "status": "Implemented scaffold", "transcript": "The runtime uses bounded state, an audit ledger, signed lineage, encrypted memory, policy gates, and least-privilege capabilities."},
    "repository": {"title": "Repository guide", "status": "Implemented scaffold", "transcript": "The repository contains the runtime, tests, architecture records, and an optional offline model-forge package. Model weights are not included."},
    "consultation": {"title": "Consultation", "status": "Public positioning", "transcript": "Consultation can translate a symbolic architecture into scoped software, measurable research, governance, tests, and rollback criteria."},
}


class SiteGuide:
    VOICES = (
        {"id": "narrator", "label": "Narrator", "descriptor": "measured"},
        {"id": "educator", "label": "Educator", "descriptor": "clear"},
        {"id": "conversational", "label": "Conversational", "descriptor": "warm"},
    )

    def context(self, content_id: str) -> dict[str, Any]:
        if content_id not in CATALOG:
            raise ValueError("Unknown canonical content identifier")
        return {"contentId": content_id, **CATALOG[content_id], "voices": list(self.VOICES), "provider_called": False}

    def questionnaire(self, content_id: str, *, consent: bool) -> dict[str, Any]:
        if consent is not True:
            raise ValueError("Affirmative consent is required")
        context = self.context(content_id)
        return {
            "orientation": f"Review {context['title']} as {context['status'].lower()}.",
            "questions": ["What outcome matters most?", "What evidence would change your view?", "What boundary should the implementation preserve?"],
            "boundary": "Do not provide sensitive personal data; answers are not stored by this component.",
        }

    def export(self, content_id: str, path: Path) -> dict[str, Any]:
        context = self.context(content_id)
        output = "\n".join([
            "AXIUS SITE GUIDE — OFFLINE TRANSCRIPT", "", f"Title: {context['title']}",
            f"Evidence status: {context['status']}", "Source: Public Site Guide context",
            "Privacy: This local file contains no visitor responses or personal data.", "", "TRANSCRIPT",
            context["transcript"], "", "This evidence label does not elevate research material into verified capability.", "",
        ])
        destination = path.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(output, encoding="utf-8")
        return {"path": str(destination), "bytes": len(output.encode("utf-8")), "visitor_data_stored": False}
