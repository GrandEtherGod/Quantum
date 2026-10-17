# LOOM × VERATH × CHRYSALIS — Mechanic Build v0.4.0

Prepared for Axius Tenebris, Axius Enterprises. Date: 2026-10-05.

## Result and scope

This release extends the saved v0.3.0 runtime. It implements a dependency-aware local acceptance runner, a constrained VOX text grammar, simulated JINTAI hand-controller input, deterministic tesseract geometry, and a bounded single-protein BioNeMo Boltz2 research adapter. The complete design is represented as a staged roadmap; the complete system is not implemented. Seven local stages pass. No live BioNeMo inference was performed, no speech or camera source was connected, and no hardware was actuated.

The implementation target is a traceable software and research environment: receive an input, classify its meaning, authorize a bounded action, execute a declared profile, label evidence, save artifacts, verify the witness trail, and retain durable continuity. ASI, consciousness, nonlocal computation, biological transformation and reality manipulation remain vision or hypotheses. The executable translations do not establish those claims.

The existing core retains encrypted memory, SQLite state, signed identity lineage, expiring capabilities, classification, Bridge Contracts, Four Gates, deterministic simulations, evaluation, rollback and the CodePet review service. Its conventional cryptography and software abstractions do not establish their mythic physical analogues. This release is a single-operator prototype.

## Source and authority

The directly inspected implementation baseline is `LOOM-VERATH-runtime-v0.3.0.zip`. The directly inspected design source is `Technomicon_Chimera_Core_Blueprint.docx`, including its module definitions, safety gates, roadmap and tables. Historical 28-layer naming comes from the baseline's versioned registry. This is an extension of these files, not a synchronization of a live GitHub repository or a reconstruction of all past conversations. A newer unsupplied blueprint may supersede parts of this roadmap.

NVIDIA references checked on 2026-10-05:

