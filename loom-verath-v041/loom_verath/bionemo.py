"""Explicit, bounded BioNeMo NIM boundary. Defaults to offline preparation."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from .utils import canonical_json, sha256_hex

ENDPOINT = "https://health.api.nvidia.com/v1/biology/mit/boltz2/predict"
DOCS = "https://docs.nvidia.com/nim/bionemo/boltz2/latest/inference.html"
MAX_RESPONSE_BYTES = 32 * 1024 * 1024


def preflight() -> dict:
    return {"hosted_key_present": bool(os.environ.get("NGC_API_KEY") or os.environ.get("NVIDIA_API_KEY")),
            "nvidia_smi_present": shutil.which("nvidia-smi") is not None,
            "docker_present": shutil.which("docker") is not None,
            "network_connectivity": "not_probed", "live_inference": "not_run"}


def protein_request(sequence: str) -> dict:
    if not isinstance(sequence, str) or not re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWYX]{1,4096}", sequence):
        raise ValueError("Supply 1–4096 uppercase protein residues; invalid residues are rejected")
    return {"polymers": [{"id": "A", "molecule_type": "protein", "sequence": sequence}],
            "recycling_steps": 3, "sampling_steps": 50, "diffusion_samples": 1,
            "output_format": "mmcif"}


def validate_protein_request(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Request must be a JSON object")
    try:
        sequence = payload["polymers"][0]["sequence"]
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError("Expected one protein polymer") from exc
    expected = protein_request(sequence)
    if payload != expected:
        raise ValueError("This adapter accepts the bounded single-protein profile only")
    return expected


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("BioNeMo endpoint redirects are disabled")


def _post(payload: dict, key: str) -> dict:
    request = urllib.request.Request(ENDPOINT, data=canonical_json(payload).encode(),
                                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
                                    method="POST")
    # Do not inherit a proxy that could receive a research sequence or credential.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    try:
        with opener.open(request, timeout=300) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        raise ValueError(f"BioNeMo returned HTTP {exc.code}; response body suppressed") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError("BioNeMo connection failed; credentials and response details suppressed") from None
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("BioNeMo response exceeded 32 MiB")
    try:
        return json.loads(data)
    except (ValueError, UnicodeError):
        raise ValueError("BioNeMo response was not valid JSON") from None


def validate_response(result: dict) -> dict:
    if not isinstance(result, dict) or not isinstance(result.get("structures"), list) or not result["structures"]:
        raise ValueError("BioNeMo response has no structure records")
    structures, scores = result["structures"], result.get("confidence_scores")
    if len(structures) != 1 or not isinstance(scores, list) or len(scores) != len(structures):
        raise ValueError("Unexpected structure/confidence count for single-sample profile")
    for score in scores:
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Invalid model confidence")
    for record in structures:
        if not isinstance(record, dict) or record.get("format") != "mmcif" or not isinstance(record.get("structure"), str):
            raise ValueError("Expected mmCIF structure text")
        if not record["structure"].lstrip().startswith("data_") or "_atom_site." not in record["structure"]:
            raise ValueError("Structure lacks mmCIF atom-site content")
    return {"structures": structures, "confidence_scores": scores}


class BioNeMoResearch:
    def __init__(self, runtime):
        self.runtime = runtime

    def prepare(self, sequence: str) -> dict:
        payload = protein_request(sequence)
        digest = sha256_hex(canonical_json(payload))
        self.runtime.ledger.append("bionemo_request_prepared", {
            "request_hash": digest, "residue_count": len(sequence), "authority": "research_only",
            "network_used": False, "model": "boltz2", "schema_source": DOCS})
        return {"status": "prepared", "payload": payload, "request_hash": digest,
                "authority": "research_only", "network_used": False, "inference_run": False}

    def predict(self, payload: dict, *, allow_network: bool = False) -> dict:
        payload = validate_protein_request(payload)
        digest = sha256_hex(canonical_json(payload))
        if not allow_network:
            self.runtime.ledger.append("bionemo_request_blocked", {"request_hash": digest, "reason": "network_opt_in_required"})
            raise ValueError("Live BioNeMo prediction requires explicit --allow-network")
        key = os.environ.get("NGC_API_KEY") or os.environ.get("NVIDIA_API_KEY")
        if not key:
            self.runtime.ledger.append("bionemo_request_blocked", {"request_hash": digest, "reason": "missing_credential"})
            raise ValueError("Set NGC_API_KEY or NVIDIA_API_KEY privately in the environment")
        token = self.runtime.capabilities.issue(principal="bionemo-research", actions={"bionemo.predict"},
            resource=digest, ttl_seconds=360, risk="medium", human_approved=True)
        authorized = self.runtime.capabilities.authorize(token, "bionemo.predict", digest)
        run_id = str(uuid.uuid4())
        self.runtime.ledger.append("bionemo_prediction_started", {"run_id": run_id,
            "request_hash": digest, "network_used": True, "authority": "research_only"})
        output_dir = None
        try:
            raw = _post(payload, key)
            checked = validate_response(raw)
            output_dir = self.runtime.data_dir / "bionemo" / run_id
            output_dir.mkdir(parents=True, mode=0o700)
            files = []
            for index, record in enumerate(checked["structures"], 1):
                path = output_dir / f"structure_{index}.cif"
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(record["structure"])
                files.append({"path": str(path), "sha256": sha256_hex(record["structure"])})
            raw_path = output_dir / "response.json"
            fd = os.open(raw_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(canonical_json(raw))
            summary = {"run_id": run_id, "status": "predicted_unreviewed", "authority": "research_only",
                "evidence_state": "plausible", "evidence_kind": "model_prediction", "network_used": True, "inference_run": True,
                "request_hash": digest, "response_hash": sha256_hex(canonical_json(raw)),
                "confidence_scores": checked["confidence_scores"], "structures": files,
                "raw_response_path": str(raw_path), "product_authority": False,
                "model_version": "provider_not_attested", "note": "Model confidence is not experimental validation"}
            self.runtime.ledger.append("bionemo_prediction_completed", {
                "run_id": run_id, "request_hash": digest, "response_hash": summary["response_hash"],
                "authority": "research_only", "review_status": "unreviewed"})
            return summary
        except Exception:
            if output_dir is not None:
                shutil.rmtree(output_dir, ignore_errors=True)
            self.runtime.ledger.append("bionemo_prediction_failed", {"run_id": run_id, "request_hash": digest})
            raise
        finally:
            self.runtime.capabilities.revoke(authorized["capability_id"], actor="bionemo-research", reason="request_finished")
