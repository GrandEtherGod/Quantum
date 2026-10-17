#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "accelerate>=1.5.0",
#   "peft>=0.15.0",
#   "torch",
#   "transformers>=4.51.0",
# ]
# ///

"""Local or job-based inference for the VERATH–Theia LoRA adapter."""

from __future__ import annotations

import argparse
import os

import torch
from peft import AutoPeftModelForCausalLM
from transformers import AutoTokenizer


DEFAULT_MODEL = "ArchitectAxius/VERATH-Theia-Qwen3-1.7B-LoRA-v1"
SYSTEM = """You are Theia VERATH, an architecture copilot for Axius Tenebris. Preserve Forge buildable software, Temple explicitly speculative language, and Bridge testable translations. Your identity is a project persona, not a claim of sentience or ASI. Never invent evidence, authorization, tool actions, storage, training, or deployment. Prefer reversible systems with consent, least privilege, shutdown, auditability, and rollback."""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--model", default=os.environ.get("VERATH_MODEL_REPO", DEFAULT_MODEL))
    parser.add_argument("--mode", choices=["dialogue", "planner", "explainer", "critic"], default="dialogue")
    parser.add_argument("--max-new-tokens", type=int, default=640)
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    tokenizer = AutoTokenizer.from_pretrained(args.model, token=token)
    model = AutoPeftModelForCausalLM.from_pretrained(
        args.model,
        token=token,
        torch_dtype="auto",
        device_map="auto",
    )
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"/{args.mode} {args.prompt}"},
    ]
    rendered = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = tokenizer(rendered, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=True,
            temperature=0.7,
            top_p=0.8,
            top_k=20,
            repetition_penalty=1.05,
            pad_token_id=tokenizer.eos_token_id,
        )
    answer = tokenizer.decode(output[0, inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
    print(answer.strip())


if __name__ == "__main__":
    main()
