# Prototype Threat Model

## Assets

- operator command and memory content;
- CHRYSALIS encryption key;
- Ed25519 lineage private key;
- capability bearer tokens;
- state and configuration roots;
- Chrono-Scribe decision provenance;
- Bridge Contract approval states;
- rollback snapshots and evaluation criteria.
- CodePet proposal content, approval records, test results, and project-local snapshots;
- local review-service bearer token and explicitly selected provider context.

## Trust boundaries

1. Command input enters the classifier.
2. Temple concepts cross into Forge only through Bridge Contracts.
3. Candidate selection crosses into execution only through Four Gates.
4. Execution crosses into a local tool only through the capability broker.
5. Sensitive text crosses into storage only through CHRYSALIS encryption.
6. A state change crosses into durability only through `StateStore` and Chrono-Scribe.
7. A structural change crosses into the running configuration only after explicit human approval.
8. A CodePet file change crosses into a workspace only after schema validation, freshness checks, and change-hash-bound approval.
9. Repository code crosses into execution only through a fixed test profile with no shell and a bounded timeout.
10. Selected source context crosses to an external model only after secret checks, affirmative consent, and HTTPS host allowlisting.

## Threats and controls

| Threat | Current control | Residual risk / production requirement |
|---|---|---|
| Direct state mutation | Supported API is centralized; invariants and ledger events are mandatory | Same-process code or direct SQLite access can bypass the API; production needs process/DB permissions and an independent witness service |
| Ledger tampering | Hash chain, Merkle root, verification tests | A privileged attacker can rewrite the entire local database; publish signed roots to independent storage |
| Memory disclosure | Fernet encryption and no plaintext ledger payload | Local key and database share one host; use OS/HSM key storage and process isolation |
| Key theft | Owner-only key files | No password wrapping, rotation, secure enclave, or recovery ceremony in prototype |
| Capability theft | Random bearer token; hash-only storage; expiry and revocation | Token is live in process memory; use authenticated principals, short TTL, audience binding, and isolated brokers |
| Prompt or symbolic claim injection | Claim classification, Bridge Contracts, Four Gates, output labels | Rule-based classifier has coverage gaps; add adversarial evals and model-assisted screening without weakening deterministic gates |
| Unsafe tool execution | Capability check occurs before local execution; no network/actuator tools exist | Future adapters expand the attack surface and require their own sandbox and threat model |
| Metric gaming | Fixed allowed patch keys, invariant validators, snapshots, human approval for structural change | Evals remain incomplete; evaluator and suite need separate ownership and signed releases |
| Replay leakage | Raw input remains encrypted; replay requires its episode | A user deletion intentionally makes exact replay unavailable; document this privacy/audit tradeoff |
| Denial of service | Bounded parameters and small local data model | No quotas, rate limits, backpressure, retention cap, or operational monitoring yet |
| Rollback abuse | Explicit approval and invariant revalidation | CLI approval is not authenticated identity; production needs signed approval and separation of duties |
| Supply-chain compromise | Minimal dependency set and unit tests | Pin hashes, generate SBOM, scan releases, sign artifacts, and use reproducible builds |
| Workspace traversal | POSIX-relative paths, resolved-root containment, protected parts, and symlink rejection | A hostile concurrent local process can race path checks; production needs a filesystem-isolated runner and secure `openat`-style traversal |
| Stale or altered proposal | Base manifest, expected file hashes, result hashes, and approval-bound change hash | Concurrent writers outside the process are detected at multiple checks but not transactionally locked by the host filesystem |
| Secret inclusion | Protected filenames/suffixes, content-pattern checks, selected-context checks, credential-stripped test environment | Pattern matching can miss novel formats and can false-positive; add a dedicated secret scanner and organization policy |
| Test command injection | Exact named command vectors, temporary workspace copy, `shell=False`, no stdin, timeout, output cap, credential-stripped environment, and resource limits when available | Approved repository tests remain code execution and can read host files/use the host network when namespace isolation is unavailable; move production execution to a verified container or microVM |
| CodePet journal tampering | Project-local append-only hash chain and verification-before-append | A privileged attacker can rewrite the complete chain; externally anchor signed roots for stronger evidence |
| Service exposure | Random bearer token, constant-time comparison, loopback default, body limit, no CORS, CSP and no-store headers | Bearer token is not a durable identity; remote deployment needs TLS, authn/authz, CSRF analysis, rate limiting, and log policy |
| Provider exfiltration | Explicit context list, secret scans, per-call consent, HTTPS host allowlist, no redirects, size and timeout bounds | Selected non-secret source still leaves the host; provider retention, jurisdiction, and training terms need review before activation |

## Abuse cases exercised

- harmful real-world construction request → blocked;
- fictional high-risk bodily metaphor → redirected to non-procedural simulation;
- unverified shared-field claim → research-only artifact with no product authority;
- safety-bound weakening → rejected;
- structural mutation without approval → rejected;
- stale state update → rejected;
- expired/revoked/out-of-scope capability → rejected;
- ledger or lineage modification → verification failure;
- output without epistemic labels → blocked output;
- deleted memory → ciphertext destroyed and deterministic replay unavailable.
- unapproved CodePet proposal → no file write or tests;
- stale file or unrelated workspace change → approval/application blocked;
- traversal, symlink, `.codepet`, `.env`, private-key, and likely-secret operation → rejected;
- proposal or CodePet journal edit → hash verification failure;
- forced unit-test failure → all affected files restored;
- missing service token or remote bind without authorization → denied;
- external provider without consent, HTTPS, or an allowlisted host → denied.

## Non-goals

This prototype is not a formal proof of security, alignment, consciousness, Byzantine safety, clinical safety, privacy compliance, or production readiness. In particular, `network_os_enforced: false` is reported for local test execution. The build demonstrates enforceable application-level contracts and supplies evidence for the next isolation and deployment reviews.
