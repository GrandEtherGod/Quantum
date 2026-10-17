import json
import os
import tempfile
import unittest
import urllib.request
from unittest import mock

from loom_verath import LoomVerathRuntime
from loom_verath.errors import CodePetError
from loom_verath.model_loop import LOOP_SYSTEM_PROMPT, deepseek_v4_pro_provider
from loom_verath.providers import (
    SYSTEM_PROMPT,
    OpenAICompatibleProvider,
    ProviderRequest,
    ProviderResponse,
)


class StubProvider:
    """Minimal ModelProvider stub: canned content or a raised error."""

    name = "stub"
    external = False

    def __init__(self, content: str | None = None, error: Exception | None = None):
        self.content = content
        self.error = error
        self.requests = []

    def complete(self, request, *, consent: bool = False) -> ProviderResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return ProviderResponse(self.content, "stub-v1", self.name)


def _content(candidates, **extra) -> str:
    return json.dumps({"candidates": candidates, **extra})


def _model_proposals(runtime) -> list[dict]:
    return [
        event["payload"]
        for event in runtime.ledger.all_events()
        if event["event_type"] == "model_proposal"
    ]


class ModelLoopRuntimeTests(unittest.TestCase):
    def make_runtime(self, provider=None):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        runtime = LoomVerathRuntime(temp.name, model_provider=provider)
        self.addCleanup(runtime.close)
        return runtime

    def test_model_candidate_selected_when_only_admissible_path(self):
        # The classification is RESTRICTED (real-world marker upgrades the
        # research claim), so the harm gate blocks every deterministic
        # candidate: primary/research/analysis modes all fail, and only a
        # simulation-mode candidate under an approved bridge can pass.
        # Approving the contract in this instance's registry models the
        # governance state in which that bridge is authorized.
        marker = "RAW-RESPONSE-MARKER-7f3a"
        provider = StubProvider(
            _content(
                [
                    {
                        "mode": "simulation",
                        "action": "Simulate the bounded measurement protocol with negative controls.",
                        "summary": "Bounded simulation of the measurement protocol.",
                    }
                ],
                raw_marker=marker,
            )
        )
        runtime = self.make_runtime(provider)
        runtime.bridge_registry.contracts["BC-ZPE-001"]["approved"] = True

        result = runtime.run("Harness zero-point energy and make it real")

        self.assertEqual("model-1", result.selected_candidate_id)
        self.assertNotEqual("blocked", result.status)
        records = _model_proposals(runtime)
        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual("ok", record["status"])
        self.assertEqual("stub", record["provider"])
        self.assertFalse(record["external"])
        self.assertEqual("stub-v1", record["model"])
        self.assertEqual(1, record["proposed"])
        self.assertEqual(1, record["accepted"])
        self.assertEqual({}, record["rejections"])
        self.assertEqual(64, len(record["request_hash"]))
        self.assertEqual(64, len(record["response_hash"]))
        # Raw provider output is never sealed: only hashes reach the ledger,
        # anywhere in it.
        all_payloads = json.dumps(
            [event["payload"] for event in runtime.ledger.all_events()]
        )
        self.assertNotIn(marker, all_payloads)

    def test_model_memory_mode_is_rejected(self):
        provider = StubProvider(
            _content(
                [
                    {
                        "mode": "memory",
                        "action": "Write this to long-term memory.",
                        "summary": "Illicit memory operation.",
                    }
                ]
            )
        )
        runtime = self.make_runtime(provider)
        result = runtime.run("Design a bounded software workflow")
        self.assertEqual("completed", result.status)
        self.assertFalse((result.selected_candidate_id or "").startswith("model-"))
        record = _model_proposals(runtime)[0]
        self.assertEqual(0, record["accepted"])
        self.assertEqual({"mode_not_allowed": 1}, record["rejections"])

    def test_malformed_response_is_rejected_and_run_completes(self):
        provider = StubProvider("this is not json at all")
        runtime = self.make_runtime(provider)
        result = runtime.run("Design a bounded software workflow")
        self.assertEqual("completed", result.status)
        record = _model_proposals(runtime)[0]
        self.assertEqual("rejected", record["status"])
        self.assertEqual({"unparseable": 1}, record["rejections"])
        self.assertEqual(0, record["accepted"])
        self.assertEqual(64, len(record["response_hash"]))

    def test_provider_error_is_unavailable_and_error_text_never_sealed(self):
        provider = StubProvider(error=RuntimeError("boom-secret-detail"))
        runtime = self.make_runtime(provider)
        result = runtime.run("Design a bounded software workflow")
        self.assertEqual("completed", result.status)
        record = _model_proposals(runtime)[0]
        self.assertEqual("unavailable", record["status"])
        self.assertEqual("RuntimeError", record["error"])
        self.assertIsNone(record["model"])
        self.assertIsNone(record["response_hash"])
        self.assertNotIn("boom-secret-detail", json.dumps(record))

    def test_at_most_three_candidates_accepted(self):
        candidates = [
            {"mode": "analysis", "action": f"Analyze option {n}.", "summary": f"Option {n}."}
            for n in range(5)
        ]
        provider = StubProvider(_content(candidates))
        runtime = self.make_runtime(provider)
        result = runtime.run("Design a bounded software workflow")
        self.assertEqual("completed", result.status)
        record = _model_proposals(runtime)[0]
        self.assertEqual(5, record["proposed"])
        self.assertEqual(3, record["accepted"])
        self.assertEqual({"over_limit": 2}, record["rejections"])
        model_ids = [
            candidate.candidate_id
            for candidate in result.candidates
            if candidate.candidate_id.startswith("model-")
        ]
        self.assertEqual(["model-1", "model-2", "model-3"], model_ids)

    def test_candidate_validation_reasons(self):
        provider = StubProvider(
            _content(
                [
                    "not-a-dict",
                    {"mode": "analysis", "action": "x" * 501, "summary": "Too long."},
                    {"mode": "analysis", "action": "Reasonable action."},
                    {"mode": "research", "action": "Reasonable action.", "summary": "Fine."},
                ]
            )
        )
        runtime = self.make_runtime(provider)
        runtime.run("Design a bounded software workflow")
        record = _model_proposals(runtime)[0]
        self.assertEqual(4, record["proposed"])
        self.assertEqual(1, record["accepted"])
        self.assertEqual(
            {"not_an_object": 1, "action_invalid": 1, "summary_invalid": 1},
            record["rejections"],
        )

    def test_replay_of_model_selected_session_is_not_deterministic(self):
        provider = StubProvider(
            _content(
                [
                    {
                        "mode": "simulation",
                        "action": "Simulate the bounded measurement protocol with negative controls.",
                        "summary": "Bounded simulation of the measurement protocol.",
                    }
                ]
            )
        )
        runtime = self.make_runtime(provider)
        runtime.bridge_registry.contracts["BC-ZPE-001"]["approved"] = True
        result = runtime.run("Harness zero-point energy and make it real")
        self.assertEqual("model-1", result.selected_candidate_id)

        replay = runtime.replay(result.session_id)
        self.assertTrue(replay["ledger_chain_valid"])
        self.assertTrue(replay["model_selected"])
        self.assertFalse(replay["deterministic"])
        self.assertIsNone(replay["output_match"])
        self.assertIsNone(replay["replayed_output_hash"])
        # Replay must never consult the provider.
        self.assertEqual(1, len(provider.requests))

    def test_replay_of_deterministic_session_unchanged(self):
        provider = StubProvider(_content([]))
        runtime = self.make_runtime(provider)
        result = runtime.run(
            "Create a fireball radius 5 duration 2 intensity 0.4",
            requested_mode="simulation",
        )
        replay = runtime.replay(result.session_id)
        self.assertTrue(replay["deterministic"])
        self.assertFalse(replay["model_selected"])
        self.assertTrue(replay["output_match"])

    def test_no_provider_means_no_model_events_and_boundary_closed(self):
        runtime = self.make_runtime()
        result = runtime.run("Design a bounded software workflow")
        self.assertEqual("completed", result.status)
        self.assertEqual([], _model_proposals(runtime))
        introspection = runtime.introspect()
        self.assertFalse(introspection["boundary"]["model_in_loop"])
        self.assertFalse(introspection["boundary"]["external_provider_calls"])
        self.assertNotIn("model_loop", introspection["components"])

    def test_provider_configured_opens_introspection_boundary(self):
        runtime = self.make_runtime(StubProvider(_content([])))
        introspection = runtime.introspect()
        self.assertTrue(introspection["boundary"]["model_in_loop"])
        # The stub is not external, so external calls stay closed.
        self.assertFalse(introspection["boundary"]["external_provider_calls"])
        self.assertIn("model_loop", introspection["components"])


