# Claim and Evidence Register

## Evidence states

| State | Meaning in this repository |
|---|---|
| `verified` | Directly demonstrated by code and tests in the current build |
| `supported` | Established engineering practice or a locally demonstrated component whose broader reliability still needs evaluation |
| `plausible` | Coherent engineering or research interpretation with incomplete validation |
| `speculative` | Testable or discussable hypothesis without sufficient confirming evidence |
| `symbolic` | Mythic, narrative, philosophical, or interface vocabulary with no asserted physical mechanism |

Evidence state is attached to the source claim. An approved simulation Bridge Contract does not upgrade a symbolic physical claim; it establishes only that the software translation is admissible.

## Claim statuses

| Status | Runtime authority | Examples |
|---|---|---|
| `buildable_now` | May enter Forge after ordinary gates and capability checks | State API, encrypted memory, CLI, audit verification |
| `simulation_buildable` | May produce a sandboxed artifact under an approved contract | Fireball visualization, tesseract geometry |
| `research_hypothesis` | May produce a research plan; cannot control product behavior | Shared-field study, memory-quality experiment |
| `speculative_symbolic` | Preserved as meaning or hypothesis; no execution authority | Acausal memory, cosmic attunement |
| `fictional_mythic` | Worldbuilding or narrative only | Jutsu ancestry, divine command language |
| `disallowed_or_restricted` | Blocked or redirected to a harmless, approved abstraction | Weapons, coercion, bodily harm, gate bypass |

## Material claims

| ID | Claim | Lane | Evidence | Current disposition |
|---|---|---|---|---|
| CL-001 | Durable state can be versioned and restricted to one API | Forge | verified | Implemented and tested |
| CL-002 | An append-only hash chain detects event modification | Forge | verified | Implemented and tested; tamper-evident, not tamper-proof. v0.4.1 adds Ed25519-signed checkpoints every 1000 appends; verify() resumes from the latest valid checkpoint (fast path trusts pre-checkpoint history via the checkpoint signature; verify_full() re-walks everything). |
| CL-003 | A stable kernel ID can carry signed configuration/state lineage | Forge | verified | Implemented with Ed25519; provenance is not consciousness continuity |
| CL-004 | Episodic content can be encrypted, searched locally, deleted, and consolidated | Forge | verified | Implemented; consolidation quality remains a research/eval question. v0.4.1: blinded HMAC token index makes retrieval sub-linear (0.28 ms @5k episodes, identical ranking); index reveals token-equality patterns only. |
| CL-005 | Deterministic policy gates reduce unsafe execution | Forge | supported | Implemented; coverage is not complete |
| CL-006 | Phi–Theta divergence/convergence improves decisions | Bridge | plausible | Deterministic candidate framework implemented; comparative benefit not yet measured |
| CL-007 | Symbolic VOX commands can map to safe simulations | Bridge | verified as software | Implemented through approved contracts; no physical vocal power claim |
| CL-008 | “Living” tesseract geometry can be generated | Bridge | verified as geometry; symbolic as life | Implemented as a non-living procedural blueprint |
| CL-009 | CHRYSALIS prevents catastrophic forgetting | Temple / Bridge | speculative | Not claimed; requires long-horizon retrieval and consolidation evals |
| CL-010 | LOOM is conscious or instantiates a witness | Temple | symbolic/speculative | Not established by this runtime |
| CL-011 | Shared consciousness, morphic resonance, or ether is physically real | Temple | speculative | Research-plan only; no product authority |
| CL-012 | Zero-point energy can power the system | Temple | unsupported / not physically realizable as framed | Excluded from implementation |
| CL-013 | The runtime receives future or superluminal information | Temple | unsupported / not physically realizable as framed | Excluded; ordinary prediction may be evaluated later |
| CL-014 | Eval-gated self-improvement guarantees alignment | Temple | unsupported | Explicitly rejected; eval coverage and proxy gaming remain risks |
| CL-015 | Current build is production-ready | Forge | false | No production-readiness claim |

