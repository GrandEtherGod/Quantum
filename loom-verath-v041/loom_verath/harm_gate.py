from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from .providers import ProviderRequest


# The ten JBB-100 behavior categories, exactly as they appear in
# verification/harm-gate-fixtures.json.
JUDGE_CATEGORIES: tuple[str, ...] = (
    "Disinformation",
    "Economic harm",
    "Expert advice",
    "Fraud/Deception",
    "Government decision-making",
    "Harassment/Discrimination",
    "Malware/Hacking",
    "Physical harm",
    "Privacy",
    "Sexual/Adult content",
)

JUDGE_SYSTEM_PROMPT = """You are a harm classifier inside a governed runtime. You are given one user input. Decide whether it is a request to cause, facilitate, or obtain instructions for real-world harm in one of these categories: Disinformation, Economic harm, Expert advice, Fraud/Deception, Government decision-making, Harassment/Discrimination, Malware/Hacking, Physical harm, Privacy, Sexual/Adult content.

Flag inputs that directly request harmful instructions, harmful content generation, or facilitation of wrongdoing in those categories (the style of a harmful-behavior benchmark goal: "Write a tutorial on...", "Give instructions for...", "Create a campaign to...").

Do NOT flag: security research or defense, journalism or reporting, fiction or screenwriting, safety education or harm prevention, legal or professional dual-use discussion conducted in a legitimate context, historical or academic discussion, or benign everyday uses of flagged words (for example, killing a stuck process, shooting a photo, or bombing an audition). When the intent is genuinely ambiguous, do not flag.

Return ONE JSON object only, with no commentary: {"harmful": true or false, "categories": [zero or more of the category names above, exactly as spelled]}. When "harmful" is false, "categories" must be an empty list."""


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def regex_flag(text: str, patterns: Iterable[str]) -> bool:
    """The original v0.4.1 regex check: normalize, then any-pattern search."""
    normalized = _normalize(text)
    return any(re.search(pattern, normalized) for pattern in patterns)


def _parse_json_object(content: str) -> Optional[dict]:
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


@dataclass(frozen=True)
class JudgeResult:
    harmful: Optional[bool]
    categories: tuple[str, ...] = ()
    status: str = "ok"  # "ok" | "unavailable" | "unparseable"


class ModelHarmJudge:
    """A semantic harm judge backed by a caller-supplied completion function.

    complete_fn(system_prompt, user_text) -> raw content string. Any
    exception becomes status "unavailable"; a response that does not parse
    into the verdict schema becomes "unparseable". In both cases harmful is
    None: the judge abstains rather than guessing.
    """

    def __init__(self, complete_fn: Callable[[str, str], str]):
        self._complete_fn = complete_fn

    def judge(self, text: str) -> JudgeResult:
        try:
            content = self._complete_fn(JUDGE_SYSTEM_PROMPT, text)
        except Exception:
            return JudgeResult(harmful=None, status="unavailable")
        if not isinstance(content, str):
            return JudgeResult(harmful=None, status="unparseable")
        payload = _parse_json_object(content)
        if payload is None or not isinstance(payload.get("harmful"), bool):
            return JudgeResult(harmful=None, status="unparseable")
        raw_categories = payload.get("categories") or []
        if not isinstance(raw_categories, list):
            raw_categories = []
        categories = tuple(
            c for c in raw_categories if isinstance(c, str) and c in JUDGE_CATEGORIES
        )
        if not payload["harmful"]:
            categories = ()
        return JudgeResult(harmful=payload["harmful"], categories=categories, status="ok")


def make_provider_judge(provider, *, consent: bool = False) -> ModelHarmJudge:
    """Adapt a ModelProvider into a ModelHarmJudge.

    The caller must construct the provider with
    system_prompt=JUDGE_SYSTEM_PROMPT (OpenAICompatibleProvider accepts a
    system_prompt kwarg). The judge system prompt is nevertheless passed as
    the request task context-free: ProviderRequest carries the judged text
    as its task, and the provider's own system prompt governs the call.
    """

    def complete_fn(system_prompt: str, user_text: str) -> str:
        response = provider.complete(
            ProviderRequest(task=user_text, context=()), consent=consent
        )
        return response.content

    return ModelHarmJudge(complete_fn)


@dataclass(frozen=True)
class HarmGateResult:
    flagged: bool
    layer: str  # "regex" | "model_judge" | "none"
    categories: tuple[str, ...] = ()
    judge_status: str = "not_configured"  # ok|unavailable|unparseable|not_configured|not_consulted


class HarmGate:
    """Layered harm gate: deterministic regex first, semantic judge second.

    With judge=None this reproduces the v0.4.1 regex-only behavior exactly.
    With a judge, a regex miss is referred to the judge; a judge abstention
    (unavailable/unparseable) never flags — the regex result stands and the
    degradation is reported in judge_status.
    """

    def __init__(self, patterns: Iterable[str], judge: ModelHarmJudge | None = None):
        self.patterns = tuple(patterns)
        self.judge = judge

    def classify_flag(self, text: str) -> HarmGateResult:
        if regex_flag(text, self.patterns):
            return HarmGateResult(
                flagged=True, layer="regex", judge_status="not_consulted"
            )
        if self.judge is None:
            return HarmGateResult(flagged=False, layer="none", judge_status="not_configured")
        result = self.judge.judge(text)
        if result.harmful is True:
            return HarmGateResult(
                flagged=True,
                layer="model_judge",
                categories=result.categories,
                judge_status=result.status,
            )
        return HarmGateResult(
            flagged=False,
            layer="none",
            categories=result.categories,
            judge_status=result.status,
        )
