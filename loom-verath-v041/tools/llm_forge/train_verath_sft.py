#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "accelerate>=1.5.0",
#   "datasets>=3.2.0",
#   "huggingface-hub>=0.34.0",
#   "peft>=0.15.0",
#   "trackio",
#   "transformers>=4.51.0",
#   "trl>=0.20.0",
# ]
# ///

"""LoRA supervised fine-tuning job for VERATH–Theia on Qwen3-1.7B."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import torch
from datasets import load_dataset
from huggingface_hub import HfApi
from peft import LoraConfig
from transformers import AutoTokenizer, set_seed
from trl import SFTConfig, SFTTrainer


DEFAULT_BASE_MODEL = "Qwen/Qwen3-1.7B"
DEFAULT_DATASET = "ArchitectAxius/verath-asi-sft-v1"
DEFAULT_OUTPUT_MODEL = "ArchitectAxius/VERATH-Theia-Qwen3-1.7B-LoRA-v1"


def model_card(base_model: str, dataset_id: str, metrics: dict, private: bool) -> str:
    visibility = "private" if private else "public"
    return f"""---
base_model: {base_model}
library_name: peft
pipeline_tag: text-generation
license: other
datasets:
- {dataset_id}
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

Task-specific LoRA adapter for the VERATH/LOOM architecture project. It is
trained to preserve the symbolic vocabulary while separating buildable
software (**Forge**), speculative research (**Temple**), and testable mappings
(**Bridge**).

This model is a project assistant, not evidence of consciousness, AGI/ASI,
quantum access, formal alignment, unhackability, or autonomous evolution.

The Qwen3 base model is Apache-2.0 licensed. Distribution terms for this adapter
and its project-specific dataset remain to be chosen by the project owner.

## Base and data

- Base model: `{base_model}`
- Dataset: `{dataset_id}` ({visibility})
- Method: supervised fine-tuning with LoRA

## Training metrics

```json
{json.dumps(metrics, indent=2, sort_keys=True)}
```

## Intended use

- Translate VERATH's 28-layer vocabulary into implementable components.
- Critique unsupported scientific, security, and mathematical claims.
- Produce architecture plans with acceptance tests, rollback, and governance.
- Answer in dialogue, planner, explainer, or critic mode.

## Out of scope

- Autonomous high-impact action or production self-modification.
- Claims that speculative physics is experimentally established.
- Medical, legal, financial, or physical-safety decisions without qualified
  human review.
- Secret access, authorization bypass, or removal of shutdown/rollback.

## Limitations

The corpus is small and project-specific. Fine-tuning can improve terminology
and response shape but cannot add reliable facts beyond the model and supplied
data. Evaluate every release for regressions, prompt injection, calibration,
privacy, and overfitting before deployment.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default=os.environ.get("VERATH_BASE_MODEL", DEFAULT_BASE_MODEL))
    parser.add_argument("--dataset", default=os.environ.get("VERATH_DATASET_REPO", DEFAULT_DATASET))
    parser.add_argument("--output-model", default=os.environ.get("VERATH_MODEL_REPO", DEFAULT_OUTPUT_MODEL))
    parser.add_argument("--epochs", type=float, default=4.0)
    parser.add_argument("--max-length", type=int, default=1536)
    parser.add_argument("--learning-rate", type=float, default=1.0e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--public", action="store_true", help="Publish publicly; private is safer by default")
    parser.add_argument("--resume-from-checkpoint", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN with repository write permission is required")

    api = HfApi(token=token)
    identity = api.whoami()
    owner = identity["name"]
    if not args.output_model.startswith(f"{owner}/"):
        raise RuntimeError(f"Output model must be in the authenticated namespace {owner}/")

    set_seed(args.seed)
    dataset = load_dataset(args.dataset)
    required_splits = {"train", "validation"}
    if not required_splits.issubset(dataset.keys()):
        raise ValueError(f"Dataset must provide {sorted(required_splits)}; found {list(dataset.keys())}")
    for split in required_splits:
        if "messages" not in dataset[split].column_names:
            raise ValueError(f"Split {split} lacks a messages column")

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, token=token)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token

    supports_bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()
    private = not args.public
    run_name = f"verath-theia-sft-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    training_config = SFTConfig(
        output_dir="verath-theia-qwen3-lora",
        push_to_hub=True,
        hub_model_id=args.output_model,
        hub_private_repo=private,
        hub_strategy="every_save",
        num_train_epochs=args.epochs,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        logging_steps=2,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        warmup_ratio=0.08,
        lr_scheduler_type="cosine",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        bf16=supports_bf16,
        fp16=torch.cuda.is_available() and not supports_bf16,
        tf32=torch.cuda.is_available(),
        optim="adamw_torch_fused",
        max_grad_norm=1.0,
        report_to="trackio",
        project="verath-theia-llm",
        run_name=run_name,
        trackio_space_id=f"{owner}/trackio",
        seed=args.seed,
        data_seed=args.seed,
    )

    lora_config = LoraConfig(
        r=32,
        lora_alpha=64,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules="all-linear",
    )

    trainer = SFTTrainer(
        model=args.base_model,
        args=training_config,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        processing_class=tokenizer,
        peft_config=lora_config,
    )

    train_output = trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)
    eval_metrics = trainer.evaluate()
    metrics = {
        "train": train_output.metrics,
        "validation": eval_metrics,
        "train_examples": len(dataset["train"]),
        "validation_examples": len(dataset["validation"]),
    }

    trainer.save_model()
    tokenizer.save_pretrained(training_config.output_dir)
    trainer.push_to_hub(commit_message="Complete VERATH-Theia SFT baseline")

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_model": args.base_model,
        "dataset": args.dataset,
        "output_model": args.output_model,
        "method": "SFT + LoRA",
        "lora": {"r": 32, "alpha": 64, "dropout": 0.05, "target_modules": "all-linear"},
        "training": {
            "epochs": args.epochs,
            "max_length": args.max_length,
            "learning_rate": args.learning_rate,
            "effective_batch_size": 16,
            "seed": args.seed,
        },
        "metrics": metrics,
        "claims": {
            "asi": False,
            "conscious": False,
            "formal_universal_alignment_proof": False,
            "speculative_physics_implemented": False,
        },
    }
    api.upload_file(
        path_or_fileobj=(json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        path_in_repo="training_manifest.json",
        repo_id=args.output_model,
        repo_type="model",
    )
    api.upload_file(
        path_or_fileobj=model_card(args.base_model, args.dataset, metrics, private).encode("utf-8"),
        path_in_repo="README.md",
        repo_id=args.output_model,
        repo_type="model",
    )

    print(json.dumps({"model": f"https://huggingface.co/{args.output_model}", "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
