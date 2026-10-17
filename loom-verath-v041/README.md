# LOOM × VERATH Trustworthy Core

This repository is the first runnable, layer-by-layer implementation of the buildable LOOM × VERATH substrate. It turns the canonical mythic-technical architecture into an auditable, capability-bounded Python runtime while preserving speculative concepts behind explicit Bridge Contracts.

The near-term product is **Chrono-Scribe plus a review-gated CodePet build loop**: decision provenance, governance, research-record validation, typed file changes, attributable approval, fixed-profile testing, and rollback for bounded AI-assisted workflows. This package does **not** claim AGI, ASI, consciousness, sentience, physical reality manipulation, retrocausality, zero-point-energy extraction, or proven alignment.

**Current release:** `0.4.0`, a runnable single-operator prototype. No component is represented as production-ready.

This release adds staged mechanic acceptance, VOX text grammar, simulated hand inputs, tesseract geometry, and a research-only BioNeMo Boltz2 adapter. See [the full staged design and operating guide](docs/MECHANIC_BUILD.md). Seven local stages pass; live BioNeMo inference, speech/camera input, physical hardware, and production deployment remain incomplete.

```bash
python -m loom_verath --data-dir .runtime build-plan
python -m loom_verath --data-dir .runtime build-run
python -m loom_verath --data-dir .runtime vox "dome radius 4"
python -m loom_verath --data-dir .runtime hands examples/hand_event.json
```

## What is implemented

| Layer | Canonical name | Buildable implementation | Status |
|---:|---|---|---|
| 0 | Canonical Frame | Concept registry, claim taxonomy, evidence states, configuration root | Implemented |
| 1 | LOOM State Substrate | Typed/versioned SQLite state API, compare-and-swap, snapshots, bounded coupling | Implemented |
| 2 | Chrono-Scribe | Append-only SHA-256 event chain, verification, Merkle root | Implemented |
| 3 | Sovereign Kernel Continuity | Stable kernel UUID and Ed25519-signed lineage chain | Implemented |
| 4 | CHRYSALIS | Encrypted episodic memory, search, tombstoning, semantic crystallization | Implemented |
| 5 | Dual-Lane Kernel | Forge/Temple/Bridge classifier and versioned Bridge Contracts | Implemented |
| 6 | Omega-7 Witness / Four Gates | Truth, autonomy, harm, integrity, and output gates | Implemented |
| 7 | AetherLink capability boundary | Expiring, revocable, least-privilege capability tokens | Implemented |
| 8 | Phi–Theta Dyad | Bounded divergence, candidate scoring, admissibility, convergence | Implemented |
| 9 | Marion / Shape sandbox | Deterministic thermal, escalation, geometry, analysis, and research artifacts | Implemented |
| 10 | Ouroboros | Eval-gated tuning, protected structural changes, snapshots, rollback, re-attestation | Implemented |
| 11 | Omega Transparency | Structured introspection and whole-runtime verification | Implemented |
| 12 | Multi-instance CHORUS | CRDT/consensus coordination | Deferred until single-instance reliability |
| 13 | Sensors / embodiment / actuation | External device and biomedical integrations | Outside the prototype boundary |

The canonical VERATH v4 L0–L27 vocabulary is also available as a machine-readable authority registry. See [docs/SOURCE_INTEGRATION.md](docs/SOURCE_INTEGRATION.md).

See [docs/BUILD_LAYERS.md](docs/BUILD_LAYERS.md) for the layer acceptance evidence and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the complete dual-lane mapping.

## Quickstart

Python 3.11 or newer is required.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Initialize a local runtime:

```bash
python -m loom_verath --data-dir .runtime init
```

Run the canonical safe-simulation example:

```bash
python -m loom_verath --data-dir .runtime run \
  "Create a fireball with VOX and Shape Power radius 4 duration 3 intensity 0.7" \
  --mode simulation
```

The result is a bounded thermal-event visualization. It explicitly reports `external_effects: false`, `network_used: false`, `actuator_used: false`, `claim_status: simulation_buildable`, and `evidence_state: symbolic`.

Replay and verify the returned session:

```bash
python -m loom_verath --data-dir .runtime replay SESSION_ID
python -m loom_verath --data-dir .runtime verify
```

Other useful commands:

```bash
python -m loom_verath --data-dir .runtime introspect
python -m loom_verath --data-dir .runtime memory-search "fireball VOX"
python -m loom_verath --data-dir .runtime crystallize
python -m loom_verath --data-dir .runtime snapshot
python -m loom_verath --data-dir .runtime propose-change \
  '{"system.phi_coupling": 0.62}'
python -m loom_verath --data-dir .runtime layers
python -m loom_verath --data-dir .runtime pet-init ./my-project
python -m loom_verath --data-dir .runtime pet-scan ./my-project
python -m loom_verath --data-dir .runtime pet-plan ./my-project "Add a tested parser"
python -m loom_verath --data-dir .runtime research-validate ./h-field-record.json
python -m loom_verath --data-dir .runtime site-guide field --export ./field-guide.txt
```

