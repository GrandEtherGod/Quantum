from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from .errors import LoomVerathError
from .runtime import LoomVerathRuntime
from .codepet import CodePetWorkspace
from .site_guide import SiteGuide


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="loom-verath",
        description="Auditable LOOM × VERATH trustworthy-core runtime",
    )
    parser.add_argument(
        "--data-dir", default=".runtime", help="Directory for encrypted runtime state"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init", help="Initialize and inspect the runtime")
    commands.add_parser("build-plan", help="Show all mechanic stages and blockers")
    stages = commands.add_parser("build-run", help="Run fixed local mechanic acceptance checks")
    stages.add_argument("--through", help="Run stages through this stage ID")
    stages.add_argument("--isolated", action="store_true",
                        help="Run against a fresh temporary runtime so no state leaks across runs")
    commands.add_parser("bionemo-preflight", help="Show credential/tool availability without network access")
    bio_prepare = commands.add_parser("bionemo-prepare", help="Prepare a single-protein Boltz2 research request")
    bio_prepare.add_argument("sequence_file", help="Plain uppercase protein sequence file")
    bio_predict = commands.add_parser("bionemo-predict", help="Run the bounded hosted Boltz2 research profile")
    bio_predict.add_argument("request_file", help="Prepared payload JSON or bionemo-prepare output JSON")
    bio_predict.add_argument("--allow-network", action="store_true", help="Opt in to sending this sequence to NVIDIA")
    vox = commands.add_parser("vox", help="Parse and run a bounded VOX text command")
    vox.add_argument("text")
    hands = commands.add_parser("hands", help="Run a simulated hand-controller event JSON")
    hands.add_argument("event_file")

    run = commands.add_parser("run", help="Run one bounded command")
    run.add_argument("text", nargs="+", help="Command text")
    run.add_argument(
        "--mode", choices=["analysis", "build", "memory", "simulation", "research"]
    )
    run.add_argument("--approve", action="store_true", help="Record explicit user approval")
    run.add_argument("--importance", type=float, default=0.7)

    replay = commands.add_parser("replay", help="Deterministically replay a session")
    replay.add_argument("session_id")

    commands.add_parser("verify", help="Verify ledger, lineage, state, and database")
    commands.add_parser("introspect", help="Show structured component state")

    search = commands.add_parser("memory-search", help="Search encrypted episodic memory")
    search.add_argument("query", nargs="+")
    search.add_argument("--limit", type=int, default=5)

    commands.add_parser("crystallize", help="Consolidate eligible episodes")
    commands.add_parser("snapshot", help="Create a rollback snapshot")

    rollback = commands.add_parser("rollback", help="Roll state back to a snapshot")
    rollback.add_argument("snapshot_id")
    rollback.add_argument("--approve", action="store_true", required=True)

    change = commands.add_parser("propose-change", help="Evaluate and apply a bounded state patch")
    change.add_argument("patch_json", help='JSON object, for example {"system.phi_coupling":0.62}')
    change.add_argument("--approve", action="store_true")

    commands.add_parser("layers", help="Show the grounded 28-layer registry")

    research_validate = commands.add_parser("research-validate", help="Validate an H-field experiment record")
    research_validate.add_argument("record_json")
    research_ingest = commands.add_parser("research-ingest", help="Validate and store a research-only record")
    research_ingest.add_argument("record_json")

    pet_init = commands.add_parser("pet-init", help="Initialize a file-native coding companion")
    pet_init.add_argument("workspace")
    pet_scan = commands.add_parser("pet-scan", help="Create a bounded workspace manifest")
    pet_scan.add_argument("workspace")
    pet_plan = commands.add_parser("pet-plan", help="Write a review-only task proposal")
    pet_plan.add_argument("workspace")
    pet_plan.add_argument("task", nargs="+")

    pet_propose = commands.add_parser("pet-propose", help="Create a concrete typed proposal from JSON")
    pet_propose.add_argument("workspace")
    pet_propose.add_argument("spec_json", help="Path to a proposal specification JSON file")
    pet_list = commands.add_parser("pet-list", help="List CodePet proposals")
    pet_list.add_argument("workspace")
    pet_show = commands.add_parser("pet-show", help="Inspect one CodePet proposal")
    pet_show.add_argument("workspace")
    pet_show.add_argument("proposal_id")
    pet_approve = commands.add_parser("pet-approve", help="Bind human approval to a proposal change hash")
    pet_approve.add_argument("workspace")
    pet_approve.add_argument("proposal_id")
    pet_approve.add_argument("--actor", default="founder")
    pet_approve.add_argument("--approve", action="store_true", required=True)
    pet_reject = commands.add_parser("pet-reject", help="Reject a pending or approved proposal")
    pet_reject.add_argument("workspace")
    pet_reject.add_argument("proposal_id")
    pet_reject.add_argument("--actor", default="founder")
    pet_reject.add_argument("--reason", required=True)
    pet_apply = commands.add_parser("pet-apply", help="Apply an approved proposal, test, and roll back on failure")
    pet_apply.add_argument("workspace")
    pet_apply.add_argument("proposal_id")
    pet_apply.add_argument("--actor", default="founder")
    pet_apply.add_argument("--timeout", type=int, default=120)
    pet_apply.add_argument("--require-network-isolation", action="store_true")
    pet_verify = commands.add_parser("pet-verify", help="Verify CodePet proposal and journal integrity")
    pet_verify.add_argument("workspace")
    pet_serve = commands.add_parser("pet-serve", help="Run the authenticated local CodePet dashboard/API")
    pet_serve.add_argument("workspace")
    pet_serve.add_argument("--host", default="127.0.0.1")
    pet_serve.add_argument("--port", type=int, default=8765)
    pet_serve.add_argument("--token-env", help="Environment variable containing the bearer token")
    pet_serve.add_argument("--allow-remote", action="store_true")

    guide = commands.add_parser("site-guide", help="Read or export a canonical public-safe guide context")
    guide.add_argument("content_id", choices=["field", "thesis", "systems", "repository", "consultation"])
    guide.add_argument("--export")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime: LoomVerathRuntime | None = None
    try:
        if args.command == "pet-init":
            _print(CodePetWorkspace(Path(args.workspace)).initialize())
        elif args.command == "pet-scan":
            _print(CodePetWorkspace(Path(args.workspace)).scan())
        elif args.command == "pet-plan":
            _print(CodePetWorkspace(Path(args.workspace)).propose(" ".join(args.task)))
        elif args.command == "pet-propose":
            with Path(args.spec_json).open("r", encoding="utf-8") as handle:
                spec = json.load(handle)
            if not isinstance(spec, dict):
                raise ValueError("Proposal specification must be a JSON object")
            _print(
                CodePetWorkspace(Path(args.workspace)).create_proposal(
                    spec.get("task", ""),
                    spec.get("operations"),
                    tests=spec.get("tests"),
                    rationale=spec.get("rationale", ""),
                    risks=spec.get("risks", []),
                )
            )
        elif args.command == "pet-list":
            _print(CodePetWorkspace(Path(args.workspace)).list_proposals())
        elif args.command == "pet-show":
            _print(CodePetWorkspace(Path(args.workspace)).load_proposal(args.proposal_id))
        elif args.command == "pet-approve":
            _print(CodePetWorkspace(Path(args.workspace)).approve(args.proposal_id, actor=args.actor, human_approved=args.approve))
        elif args.command == "pet-reject":
            _print(CodePetWorkspace(Path(args.workspace)).reject(args.proposal_id, actor=args.actor, reason=args.reason))
        elif args.command == "pet-apply":
            _print(CodePetWorkspace(Path(args.workspace)).apply(args.proposal_id, actor=args.actor, timeout_seconds=args.timeout, require_network_isolation=args.require_network_isolation))
        elif args.command == "pet-verify":
            _print(CodePetWorkspace(Path(args.workspace)).verify())
        elif args.command == "pet-serve":
            from .service import build_server

            token = os.environ.get(args.token_env) if args.token_env else None
            if args.token_env and token is None:
                raise ValueError(f"Token environment variable is unavailable: {args.token_env}")
            server, token = build_server(Path(args.workspace), host=args.host, port=args.port, token=token, allow_remote=args.allow_remote)
            _print({"status": "serving", "url": f"http://{args.host}:{server.server_port}", "bearer_token": token, "boundary": "Local review service; keep this token private."})
            try:
                server.serve_forever()
            finally:
                server.server_close()
        elif args.command == "site-guide":
            site_guide = SiteGuide()
            if args.export:
                _print(site_guide.export(args.content_id, Path(args.export)))
            else:
                _print(site_guide.context(args.content_id))
        else:
            runtime = LoomVerathRuntime(Path(args.data_dir))
            if args.command in {"init", "introspect"}:
                _print(runtime.introspect())
            elif args.command in {"build-plan", "build-run"}:
                from .build_pipeline import MechanicBuild
                build = MechanicBuild(runtime)
                if args.command == "build-plan":
                    _print(build.plan())
                else:
                    result = build.run(through=args.through, isolated=args.isolated)
                    _print(result)
                    if any(s["status"] == "failed" for s in result["stages"]):
                        return 2
            elif args.command in {"bionemo-preflight", "bionemo-prepare", "bionemo-predict"}:
                from .bionemo import BioNeMoResearch, preflight
                bio = BioNeMoResearch(runtime)
                if args.command == "bionemo-preflight":
                    _print(preflight())
                elif args.command == "bionemo-prepare":
                    _print(bio.prepare(Path(args.sequence_file).read_text(encoding="utf-8").strip()))
                else:
                    document = json.loads(Path(args.request_file).read_text(encoding="utf-8"))
                    payload = document.get("payload", document) if isinstance(document, dict) else document
                    _print(bio.predict(payload, allow_network=args.allow_network))
            elif args.command in {"vox", "hands"}:
                from .mechanics import VoxParser, JintaiHands
                command = (VoxParser.parse(args.text) if args.command == "vox" else
                    JintaiHands.parse(json.loads(Path(args.event_file).read_text(encoding="utf-8"))))
                result = runtime.run(command.text, requested_mode=command.mode)
                _print({"input": command.to_dict(), "result": result.to_dict()})
            elif args.command == "run":
                result = runtime.run(
                    " ".join(args.text),
                    requested_mode=args.mode,
                    user_approved=args.approve,
                    importance=args.importance,
                )
                _print(result.to_dict())
            elif args.command == "replay":
                _print(runtime.replay(args.session_id))
            elif args.command == "verify":
                _print(runtime.verify())
            elif args.command == "memory-search":
                _print(runtime.memory.search(" ".join(args.query), limit=args.limit))
            elif args.command == "crystallize":
                _print(
                    runtime.memory.consolidate(
                        threshold=float(runtime.state.value("memory.consolidation_threshold")),
                        actor="founder",
                    )
                )
            elif args.command == "snapshot":
                _print(runtime.state.create_snapshot(actor="founder"))
            elif args.command == "rollback":
                _print(
                    runtime.state.rollback(
                        args.snapshot_id, actor="founder", human_approved=args.approve
                    )
                )
            elif args.command == "propose-change":
                patch = json.loads(args.patch_json)
                if not isinstance(patch, dict):
                    raise ValueError("patch_json must decode to an object")
                _print(
                    runtime.evaluator.propose_and_apply(
                        patch, actor="founder", human_approved=args.approve
                    )
                )
            elif args.command == "layers":
                _print(runtime.layers.to_dict())
            elif args.command == "research-validate":
                _print(runtime.research.validate_file(Path(args.record_json)))
            elif args.command == "research-ingest":
                _print(runtime.research.ingest_file(Path(args.record_json), actor="founder"))
        return 0
    except (LoomVerathError, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        _print({"error": type(exc).__name__, "message": str(exc)})
        return 2
    finally:
        if runtime is not None:
            runtime.close()


if __name__ == "__main__":
    sys.exit(main())
