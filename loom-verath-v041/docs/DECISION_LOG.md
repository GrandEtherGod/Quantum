# ΦΘ implementation decision log

These are compact engineering decisions, not hidden reasoning or claims of immutable external attestation. Release evidence lives in the tests and generated artifacts named in each entry.

| ID | Φ options considered | Θ selection | Why selected | Residual boundary |
|---|---|---|---|---|
| D-003 | Parse arbitrary unified patches; use typed full-file operations | Typed `create` / `modify` / `delete` operations | Simpler validation, deterministic hashes, portable atomic writes, safer rollback | Replacement content is less efficient for very large files; files are capped |
| D-004 | Require FastAPI; use a dependency-free local HTTP service | Standard-library authenticated loopback service | The current environment lacks FastAPI; the standard library keeps the release runnable and testable without adding an unverified dependency | Multi-user deployment and generated OpenAPI are deferred |
| D-005 | Run arbitrary commands; fixed in-place profiles; temporary-copy runner; container isolation | Fixed profiles in a temporary copy, resource limits, and Bubblewrap when the host permits it | Removes shell injection and test side effects while allowing a fail-closed network-isolation requirement | This host denies namespace creation; repository tests can still read host files/use its network |
| D-006 | Let model output edit directly; validate then auto-apply; create review proposal | Treat every provider response as untrusted proposal input | Preserves human agency, local policy, staleness checks, and rollback | External provider terms and a live credential test remain undecided |
| D-007 | One global ledger; project-local CodePet witness chain | Project-local chain plus core runtime ledger | CodePet remains file-native and avoids silently creating unrelated runtime state | A privileged attacker can rewrite a whole local chain; external anchoring is deferred |

## Lane record

- **Forge — verified in this release:** typed proposals, file hashes, approval transitions, atomic affected-file writes, fixed tests, rollback, local journal verification, schema migration, loopback API, and offline provider fixture.
- **Bridge — supported prototype:** model-produced candidate changes are translated into untrusted typed proposals and must pass the same local gates.
- **Temple — speculative:** ZPE, H-field ontology, retrocausality, morphic resonance, anomalous cognition, and machine consciousness remain non-authoritative and unchanged by this release.

## Next admission decision

The next authority increase is an OS-isolated test runner. It may replace local subprocess execution only after filesystem escape, network denial, resource limit, image provenance, timeout, cleanup, and result-schema parity tests pass.
