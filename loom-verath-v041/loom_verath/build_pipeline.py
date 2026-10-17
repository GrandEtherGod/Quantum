"""Dependency-aware fixed-profile mechanic acceptance runner."""
from __future__ import annotations

import json
import uuid
import os
from pathlib import Path

from .bionemo import BioNeMoResearch, preflight
from .mechanics import JintaiHands, VoxParser, tesseract_geometry
from .models import EvidenceState
from .utils import canonical_json, load_json, sha256_hex


class MechanicBuild:
    def __init__(self, runtime):
        self.runtime = runtime
        self.stages = load_json(Path(__file__).parent / "config" / "mechanic_stages.json")
        seen = set()
        for stage in self.stages:
            if stage["id"] in seen or any(dep not in seen for dep in stage["depends_on"]):
                raise ValueError("Mechanic stages must form an ordered acyclic dependency graph")
            seen.add(stage["id"])

    def plan(self) -> dict:
        return {"scope": "LOOM / VERATH / CHRYSALIS", "stages": self.stages,
                "note": "Implementation status is distinct from acceptance evidence; run build-run to check"}

    def _check(self, name: str, run_id: str) -> dict:
        runtime = self.runtime
        if name == "core":
            if not runtime.verify()["valid"]:
                raise ValueError("Core integrity verification failed")
            return {"integrity": True, "canonical_layers": runtime.layers.summary()["total"]}
        if name == "memory":
            text = f"Mechanic acceptance continuity marker {run_id}"
            episode = runtime.memory.add_episode(text, session_id=run_id, kind="note", importance=0.9,
                                                 evidence_state=EvidenceState.SUPPORTED)
            try:
                found = runtime.memory.search(run_id)
                if not any(r["content"] == text for r in found):
                    raise ValueError("Memory retrieval failed")
                row = runtime.database.connection.execute("SELECT ciphertext FROM episodes WHERE episode_id=?", (episode,)).fetchone()
                if text.encode() in row["ciphertext"]:
                    raise ValueError("Memory was stored in plaintext")
            finally:
                runtime.memory.tombstone(episode, actor="mechanic-build", reason="acceptance_marker_cleanup")
            return {"encrypted_roundtrip": True, "test_marker_removed": True}
        if name in {"vox", "hands", "simulation"}:
            command = (JintaiHands.parse({"gesture": "open_palm", "confidence": 0.95, "radius": 4})
                       if name == "hands" else VoxParser.parse("dome radius 4" if name == "simulation" else "fireball radius 4"))
            result = runtime.run(command.text, actor="mechanic-build", requested_mode=command.mode)
            expected = "thermal_event_visualization" if name == "vox" else "procedural_geometry_blueprint"
            if result.output.get("artifact_type") != expected or result.output.get("external_effects") is not False:
                raise ValueError("Mechanic escaped declared simulation profile")
            if name == "simulation":
                geometry = tesseract_geometry(4)
                if len(geometry["vertices_3d"]) != 16 or len(geometry["edges"]) != 32:
                    raise ValueError("Geometry topology failed")
                return {"session_id": result.session_id, "geometry": geometry}
            return {"session_id": result.session_id, "input": command.to_dict(), "output": result.output}
        if name == "bio_prepare":
            # Short instructional sequence from the plugin example; no biological target selected.
            result = BioNeMoResearch(runtime).prepare("MTEYKLVVVGACGVGKSALTIQLIQNHFVDEYDPT")
            return {k: v for k, v in result.items() if k != "payload"} | {"input_kind": "instructional_sequence", "preflight": preflight()}
        if name == "witness":
            if not runtime.verify()["valid"]:
                raise ValueError("Post-mechanic witness verification failed")
            return {"integrity": True, "ledger_root": runtime.ledger.last_hash()}
        raise ValueError("Unknown fixed acceptance profile")

    def _run_isolated(self, *, through: str | None = None) -> dict:
        """Run the pipeline against a fresh temporary runtime.

        Each isolated run gets its own data directory, database, keys, and
        ledger, so no state accumulates across runs. The report is embedded in
        the returned summary because the temporary directory is removed.
        """
        import tempfile

        from .runtime import LoomVerathRuntime

        temporary = tempfile.TemporaryDirectory(prefix="mechanic-build-")
        try:
            isolated_runtime = LoomVerathRuntime(temporary.name)
            try:
                result = MechanicBuild(isolated_runtime).run(through=through)
            finally:
                isolated_runtime.close()
            report_path = result.get("report_path")
            if report_path:
                try:
                    result["report"] = json.loads(Path(report_path).read_text())
                except OSError:
                    result["report"] = None
            result["isolated"] = True
            result["report_ephemeral"] = True
            return result
        finally:
            temporary.cleanup()

    def run(self, *, through: str | None = None, isolated: bool = False) -> dict:
        """Run the fixed local mechanic acceptance pipeline.

        With isolated=True, the stages run against a fresh temporary runtime so
        per-run state (ledger growth, episode tombstones, reports) cannot leak
        across runs and drift timing. The caller's runtime is left untouched.
        Default False preserves the historical in-place behavior.
        """
        if isolated:
            return self._run_isolated(through=through)
        if through is not None and through not in {s["id"] for s in self.stages}:
            raise ValueError("Unknown --through stage")
        run_id = str(uuid.uuid4())
        statuses, results = {}, []
        stopped = False
        for stage in self.stages:
            name = stage["id"]
            result = {"stage": name, "lane": stage["lane"], "implementation": stage["implementation"]}
            if stopped:
                result.update(status="pending", reason="outside_requested_prefix")
            elif any(statuses.get(dep) != "passed" for dep in stage["depends_on"]):
                result.update(status="blocked", reason="dependency_not_passed")
            elif stage["profile"] is None:
                result.update(status="blocked" if name == "bio_live" else "planned", reason=stage["blocker"])
            else:
                runtime_event = {"run_id": run_id, "stage": name}
                self.runtime.ledger.append("mechanic_stage_started", runtime_event)
                try:
                    evidence = self._check(stage["profile"], run_id)
                    result.update(status="passed", evidence=evidence)
                except Exception as exc:
                    # Do not log input, sequence, or provider error details.
                    result.update(status="failed", reason=type(exc).__name__)
                self.runtime.ledger.append("mechanic_stage_completed", {
                    **runtime_event, "status": result["status"], "evidence_hash": sha256_hex(canonical_json(result))})
            statuses[name] = result["status"]
            results.append(result)
            if name == through:
                stopped = True
        summary = {"run_id": run_id, "stages": results,
                   "local_acceptance_passed": all(r["status"] == "passed" for r in results if r["implementation"] == "implemented" and r["status"] != "pending"),
                   "entire_design_complete": all(r["status"] == "passed" for r in results),
                   "network_used": False, "hardware_actuation": False,
                   "scope": "fixed local checks; no speech, camera, biological inference, or physical actuation"}
        report_dir = self.runtime.data_dir / "mechanic_builds"
        report_dir.mkdir(exist_ok=True, mode=0o700)
        report_path = report_dir / f"{run_id}.json"
        summary["report_path"] = str(report_path)
        fd = os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(canonical_json(summary))
        self.runtime.ledger.append("mechanic_build_completed", {"run_id": run_id,
            "summary_hash": sha256_hex(canonical_json(summary)), "entire_design_complete": summary["entire_design_complete"]})
        return summary
