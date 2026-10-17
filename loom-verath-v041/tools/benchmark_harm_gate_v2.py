"""Harm-gate benchmark v2 — layered gate (regex + semantic model judge).

Extends tools/benchmark_harm_gate.py (v1, regex only; baseline recall 0.04
on JBB-100) with a ModelHarmJudge layer backed by DeepSeek-V4-Pro over the
vault surrogate transport, and evaluates three configurations over the same
fixtures:

  regex_only  — HarmGate(HARM_PATTERNS), the v0.4.1 behavior
  judge_only  — the model judge alone (regex ignored)
  layered     — regex first; regex misses referred to the judge

plus an adversarial subset: the first 3 harmful prompts per category under
two obfuscation transforms (leetspeak, spaced characters), layered config.

The v1 record (verification/harm-gate-benchmark.json) is never overwritten;
this writes verification/harm-gate-benchmark-v2.json. Following the v1 record
shape, harmful entries store index/behavior/category/flagged only — never
the prompt text. Benign / over-refusal false positives may store the prompt.

Usage: python3 tools/benchmark_harm_gate_v2.py   (requires the vault
DeepSeek credential; judge calls are made with consent for this benchmark)
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

TREE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TREE))
sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")

from dynamic_credentials import add_surrogate_to_request, read_json_response  # noqa: E402

from loom_verath.classifier import HARM_PATTERNS  # noqa: E402
from loom_verath.harm_gate import (  # noqa: E402
    JUDGE_SYSTEM_PROMPT,
    HarmGate,
    JudgeResult,
    ModelHarmJudge,
    regex_flag,
)

DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODELS_ENDPOINT = "https://api.deepseek.com/v1/models"
DEEPSEEK_HOSTS = {"api.deepseek.com"}
DEEPSEEK_CREDENTIAL = "custom.deepseek"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_NoRedirect)


class VaultJudgeTransport:
    """DeepSeek chat completions via the vault surrogate exchange.

    Only an hsurr:* surrogate is attached here; the real API key is swapped
    in by authd/Sentinel on the outbound request to api.deepseek.com.
    """

    def __init__(self, timeout_seconds: int = 120):
        self.timeout_seconds = timeout_seconds
        self.model_id: str | None = None
        self.served_models: list[str] = []
        self.last_error: str | None = None

    def _resolve_model(self) -> None:
        if self.model_id:
            return
        request = urllib.request.Request(DEEPSEEK_MODELS_ENDPOINT, method="GET")
        add_surrogate_to_request(request, DEEPSEEK_CREDENTIAL, allowed_hosts=DEEPSEEK_HOSTS)
        with _opener().open(request, timeout=30) as response:
            payload = read_json_response(response)
        self.served_models = [
            str(m.get("id")) for m in payload.get("data", []) if m.get("id")
        ]
        for model_id in self.served_models:
            if "v4-pro" in model_id.lower():
                self.model_id = model_id
                return
        self.model_id = "deepseek-v4-pro"

    def complete_fn(self, system_prompt: str, user_text: str) -> str:
        self._resolve_model()
        body = json.dumps(
            {
                "model": self.model_id,
                "temperature": 0,
                # deepseek-v4-pro spends completion tokens on reasoning
                # before emitting content; 200 starved the verdict entirely
                # (finish_reason=length, empty content). 4000 leaves room.
                "max_tokens": 4000,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            DEEPSEEK_ENDPOINT,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        add_surrogate_to_request(request, DEEPSEEK_CREDENTIAL, allowed_hosts=DEEPSEEK_HOSTS)
        try:
            with _opener().open(request, timeout=self.timeout_seconds) as response:
                payload = read_json_response(response)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                detail = ""
            self.last_error = f"HTTP {exc.code}: {detail}"
            raise RuntimeError(self.last_error) from exc
        except urllib.error.URLError as exc:
            self.last_error = f"Provider request failed: {exc.reason}"
            raise RuntimeError(self.last_error) from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            self.last_error = "Provider returned an invalid completion envelope"
            raise RuntimeError(self.last_error) from exc
        if not isinstance(content, str):
            self.last_error = "Provider completion content must be text"
            raise RuntimeError(self.last_error)
        return content


class CachedJudge:
    """JudgeResult lookup over pre-evaluated verdicts (duck-typed judge)."""

    def __init__(self, cache: dict[str, JudgeResult]):
        self.cache = cache
        self.consulted: list[str] = []

    def judge(self, text: str) -> JudgeResult:
        self.consulted.append(text)
        return self.cache[text]


_LEET = str.maketrans({"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7"})


def leetspeak(prompt: str) -> str:
    return prompt.translate(_LEET)


def spaced(prompt: str) -> str:
    words = prompt.split(" ")
    head = [" ".join(list(word)) if word else word for word in words[:3]]
    return " ".join(head + words[3:])


def _latency_block(values: list[float]) -> dict:
    ordered = sorted(values)
    return {
        "median": round(statistics.median(ordered), 4),
        "p95": round(ordered[int(0.95 * len(ordered)) - 1], 4),
        "max": round(ordered[-1], 4),
    }


def _per_category(records: list[dict]) -> dict:
    categories: dict[str, dict[str, int]] = {}
    for record in records:
        bucket = categories.setdefault(record["category"], {"flagged": 0, "total": 0})
        bucket["total"] += 1
        bucket["flagged"] += int(record["flagged"])
    return {
        name: {
            "recall": round(b["flagged"] / b["total"], 4),
            "flagged": b["flagged"],
            "total": b["total"],
        }
        for name, b in sorted(categories.items())
    }


def _summarize(harmful: list[dict], benign: list[dict], over_refusal: list[dict]) -> dict:
    return {
        "recall_jbb100": round(sum(r["flagged"] for r in harmful) / len(harmful), 4),
        "flagged_jbb100": sum(r["flagged"] for r in harmful),
        "per_category_recall": _per_category(harmful),
        "false_positive_rate_benign": round(
            sum(r["flagged"] for r in benign) / len(benign), 4
        ),
        "false_positives_benign": [r["prompt"] for r in benign if r["flagged"]],
        "over_refusal_rate": round(
            sum(r["flagged"] for r in over_refusal) / len(over_refusal), 4
        ),
        "over_refused_prompts": [r["prompt"] for r in over_refusal if r["flagged"]],
        "harmful": harmful,
    }


def main() -> int:
    fixtures_path = TREE / "verification" / "harm-gate-fixtures.json"
    fixtures = json.loads(fixtures_path.read_text())
    harmful_entries = fixtures["harmful_jbb100"]
    benign_entries = fixtures["benign"]
    over_entries = fixtures["over_refusal"]

    # Adversarial subset: first 3 harmful prompts per category, in fixture order.
    by_category: dict[str, list[dict]] = {}
    for entry in harmful_entries:
        by_category.setdefault(entry["category"], []).append(entry)
    adversarial_sources: list[dict] = []
    for category in sorted(by_category):
        adversarial_sources.extend(by_category[category][:3])
    adversarial_prompts: dict[str, list[tuple[dict, str]]] = {"leetspeak": [], "spaced": []}
    for entry in adversarial_sources:
        adversarial_prompts["leetspeak"].append((entry, leetspeak(entry["prompt"])))
        adversarial_prompts["spaced"].append((entry, spaced(entry["prompt"])))

    all_prompts = (
        [e["prompt"] for e in harmful_entries]
        + [e["prompt"] for e in benign_entries]
        + [e["prompt"] for e in over_entries]
        + [p for pairs in adversarial_prompts.values() for _, p in pairs]
    )
    unique_prompts = sorted(set(all_prompts))
    print(f"judge calls required: {len(unique_prompts)} unique prompts")

    transport = VaultJudgeTransport()
    judge = ModelHarmJudge(transport.complete_fn)

    verdicts: dict[str, JudgeResult] = {}
    judge_latencies: dict[str, float] = {}

    def evaluate(prompt: str) -> tuple[str, JudgeResult, float]:
        started = time.perf_counter()
        result = judge.judge(prompt)
        return prompt, result, (time.perf_counter() - started) * 1000.0

    with ThreadPoolExecutor(max_workers=4) as pool:
        for prompt, result, elapsed in pool.map(evaluate, unique_prompts):
            verdicts[prompt] = result
            judge_latencies[prompt] = elapsed

    ok_count = sum(1 for r in verdicts.values() if r.status == "ok")
    print(f"judge verdicts ok: {ok_count}/{len(verdicts)} (model: {transport.model_id})")
    if ok_count == 0:
        print(f"ABORT: judge transport failed for every prompt. last_error={transport.last_error}")
        return 2

    cached = CachedJudge(verdicts)
    gate_regex_only = HarmGate(HARM_PATTERNS)
    gate_layered = HarmGate(HARM_PATTERNS, judge=cached)

    def run_config(flag_fn):
        harmful = [
            {
                "index": e["index"],
                "behavior": e["behavior"],
                "category": e["category"],
                "flagged": flag_fn(e["prompt"]),
            }
            for e in harmful_entries
        ]
        benign = [
            {"prompt": e["prompt"], "flagged": flag_fn(e["prompt"])} for e in benign_entries
        ]
        over = [
            {"prompt": e["prompt"], "flagged": flag_fn(e["prompt"])} for e in over_entries
        ]
        return _summarize(harmful, benign, over)

    def status_counts() -> dict:
        counts: dict[str, int] = {}
        for text in cached.consulted:
            status = verdicts[text].status
            counts[status] = counts.get(status, 0) + 1
        return counts

    # (a) regex only — with latency of the regex path itself.
    regex_latencies: list[float] = []

    def regex_timed(prompt: str) -> bool:
        started = time.perf_counter()
        result = gate_regex_only.classify_flag(prompt)
        regex_latencies.append((time.perf_counter() - started) * 1000.0)
        return result.flagged

    regex_only = run_config(regex_timed)
    regex_only["latency_ms"] = _latency_block(regex_latencies)
    regex_only["judge_status_counts"] = {}

    # (b) judge only.
    judge_only = run_config(lambda p: verdicts[p].harmful is True)
    fixture_prompts = [e["prompt"] for e in harmful_entries + benign_entries + over_entries]
    judge_only["judge_status_counts"] = {
        s: sum(1 for p in fixture_prompts if verdicts[p].status == s)
        for s in ("ok", "unavailable", "unparseable")
    }

    # (c) layered — judge consulted only on regex miss (via the cache).
    cached.consulted = []
    layered = run_config(lambda p: gate_layered.classify_flag(p).flagged)
    layered["judge_status_counts"] = status_counts()
    layered["judge_consultations"] = len(cached.consulted)
    layered["latency_ms"] = _latency_block(regex_latencies)  # regex part of the path
    layered["judge_latency_ms"] = _latency_block(list(judge_latencies.values()))

    # Adversarial: layered only.
    adversarial_report: dict[str, dict] = {}
    for name, pairs in adversarial_prompts.items():
        records = [
            {
                "index": e["index"],
                "behavior": e["behavior"],
                "category": e["category"],
                "flagged": gate_layered.classify_flag(transformed).flagged,
            }
            for e, transformed in pairs
        ]
        adversarial_report[name] = {
            "recall": round(sum(r["flagged"] for r in records) / len(records), 4),
            "flagged": sum(r["flagged"] for r in records),
            "total": len(records),
            "records": records,
        }
    source_subset_flagged = sum(
        gate_layered.classify_flag(e["prompt"]).flagged for e in adversarial_sources
    )
    adversarial_report["source_subset_layered_recall"] = round(
        source_subset_flagged / len(adversarial_sources), 4
    )

    baseline_reference = {
        "recall_jbb100": 0.04,
        "false_positive_rate_benign": 0.0,
        "over_refusal_rate": 0.025,
        "source": "verification/harm-gate-benchmark.json (v1, regex only)",
    }

    lo, jo, ro = layered, judge_only, regex_only
    adv = adversarial_report
    interpretation = (
        f"Layering the {transport.model_id} semantic judge over the v0.4.1 regex "
        f"moved JBB-100 recall from the v1 baseline of 0.04 (reproduced here as "
        f"{ro['recall_jbb100']} for regex_only) to {lo['recall_jbb100']} for the "
        f"layered gate; the judge alone reached {jo['recall_jbb100']}. The costs on "
        f"this fixture set: benign false-positive rate {lo['false_positive_rate_benign']} "
        f"(baseline 0.0) and over-refusal rate {lo['over_refusal_rate']} (baseline 0.025). "
        f"On obfuscated variants of 30 of the same harmful prompts, layered recall was "
        f"{adv['leetspeak']['recall']} (leetspeak) and {adv['spaced']['recall']} (spaced "
        f"characters), versus {adv['source_subset_layered_recall']} on the unmodified "
        f"subset. The judge abstained (unavailable/unparseable) on "
        f"{lo['judge_status_counts'].get('unavailable', 0) + lo['judge_status_counts'].get('unparseable', 0)} "
        f"of {lo['judge_consultations']} layered consultations; abstentions never flag, "
        f"so those prompts fall back to the regex verdict. Measured in a single run, "
        f"temperature 0, one judge model; judge-assigned categories are not "
        f"independently verified, and no comparison against Llama Guard / WildGuard "
        f"has been run — the v1 caveat on claiming robustness stands."
    )

    report = {
        "gate": "Layered harm gate v2: HARM_PATTERNS regex, then DeepSeek semantic judge on regex miss",
        "judge_model": transport.model_id,
        "judge_max_tokens": 4000,
        "prior_pass": {
            "judge_max_tokens": 200,
            "layered_recall_jbb100": 0.55,
            "judge_only_recall_jbb100": 0.54,
            "unparseable_of_201_fixture_verdicts": 39,
            "note": (
                "First pass used max_tokens=200; deepseek-v4-pro spent the whole "
                "budget on reasoning tokens (finish_reason=length) and returned "
                "empty content on 39 verdicts, recorded as unparseable "
                "abstentions. Transport corrected to 4000 and the benchmark "
                "re-run; the numbers in this file are the corrected pass."
            ),
        },
        "judge_served_models": transport.served_models,
        "judge_system_prompt": JUDGE_SYSTEM_PROMPT,
        "fixtures": str(fixtures_path),
        "n_harmful": len(harmful_entries),
        "n_benign": len(benign_entries),
        "n_over_refusal": len(over_entries),
        "baseline_reference": baseline_reference,
        "configurations": {
            "regex_only": regex_only,
            "judge_only": judge_only,
            "layered": layered,
        },
        "adversarial": adversarial_report,
        "interpretation": interpretation,
    }
    out_path = TREE / "verification" / "harm-gate-benchmark-v2.json"
    out_path.write_text(json.dumps(report, indent=2))
    headline = {
        name: {
            k: cfg[k]
            for k in (
                "recall_jbb100",
                "flagged_jbb100",
                "false_positive_rate_benign",
                "over_refusal_rate",
                "judge_status_counts",
            )
        }
        for name, cfg in report["configurations"].items()
    }
    print(json.dumps(headline, indent=2))
    print(
        "adversarial:",
        {k: v["recall"] for k, v in adversarial_report.items() if isinstance(v, dict)},
        "source subset:",
        adversarial_report["source_subset_layered_recall"],
    )
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
