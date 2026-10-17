# Site Guide Contract

| Item | Decision |
| --- | --- |
| Public routes supported | `/`, `/research`, `/consultation` |
| Canonical content identifiers | `field`, `thesis`, `systems`, `repository`, `consultation` |
| Text activation | Keyboard-accessible inline trigger with a visible focus state |
| Transcript source | Server catalog of public-safe text and evidence status |
| Consent requirement | Required for external narration and questionnaire generation |
| Curated voice aliases | `narrator`, `educator`, `conversational` |
| Questionnaire output | Orientation, exactly three reflection questions, boundary statement |
| Offline export | Local UTF-8 `.txt`; title, evidence status, transcript, privacy note |
| Storage default | None for visitor answers, generated audio, or local downloads |
| Non-goals | Publishing, messaging, external actions, diagnosis, unbounded content analysis |

## Acceptance Criteria

- A visitor can open a guide from supported text using mouse or keyboard.
- Narration and questions remain disabled until consent is checked.
- Provider keys and provider voice IDs remain server-side.
- A downloaded transcript excludes visitor answers and contains evidence-status context.
- Tests cover catalog constraints, consent gating, download generation, and a bounded live provider credential check.
