# Site Guide Privacy and Authority Boundaries

Treat the guide as a **visitor-controlled explainer**, not an agent with authority.

| Area | Required control |
| --- | --- |
| Content | Maintain a server-owned catalog of public-safe passages. Never accept raw DOM or arbitrary client text for provider calls. |
| Consent | Require an unchecked affirmative control before LLM or TTS calls. Local transcript download does not need provider consent. |
| Voice | Use a curated alias-to-provider-ID map on the server. Never return API keys or unrestricted provider voice IDs. |
| Questions | Generate private reflection questions only. Do not solicit health, legal, financial, identity, or other sensitive information. |
| Storage | Do not store answers, audio, or transcript downloads by default. State this in the UI. |
| Actions | Do not publish, submit, send, purchase, delete, or modify external systems. Offer explicit next steps only. |
| Claims | Preserve evidence labels and uncertainty. Do not let generated wording elevate a research concept into a verified capability. |

If persistence is requested later, add a separate consent flow, data-retention policy, access controls, and deletion path before saving any visitor material.
