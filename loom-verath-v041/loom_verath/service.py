from __future__ import annotations

import hmac
import json
import secrets
import threading
import time
from collections import defaultdict, deque
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .codepet import CodePetWorkspace
from .errors import CodePetError


DASHBOARD = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LOOM CodePet</title><style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#141b31;--ink:#eef3ff;--muted:#9aa8c7;--accent:#8b7cff;--ok:#63d8a5;--line:#293352}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top,#202957,var(--bg) 45%);color:var(--ink);font:15px system-ui,sans-serif}main{max-width:980px;margin:auto;padding:32px 18px 72px}h1{font-size:clamp(28px,5vw,52px);margin:.2em 0}p{color:var(--muted)}section{background:color-mix(in srgb,var(--panel) 92%,transparent);border:1px solid var(--line);border-radius:16px;padding:18px;margin:16px 0}label{display:block;margin:10px 0 5px}input,textarea,select,button{font:inherit;border-radius:9px;border:1px solid var(--line);padding:10px;background:#0d1428;color:var(--ink)}input,textarea{width:100%}textarea{min-height:150px;font-family:ui-monospace,monospace}button{cursor:pointer;background:var(--accent);border:0;font-weight:700;margin:8px 6px 0 0}.secondary{background:#263150}pre{overflow:auto;background:#090e1c;border-radius:10px;padding:12px;white-space:pre-wrap}.tag{display:inline-block;color:var(--ok);border:1px solid var(--ok);border-radius:20px;padding:3px 9px}.proposal{border-top:1px solid var(--line);padding:12px 0}.proposal:first-child{border:0}
</style></head><body><main><span class="tag">local · review gated</span><h1>LOOM CodePet</h1><p>Inspect, propose, approve, test, and roll back. No proposal can write until its exact change hash is approved.</p>
<section><h2>Connection</h2><label for="token">Bearer token</label><input id="token" type="password" autocomplete="off"><button onclick="refreshAll()">Connect</button><pre id="status">Not connected.</pre></section>
<section><h2>New typed proposal</h2><label for="task">Task</label><input id="task" placeholder="Add a tested greeting function"><label for="ops">Operations JSON</label><textarea id="ops">[{"operation":"create","path":"example.txt","content":"hello\n"}]</textarea><label for="tests">Test profiles</label><input id="tests" value="workspace-integrity"><button onclick="createProposal()">Create review</button><pre id="result"></pre></section>
<section><h2>Proposals</h2><div id="proposals"></div></section>
<script>
const auth=()=>({"Authorization":"Bearer "+document.querySelector('#token').value,"Content-Type":"application/json"});
async function api(path,options={}){const response=await fetch(path,{...options,headers:{...auth(),...(options.headers||{})}});const data=await response.json();if(!response.ok)throw new Error(data.error||response.statusText);return data}
async function refreshAll(){try{const [health,items]=await Promise.all([api('/api/health'),api('/api/proposals')]);document.querySelector('#status').textContent=JSON.stringify(health,null,2);document.querySelector('#proposals').innerHTML=items.map(p=>`<div class="proposal"><b>${escapeHtml(p.task)}</b><p>${p.state} · ${p.proposal_id}</p><button onclick="approve('${p.proposal_id}')">Approve</button><button onclick="applyProposal('${p.proposal_id}')">Apply + test</button><button class="secondary" onclick="showProposal('${p.proposal_id}')">Inspect</button></div>`).join('')||'<p>No proposals.</p>'}catch(e){document.querySelector('#status').textContent=e.message}}
async function createProposal(){try{const body={task:document.querySelector('#task').value,operations:JSON.parse(document.querySelector('#ops').value),tests:document.querySelector('#tests').value.split(',').map(x=>x.trim()).filter(Boolean)};const value=await api('/api/proposals',{method:'POST',body:JSON.stringify(body)});document.querySelector('#result').textContent=value.diff;refreshAll()}catch(e){document.querySelector('#result').textContent=e.message}}
async function approve(id){try{await api(`/api/proposals/${id}/approve`,{method:'POST',body:JSON.stringify({approved:true,actor:'local-operator'})});refreshAll()}catch(e){alert(e.message)}}
async function applyProposal(id){try{const v=await api(`/api/proposals/${id}/apply`,{method:'POST',body:JSON.stringify({actor:'local-operator'})});document.querySelector('#result').textContent=JSON.stringify(v.result,null,2);refreshAll()}catch(e){alert(e.message)}}
async function showProposal(id){try{const v=await api(`/api/proposals/${id}`);document.querySelector('#result').textContent=JSON.stringify(v,null,2)}catch(e){alert(e.message)}}
function escapeHtml(v){const e=document.createElement('div');e.textContent=v;return e.innerHTML}
</script></main></body></html>"""


class CodePetHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, address: tuple[str, int], workspace: CodePetWorkspace, token: str):
        super().__init__(address, CodePetHandler)
        self.workspace = workspace
        self.auth_token = token
        self._rate_lock = threading.Lock()
        self._request_times: dict[str, deque[float]] = defaultdict(deque)

    def admit_request(self, client: str, *, limit: int = 120, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        with self._rate_lock:
            requests = self._request_times[client]
            while requests and requests[0] <= now - window_seconds:
                requests.popleft()
            if len(requests) >= limit:
                return False
            requests.append(now)
            return True


class CodePetHandler(BaseHTTPRequestHandler):
    server: CodePetHTTPServer
    protocol_version = "HTTP/1.1"
    MAX_BODY = 6_000_000

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, value: Any) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"), "application/json; charset=utf-8")

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.auth_token}"
        return hmac.compare_digest(supplied, expected)

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "Valid local bearer token required"})
        return False

    def _require_rate_budget(self) -> bool:
        if self.server.admit_request(self.client_address[0]):
            return True
        self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Local request-rate limit exceeded"})
        return False

    def _read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise CodePetError("Invalid Content-Length") from exc
        if length < 1 or length > self.MAX_BODY:
            raise CodePetError("JSON body is empty or exceeds the request limit")
        if self.headers.get_content_type() != "application/json":
            raise CodePetError("Content-Type must be application/json")
        try:
            value = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise CodePetError("Request body is not valid JSON") from exc
        if not isinstance(value, dict):
            raise CodePetError("Request JSON must be an object")
        return value

    @staticmethod
    def _parts(path: str) -> list[str]:
        return [part for part in path.split("/") if part]

    def _handle_error(self, exc: Exception) -> None:
        if isinstance(exc, (CodePetError, ValueError, KeyError)):
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc), "type": type(exc).__name__})
        else:
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Internal service error", "type": type(exc).__name__})

    def do_GET(self) -> None:
        if not self._require_rate_budget():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(HTTPStatus.OK, DASHBOARD.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self._json(HTTPStatus.OK, {"status": "healthy", "service": "loom-codepet", "external_provider_calls": False, "test_network_os_enforced": False})
            return
        if not self._require_auth():
            return
        try:
            if parsed.path == "/api/manifest":
                self._json(HTTPStatus.OK, self.server.workspace.scan())
            elif parsed.path == "/api/proposals":
                self._json(HTTPStatus.OK, self.server.workspace.list_proposals())
            elif parsed.path == "/api/verify":
                self._json(HTTPStatus.OK, self.server.workspace.verify())
            else:
                parts = self._parts(parsed.path)
                if len(parts) == 3 and parts[:2] == ["api", "proposals"]:
                    self._json(HTTPStatus.OK, self.server.workspace.load_proposal(parts[2]))
                else:
                    self._json(HTTPStatus.NOT_FOUND, {"error": "Route not found"})
        except Exception as exc:
            self._handle_error(exc)

    def do_POST(self) -> None:
        if not self._require_rate_budget():
            return
        parsed = urlparse(self.path)
        if not self._require_auth():
            return
        try:
            body = self._read_json()
            parts = self._parts(parsed.path)
            if parsed.path == "/api/proposals":
                value = self.server.workspace.create_proposal(
                    body.get("task", ""),
                    body.get("operations"),
                    tests=body.get("tests"),
                    rationale=body.get("rationale", ""),
                    risks=body.get("risks", []),
                )
                self._json(HTTPStatus.CREATED, value)
                return
            if len(parts) != 4 or parts[:2] != ["api", "proposals"]:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Route not found"})
                return
            proposal_id, action = parts[2], parts[3]
            if action == "approve":
                value = self.server.workspace.approve(proposal_id, actor=body.get("actor", ""), human_approved=body.get("approved") is True)
            elif action == "reject":
                value = self.server.workspace.reject(proposal_id, actor=body.get("actor", ""), reason=body.get("reason", ""))
            elif action == "apply":
                value = self.server.workspace.apply(
                    proposal_id,
                    actor=body.get("actor", ""),
                    timeout_seconds=int(body.get("timeout_seconds", 120)),
                    require_network_isolation=body.get("require_network_isolation") is True,
                )
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Route not found"})
                return
            self._json(HTTPStatus.OK, value)
        except Exception as exc:
            self._handle_error(exc)


def build_server(
    workspace: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    token: str | None = None,
    allow_remote: bool = False,
) -> tuple[CodePetHTTPServer, str]:
    loopback = host in {"127.0.0.1", "localhost", "::1"}
    if not loopback and not allow_remote:
        raise CodePetError("Non-loopback binding requires explicit allow_remote authorization")
    if not 0 <= port <= 65535:
        raise CodePetError("Port must be in [0, 65535]")
    auth_token = token or secrets.token_urlsafe(32)
    if len(auth_token) < 24:
        raise CodePetError("Service token must contain at least 24 characters")
    pet = CodePetWorkspace(workspace)
    pet.initialize()
    return CodePetHTTPServer((host, port), pet, auth_token), auth_token
