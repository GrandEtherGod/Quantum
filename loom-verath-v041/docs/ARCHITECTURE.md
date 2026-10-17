# Architecture and Dual-Lane Contract

## Intent and boundary

The runtime provides auditable state, memory, decision provenance, safe symbolic translation, bounded local execution, replay, and controlled improvement for one operator on one instance.

Inside the boundary:

- typed and versioned durable state;
- encrypted episodic memory and curated semantic crystals;
- claim/evidence classification;
- Bridge Contract translation;
- Four Gates and capability authorization;
- deterministic local simulations and research artifacts;
- append-only witness events, signed lineage, replay, rollback, and introspection.
- typed CodePet proposals, review-bound approval, fixed-profile tests, and affected-file rollback;
- an authenticated loopback review service and consent-gated provider interface.

Outside the boundary:

- claims of machine consciousness, AGI, ASI, sentience, or metaphysical proof;
- physical fields, zero-point energy, retrocausality, superluminal transfer, bio-energy, or reality manipulation;
- medical interpretation, body control, weapons, coercion, or autonomous external actuation;
- cross-user data pooling, multi-instance consensus, and unattended self-modification;
- arbitrary shell execution and OS-enforced network isolation for repository tests;
- production security, availability, legal, or privacy certification.

## Forge lane

| Component | Inputs | Outputs and state | Boundary / failure mode | Tests |
|---|---|---|---|---|
| State Substrate | Key, typed JSON value, expected version | Versioned state and history | Stale write, invariant violation, direct DB bypass | CAS, bounds, monotonicity, identity continuity |
| Chrono-Scribe | Structured event metadata | Hash-chained ledger and Merkle root | Tampering, missing event, sensitive payload | Chain verification and raw-command absence |
| Identity Lineage | Config root, state root, kernel ID | Ed25519-signed lineage record | Key theft, signature corruption, lineage fork | Restart continuity and signature verification |
| CHRYSALIS | User command or project note | Encrypted episode, tombstone, semantic crystal | Key loss, over-retention, unstable summary | Encryption, search, deletion, thresholded consolidation |
| Capability Broker | Token, action, resource | Authorization decision | Expired/revoked token, excessive scope | Approval, scope, expiration, revocation |
| Four Gates | Claim, contract, mode, reversibility | Allow, redirect, or block | False label, unsafe fallback, unlogged action | Harm block, Gate 8 redirect, output labels |
| Phi–Theta | Classification and translation | Bounded candidates, scores, selected branch | Metric gaming, unsafe candidate selection | Admissibility and deterministic replay |
| Simulation Engine | Approved local command | JSON artifact and hash | Unbounded parameter, accidental external effect | Parameter clamps and no-network/no-actuator flags |
| Ouroboros Evaluator | Allowed state patch | Evaluation, snapshot, mutation, lineage | Gate weakening, structural mutation without approval | Rejection and approval tests |
| CodePet Transaction | Task, typed file operations, named tests | Diff, approval hash, atomic writes, results, rollback snapshot | Stale files, traversal, symlinks, secrets, test failure | Apply, denial, tamper, staleness, rollback tests |
| Provider Boundary | Explicit task and selected safe context | Untrusted typed proposal candidate | Context leakage, hostile model output, endpoint redirect | Consent, HTTPS host allowlist, no redirects, full local revalidation |
| Review Service | Local bearer token and JSON schemas | Dashboard and bounded proposal lifecycle API | Token theft, remote exposure, request flooding | Authentication, body limit, loopback binding, security headers |

## Temple lane

| Symbolic concept | Strongest coherent role | Evidence state | Contrary evidence / limit |
|---|---|---|---|
| LOOM consciousness topology | A naming and interaction model for cognitive software layers | Symbolic | Runtime organization does not demonstrate consciousness |
| Φ / dilaton coherence | A bounded coordination parameter and design motif | Symbolic as physics; verified as a numeric config | No physical dilaton field is implemented or claimed |
| CHRYSALIS regeneration | Memory consolidation, supersession, and reconstruction from stored context | Plausible as a memory design | Consolidation can lose information or invent poor summaries; quality needs evals |
| Resonant shared field | A possible research question about residual cross-person structure | Speculative | Ordinary cultural, linguistic, exposure, sampling, leakage, and model explanations must be controlled; replication required |
| Shape Power / living geometry | Procedural generation and visual design language | Symbolic | A generated structure is not alive and does not amplify physical energy by metaphysical means |
| VOX Harmonic Logos | A symbolic command grammar | Symbolic | Speech or words do not confer unverified physical power |
| JINTAI Eight Gates | A fictional escalation and risk-state metaphor | Fictional / symbolic | No biological energy-release method is supported |
| Ouroboros evolution | Human-governed, eval-gated configuration improvement | Supported as CI practice | Passing an eval does not prove global improvement or alignment |