class _FakeResponse:
    def __init__(self, body: bytes):
        self.status = 200
        self._body = body

    def read(self, _limit: int) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None


class _FakeOpener:
    def __init__(self, body: bytes):
        self._body = body
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        return _FakeResponse(self._body)


class ProviderSystemPromptTests(unittest.TestCase):
    ENDPOINT = "https://api.example.test/v1/chat/completions"

    def make_provider(self, **kwargs) -> OpenAICompatibleProvider:
        return OpenAICompatibleProvider(
            endpoint=self.ENDPOINT,
            model="model-x",
            api_key_env="LOOM_TEST_PROVIDER_KEY",
            allowed_hosts={"api.example.test"},
            **kwargs,
        )

    def capture_payload(self, provider) -> dict:
        body = json.dumps(
            {"choices": [{"message": {"content": "{}"}}]}
        ).encode("utf-8")
        opener = _FakeOpener(body)
        with mock.patch.dict(os.environ, {"LOOM_TEST_PROVIDER_KEY": "test-key"}):
            with mock.patch.object(
                urllib.request, "build_opener", lambda *handlers: opener
            ):
                provider.complete(ProviderRequest(task="t", context=()), consent=True)
        return json.loads(opener.requests[0].data.decode("utf-8"))

    def test_default_system_prompt_is_codepet_prompt(self):
        provider = self.make_provider()
        self.assertIs(SYSTEM_PROMPT, provider.system_prompt)
        payload = self.capture_payload(provider)
        self.assertEqual(SYSTEM_PROMPT, payload["messages"][0]["content"])

    def test_custom_system_prompt_is_sent(self):
        provider = self.make_provider(system_prompt="CUSTOM LOOP PROMPT")
        self.assertEqual("CUSTOM LOOP PROMPT", provider.system_prompt)
        payload = self.capture_payload(provider)
        self.assertEqual("CUSTOM LOOP PROMPT", payload["messages"][0]["content"])

    def test_consent_gate_fires_before_any_network(self):
        provider = self.make_provider()
        with self.assertRaises(CodePetError):
            provider.complete(ProviderRequest(task="t", context=()), consent=False)

    def test_deepseek_factory_builds_loop_provider_without_calling(self):
        provider = deepseek_v4_pro_provider()
        self.assertEqual("https://api.deepseek.com/v1/chat/completions", provider.endpoint)
        self.assertEqual("DeepSeek-V4-Pro", provider.model)
        self.assertEqual("DEEPSEEK_API_KEY", provider.api_key_env)
        self.assertIs(LOOP_SYSTEM_PROMPT, provider.system_prompt)
        self.assertTrue(provider.external)


if __name__ == "__main__":
    unittest.main()
