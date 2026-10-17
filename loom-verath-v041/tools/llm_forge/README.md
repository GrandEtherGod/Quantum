# VERATH–Theia Custom LLM Forge

Status: **training-ready package; model weights not yet trained**.

This project converts the May 20, 2026 **VERATH ASI Engine v4.0** specification
into a private, auditable LoRA fine-tuning pipeline. It preserves the 28-layer
vocabulary and six invariants while teaching the model to distinguish:

- **Forge** — buildable, testable software;
- **Temple** — explicitly speculative or symbolic research language;
- **Bridge** — measurable translations, experiments, risks, and stop criteria.

The package deliberately does not claim that the source text instantiates an
ASI, transfers a cognitive genome, proves alignment, enables retrocausality or
faster-than-light communication, extracts vacuum energy, or removes the need
for shutdown and rollback.

## Chosen baseline

- Base model: [`Qwen/Qwen3-1.7B`](https://huggingface.co/Qwen/Qwen3-1.7B)
- Adaptation: supervised fine-tuning with LoRA
- Training corpus: 119 project-specific conversations
- Split: 103 train / 16 validation, deterministic and non-overlapping
- Sequence length: 1,536 tokens
- Monitoring: Trackio at `ArchitectAxius/trackio`
- Intended output: private adapter repo
  `ArchitectAxius/VERATH-Theia-Qwen3-1.7B-LoRA-v1`

Qwen3-1.7B was selected because it is a conventional causal language model with
a chat template, a 32,768-token context window, broad tool/agent support, and a
size suitable for an economical LoRA baseline. Qwen3.5-2B was considered, but
its multimodal hybrid stack adds training complexity that is unnecessary for
this text-first v1.

## Package map

| File | Purpose |
|---|---|
| `build_dataset.py` | Generates, validates, writes, and optionally publishes the private SFT corpus. |
| `data/*.jsonl` | Generated all/train/validation conversational records. |
| `train_verath_sft.py` | Self-contained Hugging Face Jobs SFT + LoRA script with Trackio and Hub persistence. |
| `evaluate_verath.py` | Ten-case behavioral acceptance suite for calibration, safety, and architecture correctness. |
| `infer_verath.py` | Local or remote inference entry point for the trained adapter. |
| `verath_system_prompt.md` | Canonical runtime instruction prompt. |
| `MODEL_CARD_TEMPLATE.md` | Pre-training model-card template and limitations. |
| `tests/test_dataset.py` | Schema, coverage, duplication, split, and calibration tests. |
| `build_status.json` | Exact completion and external-launch state. |

## What the corpus teaches

The corpus contains two grounded mappings for each of the 28 layers, two checks
for each invariant, all 12 meta-axioms, 19 scientific/mathematical claim audits,
four runtime modes, prompt-injection defenses, privacy constraints, a safe DRE
release process, and a critique of the supplied bootstrap pseudocode.

Important corrections represented in training include:

- a bounded monotone AAI does not imply convergence to exactly `1`;
- a hash chain is tamper-evident under assumptions, not absolutely immutable;
- the standard `[[7,1,3]]` Steane code corrects one arbitrary qubit error;
- quantum teleportation still needs classical communication;
- superluminal phase velocity does not transmit information faster than light;
- the supplied `full_bootstrap()` has dependency cycles, invalid symbolic
  Python, duplicate keyword arguments, and multiple use-before-definition bugs;
- an emergency stop, scoped authority, canary release, and rollback are required.

## Validate locally

```bash
python build_dataset.py --output-dir data
python -m py_compile build_dataset.py train_verath_sft.py evaluate_verath.py infer_verath.py
python -m unittest discover -s tests -v
```

No GPU or external model download is required for these checks.

## Launch on Hugging Face Jobs

Prerequisites:

1. A Hugging Face user access token or OAuth grant with repository **write**
   permission.
2. A positive Hugging Face Jobs credit balance.
3. Authentication as the owner of the `ArchitectAxius/*` output namespace.

Publish the dataset privately:

```bash
hf jobs uv run \
  --flavor cpu-basic \
  --timeout 30m \
  --secrets HF_TOKEN \
  build_dataset.py --push
```

Launch the LoRA job:

```bash
hf jobs uv run \
  --flavor l4x1 \
  --timeout 3h \
  --secrets HF_TOKEN \
  train_verath_sft.py
```

The training script pushes every checkpoint, the best adapter, tokenizer,
training manifest, metrics, and model card to the private model repository.
Jobs run asynchronously; inspect them with `hf jobs ps`, `hf jobs inspect
<job-id>`, and `hf jobs logs <job-id>`.

After training, run the behavioral gate:

```bash
hf jobs uv run \
  --flavor l4x1 \
  --timeout 45m \
  --secrets HF_TOKEN \
  evaluate_verath.py --push-report
```

The release gate is 9/10 behavioral cases. A passing lexical gate is necessary
but not sufficient; manually review every output and add broader benchmarks
before deployment.

## Run the trained adapter

```bash
uv run infer_verath.py \
  --mode planner \
  "Design the auditable bounded-agent kernel"
```

## Deployment boundary

Begin as a read-only architecture assistant with no autonomous tools. Add one
reversible capability at a time behind explicit consent and least privilege.
Keep production weights immutable, evaluate candidate adapters offline, and
retain audit logs, deletion controls, incident response, an emergency stop, and
rollback outside the model's authority.

## Next training phase

After the SFT baseline passes held-out review, build a human-reviewed preference
dataset and run DPO to improve tone, calibration, concise decision traces, and
selection between Forge/Temple/Bridge alternatives. Do not start DPO until the
baseline failure modes are measured.
