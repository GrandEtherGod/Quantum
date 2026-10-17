# Verification Record

**Build:** 0.4.1
**Verified:** 2026-10-17 (refresh; supersedes the Build 0.3.0 record of 2026-09-02)
**Runtime:** Python 3.12.3, with the project's declared dependency `cryptography>=41`

## Commands

```bash
python -m compileall -q loom_verath tests examples
python -m unittest discover -s tests -t .
```

## Current evidence

- **105 runtime unit and integration tests pass** (fresh full run, 2026-10-17:
  "Ran 105 tests — OK", ~4.4 s), across 15 test modules: build isolation,
  classifier gates, CodePet workflow, evaluator, harm gate, harm-gate
  benchmark, integrated layers, ledger checkpoints, mechanics, memory
  identity, memory index, migrations, model loop, runtime replay, and
  state/ledger.
- Core, tests, and examples compile cleanly (`compileall`).
- The layered harm gate is covered by dedicated suites (harm gate: pattern
  layer and model-judge behavior incl. abstention; harm-gate benchmark:
  layered recall 0.88 / false-positive rate 0.0 / over-refusal 0.025 against
  the JBB-100-based set, vs. 0.04 recall for the pattern layer alone — as
  recorded in the measured-status record of 2026-10-10).
- The terminal-state attestation harness result (24/24 tasks attested through
  the real ledger; tamper, skip, and false-claim executors caught) stands as
  recorded 2026-10-10; it is a harness result, not part of the unit suite
  above.

## History

- 2026-09-02: Build 0.3.0 record — 41 runtime tests.
- 2026-10-10: harm-gate replacement landed (layered gate); suite at 105.
- 2026-10-17: this refresh — full suite re-executed and re-recorded for the
  public v0.4.1 tree, so this record and the measured-status figures agree.

## Interpretation

This evidence supports the declared local prototype contracts. It does not establish production security, complete policy coverage, universal alignment, AGI/ASI, consciousness, or speculative physics. Approved tests execute repository code; `network_os_enforced` remains `false` until the executor is moved into an independently verified network-denied container or microVM.