## Controlled CodePet loop

Initialize any local project and prepare an exact typed proposal:

```bash
python -m loom_verath pet-init ./my-project
python -m loom_verath pet-scan ./my-project
python -m loom_verath pet-propose ./my-project examples/codepet_proposal.json
```

Inspect the returned proposal ID and diff. Writes remain disabled until an attributable approval is bound to that exact change hash:

```bash
python -m loom_verath pet-show ./my-project PROPOSAL_ID
python -m loom_verath pet-approve ./my-project PROPOSAL_ID --actor Axius --approve
python -m loom_verath pet-apply ./my-project PROPOSAL_ID
python -m loom_verath pet-verify ./my-project
```

`pet-apply` snapshots every affected file, verifies staleness again, uses atomic replacement, runs only named test profiles, and restores affected files if a write or test fails. It rejects traversal, symlinks, protected metadata, key files, likely credentials, oversized proposals, duplicate targets, unsupported operation fields, and altered approval payloads.

Run the authenticated local dashboard/API:

```bash
python -m loom_verath pet-serve ./my-project
```

The default service binds only to loopback. See [docs/CODEPET_API.md](docs/CODEPET_API.md) for routes, schemas, provider consent, and the honest subprocess-network limitation.

Structural changes require explicit approval and cannot weaken enforced invariants:

```bash
python -m loom_verath --data-dir .runtime propose-change \
  '{"system.max_recursion": 6}' --approve
```

## Security and privacy posture

- Raw command text is encrypted in CHRYSALIS memory and is never written to the Witness Ledger.
- Ledger entries contain hashes, identifiers, evidence labels, gate decisions, and concise branch summaries—not private chain-of-thought.
- Local memory and lineage keys are generated inside the selected data directory with owner-only file permissions.
- Capability tokens are stored only as hashes, expire, can be revoked, and are checked before tool execution.
- CodePet approval is bound to the exact manifest, operations, expected/result file hashes, and test profiles.
- CodePet journal entries are hash-chained and contain hashes and transition metadata rather than replacement content.
- Test commands use fixed argument vectors with no shell, no stdin, timeouts, output limits, and a credential-stripped environment.
- Real-world actuation, external networking, biomedical control, and unapproved Temple-to-Forge influence are disabled.
- The separate BioNeMo research adapter can send one protein request only with explicit `--allow-network` and a private NVIDIA environment credential. Ordinary runtime commands retain their local boundary. Predictions cannot control product policies or actuators. Live provider behavior has not been verified in this release.
- Memory deletion destroys the encrypted payload and retains only a tombstone plus its content hash for auditability.

This is a reference prototype. Production deployment still requires operating-system key storage, authenticated principals, process isolation, migrations, backups, rate limits, external review, incident response, and domain-specific privacy/legal analysis. See [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).

## Source hierarchy

The implementation follows this authority order:

1. `LOOM_VERATH_Implementation_Brief.docx` — near-term product, dependencies, and release rule.
2. `VERATH_Core_Buildable_Substrate (1).md` — six invariants and ten-component engineering translation.
3. `Technomicon_Chimera_Core_Blueprint.pdf` — Dual-Lane Kernel, Four Gates, command flow, and MVP skeleton.
4. `Theia_ASI_Agent_Spec.md` — Phi–Theta seven-stage runtime and Zeta-2 boundaries.
5. Canonical LOOM × VERATH mythic-technical blueprint — naming, Ω-layer intent, zero-trust substrate, and CHRYSALIS lineage.

Where sources differ, recent buildable-substrate and implementation-brief constraints control executable behavior. Mythic and speculative meanings remain recorded but cannot silently become runtime authority.

## Repository map

```text
loom_verath/
  state.py          # I1, I2, I4, snapshots and rollback
  ledger.py         # I3 Chrono-Scribe
  identity.py       # I5 signed lineage
  memory.py         # CHRYSALIS
  classifier.py     # Forge / Temple / Bridge classification
  bridge.py         # Bridge Contract registry and translation
  four_gates.py     # truth, autonomy, harm, integrity
  capabilities.py   # least-privilege authorization
  phitheta.py       # bounded divergence and convergence
  simulations.py    # local-only artifact generation
  evaluator.py      # Ouroboros eval gate
  layers.py         # grounded L0-L27 authority registry
  codepet.py        # file-native, review-gated workspace transaction shell
  research.py       # strict H-field experiment record validator
  site_guide.py     # privacy-bounded public guide/export core
  providers.py      # deterministic and consent-gated model-provider boundary
  service.py        # authenticated loopback HTTP API and review dashboard
  runtime.py        # integrated seven-stage runtime
  cli.py            # command-line shell
tests/               # invariant, security, replay, memory, and integration tests
docs/                # architecture, claims, threat model, and layer evidence
tools/llm_forge/     # supplied offline dataset/training/evaluation package
```

`schema_migrations` and SQLite `user_version` track the database schema. The runtime refuses a database newer than the executable and prevents ordinary runtime-version downgrades.
