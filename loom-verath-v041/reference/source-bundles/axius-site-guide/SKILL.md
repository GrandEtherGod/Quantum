---
name: axius-site-guide
description: Build a privacy-preserving interactive Site Guide for public websites. Use when users ask to make selected text or paragraphs speakable, add an AI guide, offer a curated voice picker, generate contextual questionnaires, provide local transcript downloads, or build an opt-in autonomous-style website guide.
---

# AXIUS Site Guide

Build a **user-initiated, advisory** guide for public site content. It may explain selected passages, narrate an approved transcript in a visitor-selected voice, generate bounded reflection questions, and create local offline transcript files. It must never present itself as autonomous authority or perform external actions.

## Required Boundaries

Read [privacy-boundaries.md](references/privacy-boundaries.md) before implementation. Keep canonical guide content on the server. Do not send arbitrary page DOM, visitor answers, secrets, or private source material to an LLM or TTS provider.

Require affirmative consent before external AI/TTS calls. Keep voice-provider keys server-only using the project secret mechanism. Return only a curated voice catalog; never expose provider credentials or arbitrary voice IDs to the browser. Generate offline transcript files locally with `Blob` and `URL.createObjectURL`; do not upload them or store visitor answers.

## Workflow

### 1. Define the Guide Contract

Read [site-guide-contract.md](templates/site-guide-contract.md). Create a fixed context catalog with opaque identifiers, a title, public-safe transcript, and evidence-status label. Map public text activators to those identifiers; do not trust client-supplied transcript text.

Use an explicit content taxonomy such as `public positioning`, `research framing`, `evidence-status explanation`, `repository guide`, and `consultation guide`. If the site makes speculative technical claims, retain visible distinctions between research, specification, scaffold, implementation, symbol, and gap.

### 2. Build Protected Server Procedures

Read [runtime-contract.md](references/runtime-contract.md) before adding routes. Validate every input with a strict enum for `contentId`, approved voice aliases, and a literal consent flag. Create three public procedures:

| Procedure | Input | Output | Boundary |
| --- | --- | --- | --- |
| `context` | `contentId` | transcript, status, curated voices | No AI/provider call |
| `questionnaire` | `contentId`, `consent: true` | structured orientation, three questions, boundary | LLM uses only canonical transcript |
| `narrate` | `contentId`, approved voice, `consent: true` | temporary audio payload and transcript | TTS called server-side only |

Use a constrained JSON schema for questionnaires. Ask reflective, factual questions only; avoid assessments, diagnoses, sensitive-data prompts, claims validation, or autonomous recommendations.

### 3. Create the Client Experience

Provide keyboard-accessible passage activation with a visible focus state. Open a dialog or side panel containing the transcript and evidence status. Place a plain-language consent checkbox before any narration or questionnaire action; leave those buttons disabled until consent is checked.

Show a curated voice selector, a narration state, errors that preserve transcript access, question output with `aria-live`, and a concise privacy statement. Support `prefers-reduced-motion`, mobile layouts, and an escape/close path.

### 4. Add Offline Transcript Files

Use `scripts/generate_offline_transcript.mjs` as a deterministic reference for transcript structure. Write browser downloads with `Blob`, `URL.createObjectURL`, an explicit `.txt` filename, click dispatch, and `URL.revokeObjectURL`. Include title, evidence status, public source label, transcript, and a privacy note. Exclude visitor responses and questionnaire output.

### 5. Validate Before Delivery

Write unit/UI tests for the context catalog, consent gating, voice alias selection, local download formatting, and download trigger. Add one lightweight live provider credential test after requesting the secret. Verify a real narration and questionnaire response only with public-safe context. Run tests, type check, production build, desktop/mobile screenshots, then create a checkpoint.

## Resources

Read [privacy-boundaries.md](references/privacy-boundaries.md) before designing consent and storage behavior. Read [runtime-contract.md](references/runtime-contract.md) before server implementation. Use [site-guide-contract.md](templates/site-guide-contract.md) to scope a new guide. Use `scripts/generate_offline_transcript.mjs` for a reusable offline `.txt` transcript generator.