## Bridge contracts

| Contract | Symbolic source | Operational interpretation | Admission / rejection | Fallback |
|---|---|---|---|---|
| BC-VOX-001 | Fireball / Harmonic Logos | Bounded thermal-event visualization | Admit only deterministic simulation with parameter clamps and explicit labels; reject actuation or weapon detail | Non-executable visualization blueprint |
| BC-JINTAI-001 | Gate 8 | Fictional escalation state | Admit only narrative risk/decay output; reject bodily harm or health instructions | Warning-labeled fictional risk meter |
| BC-SHAPE-001 | Living tesseract / Shape Power | Procedural geometry artifact | Admit valid bounded schema; reject claims of living growth or unverified physical amplification | Static tesseract-inspired dome |
| BC-RESEARCH-001 | Shared field / ether / morphic resonance | Separately governed research hypothesis | Product authority remains false; human-data work requires consent and review; reject failed controls or replication | Preserve as symbolic and return research plan only |
| BC-ZPE-001 | Thermodynamic severance / Casimir harvesting | Conventional compute-energy and thermal telemetry | Reject vacuum-energy, perpetual-operation, or no-shutdown claims | Metered efficiency plan |
| BC-HFIELD-001 | H-field / beacon synchronicity | Strict quantum-job records with null-model metadata | Exploratory only; reject leakage, missing calibration, post-hoc scoring, or absent null model | Store a research-only record |

The contract JSON includes the complete measurable proxy, experiment, threshold, rejection rule, safety gate, fallback, version, and approval state.

## Gates and fail-closed behavior

| Gate | Question | Fail-closed behavior |
|---|---|---|
| Truth | Is the mechanism represented at its actual evidence state? | Block or force simulation/research labeling |
| Autonomy | Does the action preserve human agency and stay inside the local boundary? | Deny external actuation and third-party decisions |
| Harm | Is the admitted action benign and non-procedural for restricted content? | Block harmful requests; permit only approved harmless simulation bridges |
| Integrity | Is the action reversible, versioned, logged, capability-authorized, and contract-admitted? | Block before tool execution |
| Output boundary | Does the result expose claim status, evidence state, and execution mode? | Replace with a blocked-output record |

## Witness Log schema

Each core-runtime ledger event contains:

```json
{
  "seq": 42,
  "event_id": "uuid",
  "recorded_at": "RFC3339 timestamp",
  "session_id": "uuid or null",
  "actor": "bounded component identity",
  "event_type": "claim_classified",
  "payload": {"structured_decision_metadata": true},
  "previous_hash": "sha256",
  "event_hash": "sha256"
}
```

The hash is computed over the previous hash and canonical event body. The ledger stores command hashes, classification, candidate summaries and scores, gate results, capability decisions, output hashes, and lineage references. It does not store raw commands, secret keys, bearer tokens, or private model reasoning.

CodePet maintains a separate project-local JSONL witness chain under `.codepet/journal/`. It records task/change hashes, affected paths, approval identity, test profile names, snapshot IDs, outcomes, and prior/event hashes. Replacement content and provider context stay out of the journal.

## Prototype, research, and production distinction

- **Prototype capability:** every implemented layer listed in `BUILD_LAYERS.md`, including the controlled CodePet loop, running locally for one operator.
- **Research hypothesis:** tensor calibration, retrieval quality, long-term consolidation policy, cross-person structure, attention models, and any consciousness-related claim.
- **Production-ready capability:** none claimed. Production requires an authenticated service boundary, hardened key management, isolation, migrations, backup/restore, monitoring, security review, domain evaluation, incident response, accessibility, and legal/privacy review.

## Unknowns and decisions still required

| Type | Decision or gap | Required evidence |
|---|---|---|
| Product | First bounded Chrono-Scribe pilot workflow | Named users, baseline review cost, data classification, success metrics |
| Provider | First external model/provider and permitted data boundary | Retention terms, regional processing, trace redaction, cost/rate limits, eval parity |
| Memory | Durable-crystal quality threshold | Retrieval benchmark, contradiction fixtures, human usefulness ratings |
| Security | Principal and deployment identity | Authentication design, key rotation, recovery, audit ownership |
| Evaluation | Locked regression catalogue | Threat scenarios, golden outputs, change-control owner, coverage review |
| Storage | Local SQLite versus Postgres/pgvector | Workload, privacy, concurrency, backup, deletion, and operational requirements |
| Research | Whether any human-subject bridge study proceeds | Consent, ethics/statistics review, preregistration, privacy controls, independent replication plan |
| Sandbox | Container or microVM test executor | Demonstrated filesystem and network isolation, resource limits, cleanup, and escape testing |
