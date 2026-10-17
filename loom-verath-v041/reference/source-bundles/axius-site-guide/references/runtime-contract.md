# Runtime Contract

Use strict server validation. Represent context and voice selections with enums rather than free strings.

```ts
const contextId = z.enum(["field", "thesis", "systems", "repository", "consultation"]);
const approvedVoice = z.enum(["narrator", "educator", "conversational"]);
const consent = z.literal(true);
```

Expose only these shapes to the browser:

```ts
type GuideContext = {
  contentId: string;
  title: string;
  transcript: string;
  status: string;
  voices: Array<{ id: string; label: string; descriptor: string }>;
};

type Questionnaire = {
  orientation: string;
  questions: [string, string, string];
  boundary: string;
};
```

Resolve the server-side voice alias to its provider ID only after validating consent. Enforce short canonical transcripts, a provider request timeout, provider-error fallback text, and no persistent audio cache unless a separate storage policy has been approved.
