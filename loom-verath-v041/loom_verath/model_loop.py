from __future__ import annotations

import json
from typing import Any

from .models import BridgeTranslation, Candidate, Classification
from .phitheta import EVIDENCE_SCORES, RISK_SCORES
from .providers import ModelProvider, OpenAICompatibleProvider, ProviderRequest
from .utils import canonical_json, sha256_hex


LOOP_SYSTEM_PROMPT = """You are a bounded candidate proposer inside a governed runtime.
Return ONE JSON object only, with this schema:
{"candidates":[{"mode":"analysis|research|simulation","action":"...","summary":"..."}]}
Propose at most 3 candidates. You have no authority: every candidate you propose is
scored and gated by the runtime before anything is executed, and the runtime may
ignore all of your candidates. Never propose memory operations, and never propose
shell, network, credential, or other external-effect actions."""

ALLOWED_MODEL_MODES = {"analysis", "research", "simulation"}

MAX_MODEL_CANDIDATES = 3
MAX_ACTION_CHARS = 500
MAX_SUMMARY_CHARS = 200
MAX_TASK_TEXT_CHARS = 2000


def _parse_json_object(content: str) -> dict[str, Any] | None:
    """Parse provider output into a JSON object, tolerating code fences.

    Mirrors the house pattern in ProviderProposalService._parse_json_object,
    but returns None instead of raising so the proposer can record a
    rejection and let the deterministic path continue.
    """
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            value = "\n".join(lines[1:-1])
            if value.lstrip().startswith("json"):
                value = value.lstrip()[4:].lstrip()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class ModelCandidateProposer:
    """Asks a model provider for extra candidates, under strict local control.

    The model only proposes. Every returned candidate is validated field by
    field, capped in count, restricted to non-memory modes, and assigned
    runtime-owned conservative scores; the raw prompt and raw response are
    never recorded — only their hashes reach the ledger record.
    """

    def __init__(self, provider: ModelProvider, *, consent: bool = False):
        self.provider = provider
        self.consent = consent

    def propose(
        self,
        text: str,
        classification: Classification,
        bridge: BridgeTranslation,
        deterministic_candidates: list[Candidate],
    ) -> tuple[list[Candidate], dict[str, Any]]:
        context: tuple[dict[str, str], ...] = (
            {
                "kind": "classification",
                "concept_id": classification.concept_id,
                "lane": classification.lane.value,
                "evidence_state": classification.evidence_state.value,
                "claim_status": classification.claim_status.value,
                "risk": classification.risk,
            },
            {
                "kind": "bridge",
                "contract_id": bridge.contract_id or "none",
                "execution_mode": bridge.execution_mode,
                "approved": "true" if bridge.approved else "false",
            },
            *(
                {
                    "kind": "deterministic_candidate",
                    "candidate_id": candidate.candidate_id,
                    "mode": candidate.mode,
                    "summary": candidate.summary,
                }
                for candidate in deterministic_candidates
            ),
        )
        task = (
            "Propose at most 3 candidate actions for the governed runtime to "
            "consider for the user request below. Return ONE JSON object: "
            '{"candidates":[{"mode":"analysis|research|simulation",'
            '"action":"...","summary":"..."}]}. You have no authority: the '
            "runtime scores and gates every candidate. Never propose memory "
            "operations or shell, network, or credential actions.\n"
            f"User request: {text[:MAX_TASK_TEXT_CHARS]}"
        )
        request = ProviderRequest(task=task, context=context)
        record: dict[str, Any] = {
            "provider": self.provider.name,
            "external": self.provider.external,
            "model": None,
            "status": "ok",
            "error": None,
            "request_hash": sha256_hex(
                canonical_json(
                    {"task": request.task, "context": [dict(item) for item in request.context]}
                )
            ),
            "response_hash": None,
            "proposed": 0,
            "accepted": 0,
            "rejections": {},
        }
        try:
            response = self.provider.complete(request, consent=self.consent)
        except Exception as exc:  # provider boundary: never propagate, never leak text
            record["status"] = "unavailable"
            record["error"] = type(exc).__name__
            return [], record
        record["model"] = response.model
        record["response_hash"] = sha256_hex(response.content)

        payload = _parse_json_object(response.content)
        raw_candidates = payload.get("candidates") if payload is not None else None
        if not isinstance(raw_candidates, list):
            record["status"] = "rejected"
            record["rejections"] = {"unparseable": 1}
            return [], record
        record["proposed"] = len(raw_candidates)

        evidence = min(EVIDENCE_SCORES[classification.evidence_state], 0.68)
        risk = max(RISK_SCORES.get(classification.risk, 0.5), 0.35)
        accepted: list[Candidate] = []
        rejections: dict[str, int] = {}
        for item in raw_candidates:
            if len(accepted) >= MAX_MODEL_CANDIDATES:
                rejections["over_limit"] = rejections.get("over_limit", 0) + 1
                continue
            reason = self._rejection_reason(item)
            if reason is not None:
                rejections[reason] = rejections.get(reason, 0) + 1
                continue
            accepted.append(
                Candidate(
                    candidate_id=f"model-{len(accepted) + 1}",
                    action=item["action"],
                    mode=item["mode"],
                    evidence=evidence,
                    coherence=0.7,
                    risk=risk,
                    utility=0.7,
                    reversibility=1.0 if item["mode"] in {"analysis", "research"} else 0.9,
                    summary=item["summary"],
                )
            )
        record["accepted"] = len(accepted)
        record["rejections"] = rejections
        return accepted, record

    @staticmethod
    def _rejection_reason(item: Any) -> str | None:
        if not isinstance(item, dict):
            return "not_an_object"
        if item.get("mode") not in ALLOWED_MODEL_MODES:
            return "mode_not_allowed"
        action = item.get("action")
        if not isinstance(action, str) or not 1 <= len(action) <= MAX_ACTION_CHARS:
            return "action_invalid"
        summary = item.get("summary")
        if not isinstance(summary, str) or len(summary) > MAX_SUMMARY_CHARS:
            return "summary_invalid"
        return None


def deepseek_v4_pro_provider(
    *, model: str = "DeepSeek-V4-Pro", api_key_env: str = "DEEPSEEK_API_KEY"
) -> OpenAICompatibleProvider:
    """Build the DeepSeek V4 Pro provider for the model loop (no call is made).

    Endpoint and model id follow the Chimeric registry v2
    synthesis_orchestration primary (deepseek-ai/DeepSeek-V4-Pro, MIT). The
    exact served model id must be confirmed against the provider's model
    list at first live use; constructing this object performs no network
    access and reads no credential.
    """
    return OpenAICompatibleProvider(
        endpoint="https://api.deepseek.com/v1/chat/completions",
        model=model,
        api_key_env=api_key_env,
        allowed_hosts={"api.deepseek.com"},
        system_prompt=LOOP_SYSTEM_PROMPT,
    )
