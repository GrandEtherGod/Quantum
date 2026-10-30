import http.client
import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from loom_verath.cli import main
from loom_verath.codepet import CodePetWorkspace
from loom_verath.errors import CodePetError, ProposalStateError, StaleProposalError, WorkspaceBoundaryError
from loom_verath.providers import (
    AnthropicMessagesProvider,
    DeterministicProvider,
    OpenAICompatibleProvider,
    ProviderProposalService,
    ProviderRequest,
    chatgpt_provider,
    claude_provider,
)
from loom_verath.service import build_server


class CodePetWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        (self.root / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.pet = CodePetWorkspace(self.root)
        self.pet.initialize()

    def tearDown(self):
        self.temp.cleanup()

    def proposal(self, content: str = "VALUE = 2\n", tests=None):
        return self.pet.create_proposal(
            "Update value",
            [{"operation": "modify", "path": "main.py", "content": content}],
            tests=tests or ["python-compile"],
            rationale="Exercise the controlled build loop.",
        )

    def test_successful_approval_apply_and_verification(self):
        proposal = self.proposal()
        self.assertIn("-VALUE = 1", proposal["diff"])
        self.assertIn("+VALUE = 2", proposal["diff"])
        with self.assertRaises(ProposalStateError):
            self.pet.apply(proposal["proposal_id"], actor="tester")
        approved = self.pet.approve(proposal["proposal_id"], actor="tester", human_approved=True)
        self.assertEqual(proposal["change_hash"], approved["approval"]["change_hash"])
        result = self.pet.apply(proposal["proposal_id"], actor="tester")
        self.assertTrue(result["result"]["passed"])
        self.assertEqual("applied", result["proposal"]["state"])
        self.assertEqual("VALUE = 2\n", (self.root / "main.py").read_text(encoding="utf-8"))
        self.assertIn("State: **applied**", (self.root / ".codepet" / "STATUS.md").read_text(encoding="utf-8"))
        self.assertIn("Update value", (self.root / ".codepet" / "MEMORY.md").read_text(encoding="utf-8"))
        self.assertTrue(self.pet.verify()["valid"])

    def test_stale_workspace_blocks_approval_and_application(self):
        proposal = self.proposal()
        (self.root / "other.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(StaleProposalError):
            self.pet.approve(proposal["proposal_id"], actor="tester", human_approved=True)

        (self.root / "other.txt").unlink()
        fresh = self.proposal("VALUE = 3\n")
        self.pet.approve(fresh["proposal_id"], actor="tester", human_approved=True)
        (self.root / "main.py").write_text("VALUE = 99\n", encoding="utf-8")
        with self.assertRaises(StaleProposalError):
            self.pet.apply(fresh["proposal_id"], actor="tester")

    def test_failed_test_rolls_back_all_affected_files(self):
        proposal = self.pet.create_proposal(
            "Exercise rollback",
            [
                {"operation": "modify", "path": "main.py", "content": "VALUE = 7\n"},
                {"operation": "create", "path": "tests/test_forced.py", "content": "import unittest\n\nclass Forced(unittest.TestCase):\n    def test_failure(self):\n        self.fail('forced')\n"},
            ],
            tests=["python-unittest"],
        )
        self.pet.approve(proposal["proposal_id"], actor="tester", human_approved=True)
        result = self.pet.apply(proposal["proposal_id"], actor="tester", timeout_seconds=30)
        self.assertFalse(result["result"]["passed"])
        self.assertEqual("rolled_back", result["proposal"]["state"])
        self.assertEqual("VALUE = 1\n", (self.root / "main.py").read_text(encoding="utf-8"))
        self.assertFalse((self.root / "tests" / "test_forced.py").exists())

    def test_tests_run_in_copy_and_required_network_isolation_fails_closed(self):
        proposal = self.pet.create_proposal(
            "Keep test side effects outside the source workspace",
            [
                {
                    "operation": "create",
                    "path": "tests/test_side_effect.py",
                    "content": "import pathlib\nimport unittest\n\nclass SideEffect(unittest.TestCase):\n    def test_write(self):\n        pathlib.Path('side-effect.txt').write_text('temporary')\n",
                }
            ],
            tests=["python-unittest"],
        )
        self.pet.approve(proposal["proposal_id"], actor="tester", human_approved=True)
        result = self.pet.apply(proposal["proposal_id"], actor="tester")
        self.assertTrue(result["result"]["passed"])
        self.assertFalse((self.root / "side-effect.txt").exists())
        self.assertTrue(result["result"]["tests"][0]["temporary_workspace_copy"])

        second = self.proposal("VALUE = 11\n")
        self.pet.approve(second["proposal_id"], actor="tester", human_approved=True)
        with patch("loom_verath.runner.IsolatedTestRunner._probe_bubblewrap", return_value=False):
            with self.assertRaises(CodePetError):
                self.pet.apply(second["proposal_id"], actor="tester", require_network_isolation=True)
        self.assertEqual("VALUE = 1\n", (self.root / "main.py").read_text(encoding="utf-8"))

    def test_paths_symlinks_secrets_and_duplicate_targets_fail_closed(self):
        cases = [
            [{"operation": "create", "path": "../escape.py", "content": "x=1\n"}],
            [{"operation": "create", "path": ".codepet/policy.json", "content": "{}\n"}],
            [{"operation": "create", "path": ".env", "content": "SAFE=1\n"}],
            [{"operation": "create", "path": "secret.py", "content": "api_key = \"abcdefghijklmnopqrstuv\"\n"}],
            [
                {"operation": "create", "path": "same.py", "content": "x=1\n"},
                {"operation": "create", "path": "same.py", "content": "x=2\n"},
            ],
        ]
        for operations in cases:
            with self.subTest(operations=operations):
                with self.assertRaises(CodePetError):
                    self.pet.create_proposal("unsafe", operations)

        outside = Path(self.temp.name) / "outside.py"
        outside.write_text("EXTERNAL = True\n", encoding="utf-8")
        (self.root / "link.py").symlink_to(outside)
        with self.assertRaises(WorkspaceBoundaryError):
            self.pet.create_proposal("follow link", [{"operation": "modify", "path": "link.py", "content": "bad\n"}])
        self.assertEqual("EXTERNAL = True\n", outside.read_text(encoding="utf-8"))

        with self.assertRaises(CodePetError):
            self.pet.create_proposal(
                "undertested Python",
                [{"operation": "modify", "path": "main.py", "content": "VALUE = 8\n"}],
                tests=["workspace-integrity"],
            )

    def test_proposal_and_journal_tampering_are_detected(self):
        proposal = self.proposal()
        plan_path = self.root / ".codepet" / "plans" / f"{proposal['proposal_id']}.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        plan["operations"][0]["content"] = "VALUE = 1000\n"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        with self.assertRaises(CodePetError):
            self.pet.load_proposal(proposal["proposal_id"])

        lines = self.pet.journal_path.read_text(encoding="utf-8").splitlines()
        event = json.loads(lines[0])
        event["event_type"] = "forged"
        lines[0] = json.dumps(event)
        self.pet.journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertFalse(self.pet.verify_journal()["valid"])

    def test_deterministic_provider_output_is_locally_revalidated(self):
        provider = DeterministicProvider(
            {
                "operations": [{"operation": "modify", "path": "main.py", "content": "VALUE = 4\n"}],
                "tests": ["python-compile"],
                "rationale": "fixture",
                "risks": [],
            }
        )
        proposal = ProviderProposalService(self.pet).propose(provider, "Update value", context_paths=["main.py"])
        self.assertEqual("deterministic_provider", proposal["source"])
        self.assertFalse(proposal["provider"]["external"])

        unsafe = DeterministicProvider({"operations": [{"operation": "create", "path": "../bad", "content": "x"}]})
        with self.assertRaises(WorkspaceBoundaryError):
            ProviderProposalService(self.pet).propose(unsafe, "escape", context_paths=[])

    def test_external_provider_requires_https_allowlist_and_consent(self):
        with self.assertRaises(CodePetError):
            OpenAICompatibleProvider(endpoint="http://example.test/v1", model="x", api_key_env="TEST_KEY", allowed_hosts={"example.test"})
        with self.assertRaises(CodePetError):
            OpenAICompatibleProvider(endpoint="https://other.test/v1", model="x", api_key_env="TEST_KEY", allowed_hosts={"example.test"})
        provider = OpenAICompatibleProvider(endpoint="https://example.test/v1", model="x", api_key_env="TEST_KEY", allowed_hosts={"example.test"})
        with self.assertRaises(CodePetError):
            provider.complete(ProviderRequest("task", ()), consent=False)

    def test_anthropic_provider_requires_https_allowlist_and_consent(self):
        with self.assertRaises(CodePetError):
            AnthropicMessagesProvider(endpoint="http://example.test/v1", model="x", api_key_env="TEST_KEY", allowed_hosts={"example.test"})
        with self.assertRaises(CodePetError):
            AnthropicMessagesProvider(endpoint="https://other.test/v1", model="x", api_key_env="TEST_KEY", allowed_hosts={"example.test"})
        with self.assertRaises(CodePetError):
            AnthropicMessagesProvider(endpoint="https://example.test/v1?key=1", model="x", api_key_env="TEST_KEY", allowed_hosts={"example.test"})
        with self.assertRaises(CodePetError):
            AnthropicMessagesProvider(endpoint="https://example.test/v1", model="x", api_key_env="not an identifier", allowed_hosts={"example.test"})
        with self.assertRaises(CodePetError):
            AnthropicMessagesProvider(endpoint="https://example.test/v1", model="x", api_key_env="TEST_KEY", allowed_hosts={"example.test"}, max_tokens=0)
        with self.assertRaises(CodePetError):
            AnthropicMessagesProvider(endpoint="https://example.test/v1", model="x", api_key_env="TEST_KEY", allowed_hosts={"example.test"}, anthropic_version="bad\"version")
        provider = AnthropicMessagesProvider(endpoint="https://example.test/v1", model="x", api_key_env="TEST_KEY", allowed_hosts={"example.test"})
        self.assertEqual("anthropic-messages", provider.name)
        self.assertTrue(provider.external)
        with self.assertRaises(CodePetError):
            provider.complete(ProviderRequest("task", ()), consent=False)

    def _anthropic_test_provider(self) -> AnthropicMessagesProvider:
        return AnthropicMessagesProvider(
            endpoint="https://api.anthropic.com/v1/messages",
            model="claude-test",
            api_key_env="TEST_ANTHROPIC_KEY",
            allowed_hosts={"api.anthropic.com"},
        )

    def test_anthropic_envelope_parsing(self):
        payload = {"content": [{"type": "text", "text": "{\"operations\":[]}"}, {"type": "thinking", "thinking": "skip"}]}
        captured = {}

        def fake_post(endpoint, body, headers, timeout_seconds):
            captured["endpoint"] = endpoint
            captured["body"] = json.loads(body)
            captured["headers"] = headers
            return json.dumps(payload).encode("utf-8")

        provider = self._anthropic_test_provider()
        with patch.dict(os.environ, {"TEST_ANTHROPIC_KEY": "test-key-value"}), patch("loom_verath.providers._post_json", side_effect=fake_post):
            response = provider.complete(ProviderRequest("task", ()), consent=True)
        self.assertEqual("{\"operations\":[]}", response.content)
        self.assertEqual("claude-test", response.model)
        self.assertEqual("anthropic-messages", response.provider)
        self.assertEqual("https://api.anthropic.com/v1/messages", captured["endpoint"])
        self.assertEqual("test-key-value", captured["headers"]["x-api-key"])
        self.assertEqual("2023-06-01", captured["headers"]["anthropic-version"])
        self.assertEqual("claude-test", captured["body"]["model"])
        self.assertEqual(provider.system_prompt, captured["body"]["system"])
        self.assertEqual(1, len(captured["body"]["messages"]))
        self.assertEqual(0, captured["body"]["temperature"])

    def test_anthropic_invalid_envelopes_fail_closed(self):
        for payload in [
            b"not json",
            {"content": []},
            {"content": [{"type": "text", "text": 42}]},
            {"unexpected": True},
        ]:
            provider = self._anthropic_test_provider()
            with patch.dict(os.environ, {"TEST_ANTHROPIC_KEY": "k"}), patch(
                "loom_verath.providers._post_json",
                side_effect=lambda *a, **k: payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8"),
            ):
                with self.assertRaises(CodePetError):
                    provider.complete(ProviderRequest("task", ()), consent=True)

    def test_anthropic_missing_credential_fails_closed(self):
        provider = self._anthropic_test_provider()
        env = {k: v for k, v in os.environ.items() if k != "TEST_ANTHROPIC_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(CodePetError):
                provider.complete(ProviderRequest("task", ()), consent=True)

    def test_provider_factories_pin_official_hosts(self):
        chatgpt = chatgpt_provider()
        self.assertEqual("https://api.openai.com/v1/chat/completions", chatgpt.endpoint)
        self.assertEqual("OPENAI_API_KEY", chatgpt.api_key_env)
        self.assertTrue(chatgpt.external)

        claude = claude_provider()
        self.assertIsInstance(claude, AnthropicMessagesProvider)
        self.assertEqual("https://api.anthropic.com/v1/messages", claude.endpoint)
        self.assertEqual("ANTHROPIC_API_KEY", claude.api_key_env)
        self.assertTrue(claude.external)

    def test_external_providers_flow_through_proposal_service_as_untrusted(self):
        provider = DeterministicProvider(
            {
                "operations": [{"operation": "modify", "path": "main.py", "content": "VALUE = 7\n"}],
                "tests": ["python-compile"],
                "rationale": "fixture",
                "risks": [],
            }
        )
        proposal = ProviderProposalService(self.pet).propose(provider, "bump", context_paths=[])
        self.assertEqual("deterministic_provider", proposal["source"])
        self.assertEqual("awaiting_review", proposal["state"])

        claude = claude_provider()
        self.assertTrue(claude.external)
        with self.assertRaises(CodePetError):
            ProviderProposalService(self.pet).propose(claude, "bump", context_paths=[], external_consent=False)

    def test_pet_cli_does_not_create_unrelated_runtime(self):
        runtime_path = Path(self.temp.name) / "must-not-exist"
        output = StringIO()
        with redirect_stdout(output):
            result = main(["--data-dir", str(runtime_path), "pet-verify", str(self.root)])
        self.assertEqual(0, result)
        self.assertFalse(runtime_path.exists())
        self.assertTrue(json.loads(output.getvalue())["valid"])


class CodePetServiceTests(unittest.TestCase):
    def test_authenticated_http_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("VALUE = 1\n", encoding="utf-8")
            server, token = build_server(root, port=0, token="a" * 32)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            try:
                connection.request("GET", "/api/health")
                response = connection.getresponse()
                self.assertEqual(200, response.status)
                response.read()

                connection.request("GET", "/api/proposals")
                response = connection.getresponse()
                self.assertEqual(401, response.status)
                response.read()

                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                body = json.dumps({"task": "update", "operations": [{"operation": "modify", "path": "main.py", "content": "VALUE = 2\n"}], "tests": ["python-compile"]})
                connection.request("POST", "/api/proposals", body=body, headers=headers)
                response = connection.getresponse()
                self.assertEqual(201, response.status)
                proposal = json.loads(response.read())

                connection.request("POST", f"/api/proposals/{proposal['proposal_id']}/approve", body=json.dumps({"approved": True, "actor": "tester"}), headers=headers)
                response = connection.getresponse()
                self.assertEqual(200, response.status)
                response.read()

                connection.request("POST", f"/api/proposals/{proposal['proposal_id']}/apply", body=json.dumps({"actor": "tester"}), headers=headers)
                response = connection.getresponse()
                self.assertEqual(200, response.status)
                result = json.loads(response.read())
                self.assertTrue(result["result"]["passed"])
                self.assertEqual("VALUE = 2\n", (root / "main.py").read_text(encoding="utf-8"))
            finally:
                connection.close()
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_remote_binding_requires_explicit_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(CodePetError):
                build_server(Path(directory), host="0.0.0.0", port=0, token="a" * 32)


if __name__ == "__main__":
    unittest.main()
