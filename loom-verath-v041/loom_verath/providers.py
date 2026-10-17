from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlparse

from .codepet import CodePetWorkspace
from .errors import CodePetError


SYSTEM_PROMPT = """You are a bounded coding proposal generator. Return one JSON object only.
Schema: {"operations":[{"operation":"create|modify|delete","path":"relative/posix/path","content":"full UTF-8 replacement or omit for delete"}],"tests":["workspace-integrity|python-compile|python-unittest|python-pytest|npm-test"],"rationale":"short text","risks":["short text"]}.
Never emit shell commands, absolute paths, traversal, credentials, network actions, or changes to .git, .codepet, .env, keys, or certificates. Use only supplied context. A proposal has no authority until separately approved and applied."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class ProviderRequest:
    task: str
    context: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    model: str
    provider: str


class ModelProvider(Protocol):
    name: str
    external: bool

    def complete(self, request: ProviderRequest, *, consent: bool = False) -> ProviderResponse:
        ...


class DeterministicProvider:
    """Offline provider used for boundary tests and explicit fixture proposals."""

    name = "deterministic"
    external = False

    def __init__(self, response: dict[str, Any]):
        self.response = response

    def complete(self, request: ProviderRequest, *, consent: bool = False) -> ProviderResponse:
        return ProviderResponse(json.dumps(self.response), "fixture-v1", self.name)


class OpenAICompatibleProvider:
    """Minimal opt-in adapter for an explicitly allowlisted HTTPS endpoint."""

    name = "openai-compatible"
    external = True

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key_env: str,
        allowed_hosts: set[str],
        timeout_seconds: int = 45,
        system_prompt: str | None = None,
    ):
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.hostname or parsed.hostname not in allowed_hosts:
            raise CodePetError("Provider endpoint must be HTTPS and explicitly host-allowlisted")
        if parsed.username or parsed.password or parsed.fragment or parsed.query:
            raise CodePetError("Provider endpoint cannot contain credentials, a query, or a fragment")
        if not api_key_env.isidentifier():
            raise CodePetError("api_key_env must be an environment-variable identifier")
        if not 1 <= timeout_seconds <= 120:
            raise CodePetError("Provider timeout must be in [1, 120]")
        self.endpoint = endpoint
        self.model = model
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds
        self.system_prompt = SYSTEM_PROMPT if system_prompt is None else system_prompt

    def complete(self, request: ProviderRequest, *, consent: bool = False) -> ProviderResponse:
        if consent is not True:
            raise CodePetError("Affirmative consent is required before an external model call")
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise CodePetError(f"Provider credential environment variable is unavailable: {self.api_key_env}")
        user_payload = {"task": request.task, "selected_context": list(request.context)}
        body = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
            }
        ).encode("utf-8")
        request_object = urllib.request.Request(
            self.endpoint,
            data=body,
            method="POST",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        try:
            opener = urllib.request.build_opener(_NoRedirect)
            with opener.open(request_object, timeout=self.timeout_seconds) as response:
                if response.status != 200:
                    raise CodePetError(f"Provider returned HTTP {response.status}")
                raw = response.read(2_000_001)
        except urllib.error.URLError as exc:
            raise CodePetError(f"Provider request failed: {exc.reason}") from exc
        if len(raw) > 2_000_000:
            raise CodePetError("Provider response exceeds the size limit")
        try:
            payload = json.loads(raw)
            content = payload["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise CodePetError("Provider returned an invalid completion envelope") from exc
        if not isinstance(content, str):
            raise CodePetError("Provider completion content must be text")
        return ProviderResponse(content, self.model, self.name)


class ProviderProposalService:
    """Transforms untrusted provider output into a locally validated proposal."""

    def __init__(self, workspace: CodePetWorkspace):
        self.workspace = workspace

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        value = content.strip()
        if value.startswith("```"):
            lines = value.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                value = "\n".join(lines[1:-1])
                if value.lstrip().startswith("json"):
                    value = value.lstrip()[4:].lstrip()
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise CodePetError("Provider output is not a JSON object") from exc
        if not isinstance(parsed, dict):
            raise CodePetError("Provider output must be a JSON object")
        return parsed

    def propose(
        self,
        provider: ModelProvider,
        task: str,
        *,
        context_paths: list[str],
        external_consent: bool = False,
    ) -> dict[str, Any]:
        task = self.workspace.validate_prompt(task, name="provider task")
        context = tuple(self.workspace.read_context(context_paths))
        response = provider.complete(ProviderRequest(task=task, context=context), consent=external_consent)
        payload = self._parse_json_object(response.content)
        proposal = self.workspace.create_proposal(
            task,
            payload.get("operations"),
            tests=payload.get("tests"),
            rationale=payload.get("rationale", ""),
            risks=payload.get("risks", []),
            source="external_provider" if provider.external else "deterministic_provider",
        )
        proposal["provider"] = {"name": response.provider, "model": response.model, "external": provider.external}
        return proposal
