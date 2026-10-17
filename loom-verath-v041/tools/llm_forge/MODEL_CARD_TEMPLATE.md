---
base_model: Qwen/Qwen3-1.7B
library_name: peft
pipeline_tag: text-generation
license: other
datasets:
- ArchitectAxius/verath-asi-sft-v1
language:
- en
tags:
- trl
- lora
- verath
- theia
- grounded-architecture
---

# VERATH–Theia Qwen3-1.7B LoRA v1

Status: **training package prepared; weights not yet trained**.

This task-specific adapter is designed to preserve the VERATH/LOOM symbolic
vocabulary while separating buildable software (**Forge**), speculative
research (**Temple**), and testable mappings (**Bridge**).

It is a project assistant, not evidence of consciousness, AGI/ASI, quantum
access, formal universal alignment, unhackability, or autonomous evolution.

The Qwen3 base model is Apache-2.0 licensed. Distribution terms for this adapter
and its project-specific dataset remain to be chosen by the project owner.

## Intended use

- Translate the 28-layer vocabulary into implementable components.
- Critique unsupported scientific, security, and mathematical claims.
- Produce architecture plans with acceptance tests, rollback, and governance.
- Answer in dialogue, planner, explainer, or critic mode.

## Training

- Base: `Qwen/Qwen3-1.7B`
- Method: SFT + LoRA (`r=32`, `alpha=64`, all linear modules)
- Dataset: 119 conversational examples; deterministic train/validation split
- Sequence length: 1,536 tokens
- Epochs: 4 baseline
- Monitoring: Trackio

Training and behavioral metrics must be inserted after an actual job completes.

## Limitations

The corpus is small and project-specific. Fine-tuning can improve terminology
and output structure but cannot validate the underlying speculative physics or
create capabilities absent from the base model and runtime. Require held-out
evaluation, human review, and rollback before any tool-enabled deployment.
