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


MAX_PROVIDER_RESPONSE_BYTES = 2_000_000


def _validate_provider_endpoint(endpoint: str, allowed_hosts: set[str]) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname not in allowed_hosts:
        raise CodePetError("Provider endpoint must be HTTPS and explicitly host-allowlisted")
    if parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise CodePetError("Provider endpoint cannot contain credentials, a query, or a fragment")


def _validate_provider_options(api_key_env: str, timeout_seconds: int) -> None:
    if not api_key_env.isidentifier():
        raise CodePetError("api_key_env must be an environment-variable identifier")
    if not 1 <= timeout_seconds <= 120:
        raise CodePetError("Provider timeout must be in [1, 120]")


def _post_json(endpoint: str, body: bytes, headers: dict[str, str], timeout_seconds: int) -> bytes:
    request_object = urllib.request.Request(endpoint, data=body, method="POST", headers=headers)
    try:
        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(request_object, timeout=timeout_seconds) as response:
            if response.status != 200:
                raise CodePetError(f"Provider returned HTTP {response.status}")
            raw = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
    except urllib.error.URLError as exc:
        raise CodePetError(f"Provider request failed: {exc.reason}") from exc
    if len(raw) > MAX_PROVIDER_RESPONSE_BYTES:
        raise CodePetError("Provider response exceeds the size limit")
    return raw


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
        _validate_provider_endpoint(endpoint, allowed_hosts)
        _validate_provider_options(api_key_env, timeout_seconds)
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
        raw = _post_json(
            self.endpoint,
            body,
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            self.timeout_seconds,
        )
        try:
            payload = json.loads(raw)
            content = payload["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise CodePetError("Provider returned an invalid completion envelope") from exc
        if not isinstance(content, str):
            raise CodePetError("Provider completion content must be text")
        return ProviderResponse(content, self.model, self.name)


class AnthropicMessagesProvider:
    """Minimal opt-in adapter for the Anthropic Messages API (Claude)."""

    name = "anthropic-messages"
    external = True

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key_env: str,
        allowed_hosts: set[str],
        timeout_seconds: int = 45,
        max_tokens: int = 4096,
        anthropic_version: str = "2023-06-01",
        system_prompt: str | None = None,
    ):
        _validate_provider_endpoint(endpoint, allowed_hosts)
        _validate_provider_options(api_key_env, timeout_seconds)
        if not 1 <= max_tokens <= 200_000:
            raise CodePetError("max_tokens must be in [1, 200000]")
        if not anthropic_version or any(ch in anthropic_version for ch in "\"' \t\r\n"):
            raise CodePetError("anthropic_version must be a plain header token")
        self.endpoint = endpoint
        self.model = model
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.anthropic_version = anthropic_version
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
                "max_tokens": self.max_tokens,
                "temperature": 0,
                "system": self.system_prompt,
                "messages": [
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
            }
        ).encode("utf-8")
        raw = _post_json(
            self.endpoint,
            body,
            {
                "x-api-key": api_key,
                "anthropic-version": self.anthropic_version,
                "Content-Type": "application/json",
            },
            self.timeout_seconds,
        )
        try:
            payload = json.loads(raw)
            blocks = payload["content"]
            if not isinstance(blocks, list) or not blocks:
                raise KeyError("content")
            parts = [block["text"] for block in blocks if isinstance(block, dict) and block.get("type") == "text"]
            content = "".join(part for part in parts if isinstance(part, str))
            if not content:
                raise CodePetError("Provider returned no text content")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise CodePetError("Provider returned an invalid completion envelope") from exc
        return ProviderResponse(content, self.model, self.name)


def chatgpt_provider(
    *, model: str = "gpt-5", api_key_env: str = "OPENAI_API_KEY"
) -> OpenAICompatibleProvider:
    """Build a ChatGPT (OpenAI) provider for the proposal/loop boundary (no call is made).

    Constructing this object performs no network access and reads no credential;
    the allowlist pins the endpoint to the official OpenAI API host.
    """
    return OpenAICompatibleProvider(
        endpoint="https://api.openai.com/v1/chat/completions",
        model=model,
        api_key_env=api_key_env,
        allowed_hosts={"api.openai.com"},
    )


def claude_provider(
    *, model: str = "claude-sonnet-4-5", api_key_env: str = "ANTHROPIC_API_KEY"
) -> AnthropicMessagesProvider:
    """Build a Claude (Anthropic) provider for the proposal/loop boundary (no call is made).

    Constructing this object performs no network access and reads no credential;
    the allowlist pins the endpoint to the official Anthropic API host. The exact
    served model id must be confirmed against the provider's model list at first
    live use.
    """
    return AnthropicMessagesProvider(
        endpoint="https://api.anthropic.com/v1/messages",
        model=model,
        api_key_env=api_key_env,
        allowed_hosts={"api.anthropic.com"},
    )


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
