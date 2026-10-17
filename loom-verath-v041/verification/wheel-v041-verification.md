# LOOM v0.4.1 Wheel — Build & Verification Record

**Date:** 2026-10-10 · **Verdict: VERIFIED** · **Gate:** build and verify
only — no commit, push, publication, or release was performed.

**Seal:** the facts below are recorded in
`verification/wheel-v041-ledger.jsonl` (Chrono-Scribe v2 hash chain,
8 events, verification `ok: true`, tip certificate
`5ed7f1e8d2e1b559c9bd6152ac3d4349e102fac04cd5c1ec5f8df8484210d3c7545480b2df0530c0b8e11bb8068cd918b187e5a5571c860f652045c1b9cdaae7`).

## The defect this replaces

The in-tree wheel was `loom_verath_runtime-0.4.0-py3-none-any.whl` —
METADATA version **0.4.0**, 40 files, containing neither `harm_gate.py`
nor `model_loop.py` (both are 0.4.1 code). The filed source has declared
0.4.1 all along (`pyproject.toml`, `loom_verath/version.py`); the 0.4.1
release was simply never packaged. Stale wheel SHA-256:
`5623c886ce61845577aa7c38d4e370905f45abc38c7f977a03a2790944530688`
(a copy is preserved in the build record; the stale file itself was
removed from `build-artifacts/` when the verified wheel replaced it).

## The rebuilt wheel

| | |
|---|---|
| File | `build-artifacts/loom_verath_runtime-0.4.1-py3-none-any.whl` |
| METADATA version | **0.4.1** |
| Size | 87,895 bytes |
| SHA-256 | `3c39679b0bec5a220c6a9a94a6ce48063a432145c0d0ea06b9e2e9ed9a4489f3` |
| Built from | the filed v0.4.1 source in this directory, `python -m build --wheel` |

## Author correction (2026-10-10, owner's standing rule)

At the owner's direction, the package author of record is his legal
name: the rebuilt wheel's METADATA reads **Author: Joseph Conely,
Axius Enterprises** (pyproject authors updated accordingly), and the
wheel was rebuilt and re-verified in full — content still 39/39
hash-identical to the filed source, install smoke re-passed. The
first build's SHA-256 (`8c1eb4db…`) is superseded by the one above;
both builds and the correction are sealed in the ledger
(`author-corrected`, `wheel-rebuilt` events).

## Content verification (against the filed source, not the stale wheel)

- Package files compared: **39** · SHA-256 matched: **39** · mismatched: **0**
- Source files missing from the wheel: **0** · extra files in the wheel: **0**

The wheel's contents are byte-identical to the filed v0.4.1 source.

## Test result (filed source, full suite)

- **105 tests.** Nine consecutive full runs were made: run 1 showed a
  single failure whose test name was not captured; runs 2–9 were all
  **OK (105/105)**. The same uncaptured single failure was seen once
  during the harm-gate build and likewise never reproduced (7 runs) —
  it is recorded here rather than hidden, and remains an open flake
  to identify.
- Note on the older "84/84" figure: that was the v0.4.1-remaster suite.
  The filed source has since gained the model-loop and harm-gate test
  files; 105 is the current, correct total.

## Install smoke test

In a fresh virtual environment, installed from the wheel file alone:

- Distribution version reports **0.4.1**; `loom_verath.version.VERSION`
  is **0.4.1**.
- The 0.4.1-only modules `loom_verath.harm_gate` and
  `loom_verath.model_loop` import from the installed package.
- The `loom-verath` command-line entry point runs.

## What this verification does not claim

Packaging correctness only: that this wheel is the filed 0.4.1 source,
installable and self-consistent. It is not a release, a security
review, or an endorsement of the runtime beyond its existing evidence
states.
