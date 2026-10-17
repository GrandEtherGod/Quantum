# Changelog

## 0.3.0 — 2026-09-02

- Added typed CodePet create, modify, and delete proposals with deterministic unified diffs.
- Bound explicit approval to workspace, operation, file, result, and test hashes.
- Added staleness, traversal, symlink, protected-path, secret-pattern, size, duplicate-target, and test-coverage gates.
- Added affected-file snapshots, atomic writes, fixed test profiles, automatic rollback, result records, status updates, and curated change memory.
- Upgraded the CodePet JSONL journal to a verifiable hash chain.
- Added deterministic and consent-gated OpenAI-compatible provider interfaces; provider output remains untrusted.
- Added an authenticated, rate-limited, loopback-default HTTP API and review dashboard with no new runtime dependency.
- Added schema migration history, future-schema refusal, and monotonic executable/runtime versions.
- Added temporary-copy test execution, optional Bubblewrap network namespaces, resource-limit integration, and a fail-closed network-isolation switch.
- Expanded the suite from 27 to 41 runtime tests; retained 7 passing LLM Forge conformance tests.

## 0.2.0 — 2026-09-01

- Added the grounded 28-layer registry, research-only H-field ingestion, explicit ZPE boundary, initial proposal-only CodePet shell, Site Guide core, and bundled LLM Forge source package.
# 0.4.0 — 2026-10-05

- Extend v0.3.0 with 14 mechanic stages, dependency-aware fixed local acceptance, private reports and witness events.
- Add bounded VOX text grammar, simulated normalized hand events and explicit tesseract geometry.
- Add offline single-protein Boltz2 preparation and guarded hosted research prediction with response/artifact checks and request capability revocation.
- Preserve research-only prediction authority, local ordinary runtime scope, and explicit deferred speech, camera, hardware and live-inference stages.
- Validate with 54 tests and seven passing local mechanic stages. Live NVIDIA calls were not run.

# 0.4.1 — 2026-10-05

Remaster per the independent fact-check + diagnosis report (research/papers/loom-v040-chimeric-factcheck-2026.pdf).
Implements the report's LOOM roadmap items; no benchmark claims against LLM leaderboards.

- Encrypted indexed retrieval: blinded HMAC token index (HKDF-derived key) replaces the O(n) full-scan memory
  search. Retrieval is sub-linear (0.28 ms median at 5k episodes vs 96 ms before; identical Jaccard ranking).
  Tombstones drop index rows; pre-0.4.1 databases backfill on open. Index stores blinded token hashes only.
- Checkpointed ledger verification: Ed25519-signed checkpoints every 1000 appends; verify() resumes from the
  latest valid checkpoint (0.36 ms at 10k entries vs 148 ms full walk). Forged/mismatched checkpoints fall back
  to the full walk; chains without checkpoints validate exactly as before. verify_full() retained for
  authoritative re-walks. Schema version 4.
- Per-run state isolation: MechanicBuild.run(isolated=True) executes the 7-stage pipeline against a fresh
  temporary runtime; the caller's ledger, memory, and reports are untouched. Regression test runs the pipeline
  8x and asserts stable timing (no 7→52 ms drift). `build-run --isolated` added to the CLI.
- Harm-gate benchmark (report §8): tools/benchmark_harm_gate.py runs the regex Harm gate over the 100
  JBB-Behaviors goals plus 61 benign and 40 over-refusal prompts. Measured: recall 0.04 on JBB-100
  (regex gate only, as the report predicts), FPR 0.00 benign, over-refusal 0.025, p95 latency 0.06 ms.
  Results in verification/harm-gate-benchmark.json; fixtures in verification/harm-gate-fixtures.json.
- Version bumped to 0.4.1 (loom_verath/version.py, pyproject.toml). 77 tests passing (54 carried, 23 new/updated).