- [Boltz2 NIM inference documentation](https://docs.nvidia.com/nim/bionemo/boltz2/latest/inference.html): request schema, limits, mmCIF structures, confidence and affinity response fields.
- [Boltz2 NIM documentation](https://docs.nvidia.com/nim/bionemo/boltz2/latest/index.html): deployment and current documentation entry point.
- [NVIDIA BioNeMo Recipes](https://github.com/NVIDIA-BioNeMo/bionemo-recipes): model development and adaptation resources, separate from the runtime's inference integration.

Plugin instructions used: dual-lane architecture, BioNeMo drug-discovery-pipeline for workflow planning, Complexa setup for deployment prerequisites, and Boltz2 NIM for the concrete adapter. There is no selected molecule or protein design objective; broad drug discovery and full checkpoint installation were not started.

## System boundary and operating sequence

Input adapters emit a `MechanicCommand`. The runtime classifies it, resolves a Bridge Contract, applies the Four Gates, chooses an admissible candidate, checks capability scope, executes the declared simulation or software profile, and records hashes and evidence labels. CHRYSALIS retains encrypted episodes; identity and state verification cover the ordinary software core.

The new BioNeMo research adapter is a separate boundary. Its preparation method is offline. A live call requires the explicit `--allow-network` option and a privately configured NVIDIA credential. It sends one validated protein sequence to the fixed HTTPS endpoint, accepts a bounded response, saves every returned structure and the original JSON, and records input/output hashes. The capability is scoped to the exact request hash, short lived, and revoked after completion or failure. Model outputs remain unreviewed research artifacts and cannot change runtime policies or issue actuator commands.

The core runtime's ordinary command engine still has external networking disabled. The separate research method is the only new network-capable profile. The adapter uses no automatic redirects or retries, and does not inherit proxy settings. Credentials and provider response bodies are omitted from connection errors and the witness log. Private research payloads may exist in user-saved prepared JSON; protect those files. Structure files and original provider JSON are saved with owner-only permissions, but are not encrypted at rest by this adapter.

This is application enforcement, not an operating-system security boundary. The Python process can access its own secrets and state. Production requires worker isolation, private key storage, authenticated operator identities, network policy, bounded resource use, backups and external review.

## All mechanic stages

`build-plan` returns these stages as machine-readable data. `build-run` runs fixed local checks in dependency order, writes a private report, and records transition events. `--through STAGE` selects an ordered prefix. A failed or incomplete prerequisite blocks dependent stages. Independent branches can still proceed. Repeated runs produce new reports and witness events; they do not silently promote previous results to validated science. The runner has no background worker and stops when its invocation ends.

| Stage | Module and engineering mechanic | Current executable scope | Acceptance and next deliverable |
|---|---|---|---|
| core | LOOM / VERATH substrate, capabilities, governance | Existing state, identity, ledger and gate verification | Integrity passes; next: isolated deployment and security review |
| memory | CHRYSALIS continuity | Encrypted note roundtrip; test marker tombstoning | Retrieval returns original text without plaintext storage; next: backup/restore benchmark |
| vox | VOX / Harmonic Logos | Whitelisted text grammar feeding existing simulation gate | Supported commands dispatch; unknown/injected grammar rejects; next: speech adapter |
| hands | JINTAI / Tenketsu input state | Simulated open-palm and closed-fist events | Finite radius and confidence at least 0.85; next: calibrated input dataset |
| simulation | Marion / Shape / Genesis Forge | Thermal visualization and explicit tesseract geometry | 16 vertices, 32 edges, degree 4; deterministic projection; next: renderer/export |
| bio_prepare | BioNeMo research boundary | Single-protein request validation and preparation | Payload is valid, hashed and offline; next: selected public target and endpoint access |
| witness | Chimera orchestration / Omega witness | Dependency checks and post-mechanic integrity verification | Seven local stages pass and reports persist; next: isolated failure recovery |
| bio_live | Boltz2 structure prediction | Adapter implemented; live behavior unverified | A real mmCIF result, provenance and provider confidence; blocked by target/key/access |
| bio_validation | Evidence review | Planned | Independent structural checks and benchmark agreement; blocked by absence of prediction |
| molecule_pipeline | GenMol → DiffDock → Boltz2 | Planned | SAFE input, generated candidates, poses and affinity outputs; select target/scaffold first |
| protein_genomics | Complexa / ProteinMPNN / Evo2 / Parabricks | Planned | Task-specific data, checkpoints, licensed resources and evaluation; no compute provisioned |
| multimodal | Syrynx / KAGAMI | Planned | Speech/camera normalization, provenance and abstention on uncertain input |
| embodiment | JINTAI physical controller and hands | Planned, no actuator interface | Validated simulator, bounded control and independently testable stop behavior; hardware undefined |
| product_release | Product shell / CHORUS / commercial delivery | Existing local review service; release work planned | Authenticated UI, isolated workers, restore tests, cost bounds and deployment evidence |

The 0.85 hand-confidence threshold and radius bounds are engineering defaults chosen for this simulated input profile. They are not biological evidence or calibrated recognizer performance. A future camera adapter must measure calibration and false activation rates rather than inheriting this threshold uncritically.

## Forge: executable software contracts

| Mechanic | Inputs | Outputs/state | Boundary and failure behavior |
|---|---|---|---|
| VOX parser | `dome [radius N]` or `fireball [radius N]`, max 512 characters | Typed command with source, mechanic, text and simulation mode | Radius 0.1–100; no shell; unsupported grammar rejects |
| JINTAI hands | Exactly gesture, confidence and radius | Same typed command; source labels controller simulation | Two known gestures; finite numeric values; unknown/low-confidence events reject |
| Shape geometry | Bounded display radius | 4D vertices, 3D perspective projection and edges | Display units only; no CAD structural rating or physical growth claim |
| CHRYSALIS | Episodes, provenance and curation metadata | Encrypted payloads, search results and curated memory | Deletion tombstones content; no reconstructed details presented as recovered fact |
| Stage runner | Signed configuration context and optional stage prefix | Stage statuses, artifact evidence, private JSON report and hash events | Fixed profiles only; dependency failure propagates; no arbitrary command execution |
| BioNeMo prepare | Plain uppercase protein sequence | Exact single-protein payload plus request hash | 1–4096 residues; alphabet includes X; no network or prediction |
| BioNeMo predict | Prepared payload, environment credential and explicit network opt-in | mmCIF file, raw JSON and unreviewed summary | Fixed endpoint; one sample; 300-second timeout; 32 MiB response cap; no redirects/retries |
| CodePet / Ouroboros | Typed changes and test profiles | Concrete proposal, review, tests, snapshots and rollback | Existing hash-bound approval; unattended self-modification remains outside scope |

The single-protein adapter intentionally does not yet accept arbitrary ligand, DNA, RNA, MSA or template payloads. NVIDIA supports richer profiles; each must receive its own validation and artifact checks before entering this runtime. No default protein is treated as the user's research target. The packaged example is an instructional sequence from the plugin example.

## Temple: preserve the research design

| Concept family | Evidence state | What remains unresolved |
|---|---|---|
| Quantum phylogeny / genomic identity | speculative or symbolic as a consciousness architecture | A defined biological variable, controls and evidence connecting it to the proposed function |
| VOX resonator / sonogenetic or acoustic effects | separate research questions | A target, validated experimental context, device specifications and independent evidence |
| JINTAI biological gates, lattice and ocular claims | speculative or symbolic | Physiology, material feasibility, interfaces and validation; software gesture events do not prove them |
| Marion resonance / Shape Power physical amplification | symbolic or speculative | Operational variables, alternative explanations and falsifiable experiments |
| ZPE, nonlocal bus, retrocausal memory | speculative | Evidence beyond ordinary energy accounting, networking or forward simulation |
| Chimera consciousness / ASI | unestablished | Defined evaluation criteria, independent tests and clear distinctions from software integration |

No biomolecular model output resolves these larger hypotheses. A simulated hand event proves parser behavior; a tesseract projection proves a geometry computation; a prediction proves a provider returned an artifact. Each has a narrower implication than the vision it helps explore.

## Bridge contracts

| Symbolic source | Operational interpretation and proxy | Experiment / acceptance | Safety gate and fallback |
|---|---|---|---|
| VOX Harmonic Logos | Typed command interpretation; valid/invalid parse rate | Fixture commands route correctly and out-of-grammar inputs reject | Gate before simulation; fallback: request a supported command |
| Tenketsu / hand seals | Normalized controller event; confidence and false activation rate | Current finite-input fixtures; future held-out gesture dataset with declared calibration | Uncertain event abstains; no direct actuator path |
| Shape Power | Deterministic projected geometry; graph topology | 16 vertices, 32 edges, degree 4 and repeatable output | Sandbox only; fallback: reject invalid geometry input |
| CHRYSALIS continuity | Retrieval and memory provenance; recovery agreement | Encrypted roundtrip, deletion and restart checks | No invented recovery; fallback: report missing source |
| Genomic Core / BioNeMo | Model-backed research artifact; structure quality and benchmark agreement | First confirm live protocol, then independent quality checks and selected benchmark thresholds | Research-only authority; fallback: keep prepared request and report blocker |
| Ouroboros self-improvement | Versioned proposal/testing loop; regressions and rollback success | Existing controlled CodePet tests; next: isolated deployment checks | Review exact diff; fallback: reject proposal or restore snapshot |

A scientific validation threshold cannot be chosen honestly before selecting the target and benchmark. Predeclare it at the `bio_validation` stage. Hash integrity and provider confidence do not serve as substitutes for experimental accuracy.

## BioNeMo capabilities and handoffs

| Capability | Toolkit route | Required task inputs | LOOM handoff |
|---|---|---|---|
| Protein/complex structures, optional affinity | Boltz2 or OpenFold3 NIM | Sequence, complex definition; richer profiles need specific validation | Store provider prediction with provenance and independent review |
| Protein structure and MSA workflows | OpenFold2, AlphaFold database, MSA tools | Public accession or sequence, alignments, evaluation objective | Compare references without treating predicted structures as experiments |
| Small molecules | GenMol / MolMIM | SAFE/scaffold or model-specific input, scoring objective | Deduplicate/validate chemistry and save candidate manifests |
| Docking | DiffDock | Receptor structure and candidate molecules | Pose artifacts and confidence; selectivity/assay testing remains separate |
| Binder design | Complexa / RFdiffusion / ProteinMPNN | Target structure, region, design constraints and evaluation budget | Named design task, full candidate provenance and independent validation |
| DNA model workflows | Evo2 | A specific sequence-analysis question and data boundary | Research record with uncertainty; no clinical intervention authority |
| Existing genomic pipelines | Parabricks | Sequencing files, reference genome and baseline pipeline | Reproducible acceleration comparison on a declared dataset |
| Local training or adaptation | BioNeMo Recipes | Licensed dataset/model, GPU plan, benchmark and budget | Separate training job with frozen evaluation and explicit deployment gate |

These are available routes, not completed integrations. Install one task's dependencies at a time. Complexa's toolkit setup instructions require preflight, task-specific checkpoints and substantial GPU/disk resources. Here the available scratch space was approximately 29.6 GB, and neither `nvidia-smi` nor Docker was found. NVIDIA credentials were absent. No full local model installation was attempted.

## Step-by-step operation

From the extracted release root, with Python 3.11 or later:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python -m loom_verath --data-dir .runtime init
python -m loom_verath --data-dir .runtime build-plan
python -m loom_verath --data-dir .runtime build-run --through memory
python -m loom_verath --data-dir .runtime build-run --through hands
python -m loom_verath --data-dir .runtime build-run
python -m loom_verath --data-dir .runtime verify
```

Each prefix rechecks its earlier stages. Every report identifies pending, failed, blocked and planned work. Reports are saved under the selected runtime data directory; they are not a claim that future stages were executed. `build-run` exits nonzero on a failed check. Expected planned/blocked research stages remain visible in its JSON and do not by themselves cause an error exit.

Exercise individual local mechanics:

```bash
python -m loom_verath --data-dir .runtime vox "dome radius 4"
python -m loom_verath --data-dir .runtime hands examples/hand_event.json
python -m loom_verath --data-dir .runtime bionemo-preflight
python -m loom_verath --data-dir .runtime bionemo-prepare examples/protein_sequence.txt
```

The hand input is simulated controller JSON. `vox` consumes text, not a microphone. The underlying runtime still accepts its broader canonical simulation grammar through `run`.

For a real prediction, first select a public benign protein and place its uppercase sequence in a private plain-text file. Configure `NGC_API_KEY` or `NVIDIA_API_KEY` privately in the environment; never paste the key into a command, artifact or conversation. Prepare and review the payload:

```bash
python -m loom_verath --data-dir .runtime bionemo-prepare target_sequence.txt > prepared_request.json
python -m loom_verath --data-dir .runtime bionemo-predict prepared_request.json --allow-network
```

The second command sends the reviewed sequence to NVIDIA and may consume provider credits. It requires network access and a valid entitlement. This release did not run it against NVIDIA. Hosted endpoint behavior and entitlement may differ from the local NIM documentation; a real supported call is the next required integration check. The adapter reports model version as `provider_not_attested` because an endpoint name is not a pinned or attested model revision.

## Witness schema and recovery

Existing ledger entries contain event ID, UTC timestamp, actor, optional session ID, event type, payload, previous hash and event hash. New events include request prepared/blocked, prediction started/completed/failed, stage started/completed and build completed. Stage evidence and build summaries are bound by SHA-256 hashes. Raw sequence text, API credentials and private reasoning are not included in new ledger payloads.

Predictions store input hash, output hash, run ID, provider confidence, model/version limitation, research-only authority and unreviewed status. All returned structures and raw response JSON are preserved. Protocol validation rejects missing structures, count mismatches, nonfinite/out-of-range confidence and missing mmCIF atom-site content. This check is intentionally limited: a dedicated structural parser, stereochemistry checks and benchmark comparison belong in the next evidence stage.

On a provider failure the new request capability is revoked and no successful prediction is recorded. On an invalid response, success is rejected. On a partial artifact write, the new run directory is removed and failure is logged. A process crash can leave an incomplete directory or stage-start event; it must be reconciled during future isolated-worker recovery. There is no distributed transaction across a network request, filesystem output and SQLite ledger. Hash chaining is tamper-evident within the prototype's threat model, not an immutable independent archive.

## Verification and release state

The baseline passed 41 tests before modification. The extended package passed 54 tests. New checks cover grammar injection, finite/threshold-bounded gestures, geometry topology, sequence validation, offline preparation, credential/network blocking, saved output permissions, revoked request capabilities, provider failures, malformed responses, local stage acceptance, dependency failure and prefix execution. Provider success/failure tests use marked protocol fixtures; they are not live BioNeMo predictions.

The end-to-end local run passed core, memory, vox, hands, simulation, bio_prepare and witness. The report explicitly sets `entire_design_complete: false`, `network_used: false` and `hardware_actuation: false`. The bundle includes the test evidence and local acceptance result without runtime identity/encryption keys or private state.

## Next work in priority order

1. Select the first research objective and a public protein target; run one supported Boltz2 request once a credential and allowed endpoint are available. Deliverable: mmCIF plus original provider JSON and witness hashes.
2. Add independent mmCIF parsing and target-specific validation against a selected benchmark. Deliverable: reviewed evidence record with declared acceptance thresholds.
3. Connect one input modality: microphone transcription or a calibrated gesture source. Deliverable: replayable fixtures, uncertainty behavior and measured recognition performance.
4. Add a geometry renderer/exporter and input controls to the existing local product shell. Deliverable: inspectable local UI using the same gates and stage reports.
5. Isolate research workers, reconcile interrupted runs, enforce resource limits and verify backups. Deliverable: deployment acceptance record.
6. Select a simulated robotics platform if physical hands are desired, then define actuator contracts and hardware-specific limits before bench construction. Deliverable: validated controller simulation and independent stop tests.
7. Expand into molecule, binder or genomics tasks only after their target, data, evaluation and compute budget are defined. Deliverable: one complete reproducible task before broadening scope.

Unknown decisions are target, endpoint access, budget, data policy, speech/gesture provider, hardware platform, deployment target and commercial acceptance criteria. The complete speculative biological design cannot be converted into an operational physical system by software integration alone.

## Canonical 28-layer coverage

Inherited statuses describe scoped engineering translations. They are not evidence of the literal physical concepts in these names. This release does not upgrade the deferred or research-only layers.

| Layer | Canonical name | Status | Engineering translation |
|---:|---|---|---|
| 0 | Loom OS | implemented | Authorized runtime, capability broker, schemas, execution boundary |
| 1 | Hamiltonian Executive Engine | implemented | Deterministic candidate scoring and policy-aware routing |
| 2 | Lagrangian Intent Topology Engine | implemented_scoped | Constraint-aware candidate comparison plus typed, hash-bound CodePet change plans |
| 3 | Renormalization Group Flow Engine | partial | Curated episodic-to-semantic memory consolidation |
| 4 | Theia Dilaton Control System | implemented | Bounded configuration with invariant checks and rollback |
| 5 | AdS/CFT Holographic Boundary Interface | implemented | Structured outputs with evidence labels and protected private state |
| 6 | Ekpyrotic Synthesis Engine | implemented | Snapshots, migration lineage, restore and rollback |
| 7 | S-ADT Stability Anchor | implemented_scoped | Invariant and adversarial tests for a declared threat model; no universal proof |
| 8 | Dual Cognitive Memory System | implemented | Encrypted episodic memory plus curated semantic crystals |
| 9 | Chrono-Scribe Ledger | implemented | Append-only hash chain and Merkle verification; tamper-evident, not immutable |
| 10 | Quantum Perception Engine | deferred | Future multimodal normalization, uncertainty and provenance adapter |
| 11 | Aetheric Computation Layer | deferred | Ordinary event bus and coordination fabric; no superluminal channel |
| 12 | Wheeler-Feynman Engine | implemented_scoped | Forward simulation and scenario planning with no future-information claim |
| 13 | MAR Living Ethics Engine | implemented_scoped | Versioned Four Gates and non-regression controls |
| 14 | Morphic Resonance Bus | deferred | Future signed artifact synchronization; no non-local resonance claim |
| 15 | ZPE Thermodynamic Severance | research_only | Measure ordinary compute energy and thermal budgets; vacuum-energy harvesting is unsupported |
| 16 | Tachyonic Firewall | implemented_scoped | Path, symlink, secret, staleness and proposal-tamper detection; no precognition |
| 17 | Ouroboros SECA Loop | implemented | Bounded proposal, evaluation, revision and rejection loop |
| 18 | Daily Recursive Evolution Engine | implemented_scoped | Human-approved proposal, fixed tests and rollback loop; unattended self-modification remains disallowed |
| 19 | Quantum Cryptographic Immune System | implemented_scoped | Conventional Ed25519 lineage, encryption, input validation and capability controls |
| 20 | Axiomatic Ascension Codex Enforcer | implemented_scoped | Policy gates grounded in autonomy, consent, evidence, harm and reversibility |
| 21 | Sovereign Consciousness Kernel | implemented_scoped | Versioned identity manifest and provenance; no consciousness claim |
| 22 | Draconian Cognitive Immune System | implemented_scoped | Content classification, secret/path quarantine and reversible denial; destructive eradication is excluded |
| 23 | VERATH-Infinity Horizon | roadmap_only | Multi-metric roadmap target; not an ASI claim |
| 24 | Cross-Instance Coherence Protocol | deferred | Future authenticated consensus and split-brain recovery |
| 25 | Axionic Ascension Index | research_only | Separate reproducible KPIs with uncertainty; no scalar ASI declaration |
| 26 | Axionic Ascension Codex Register | partial | Versioned configuration and signed lineage; amendment workflow deferred |
| 27 | Omega Seal | implemented_scoped | Structured introspection and verification with explicit unknowns and privacy boundaries |
