# Verification Record

**Build:** 0.3.0  
**Verified:** 2026-09-02 UTC  
**Runtime:** Python 3.12.13

## Commands

```bash
python -m compileall -q loom_verath tests examples
python -m unittest discover -s tests -v
cd tools/llm_forge && python -m unittest discover -s tests -v
python -c "from setuptools.build_meta import build_wheel; build_wheel('DIST_DIR')"
python -m pip check
unzip WHEEL -d WHEEL_IMPORT_DIR
PYTHONPATH=WHEEL_IMPORT_DIR python -m loom_verath --data-dir RUNTIME_DIR verify
```

## Current evidence

- 41 runtime unit and integration tests pass.
- 7 bundled LLM Forge dataset conformance tests pass.
- Core, tests, examples, and all four LLM Forge Python entry points compile.
- The locally built wheel was extracted into a clean import directory and executed from outside the source tree because this environment intercepts package installation commands as potential network operations.
- A clean runtime verifies the Chrono-Scribe chain, Ed25519 lineage, state invariants, SQLite integrity, schema version, configuration root, and Merkle root.
- The CodePet HTTP test performs an authenticated propose → approve → apply lifecycle.
- A forced failing unit test restores all affected files; passing tests execute in a temporary workspace copy so their side effects do not touch the source workspace.
- Traversal, symlink targets, protected paths, likely secrets, duplicate targets, stale workspaces, altered proposals, altered journal events, missing approval, missing provider consent, unallowlisted endpoints, anonymous API access, and unauthorized remote binding are rejected.

## Test inventory

| Area | Tests |
|---|---:|
| Classification, Bridge Contracts, gates, capability authorization | 6 |
| CodePet transactions, test-runner isolation, provider boundary, service authentication | 11 |
| Ouroboros evaluator and approval controls | 3 |
| Layer authority, H-field, ZPE, Site Guide integration | 6 |
| CHRYSALIS encryption, deletion, consolidation, identity continuity | 3 |
| Database and runtime migrations | 3 |
| Runtime privacy, replay, rejection, introspection | 4 |
| State invariants, CAS, snapshots, rollback, ledger tamper, Merkle root | 5 |
| **Runtime total** | **41** |

## Interpretation

This evidence supports the declared local prototype contracts. It does not establish production security, complete policy coverage, universal alignment, AGI/ASI, consciousness, or speculative physics. Approved tests execute repository code; `network_os_enforced` remains `false` until the executor is moved into an independently verified network-denied container or microVM.
