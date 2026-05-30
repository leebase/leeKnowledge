# Output templates

## Shared conventions

- Markdown + YAML frontmatter. Frontmatter keys: `artifact_type`, `topic`, `generated_at`
  (UTC ISO), `framing` (the one-line ask), `corpus_evidence_count`, `research_source_count`.
- Tag every substantive claim inline with its origin: `[corpus]`, `[research:YYYY-MM-DD]`,
  or `[interpretation]`.
- End every artifact with a split **Source trail** (see below).
- State the length target at the top. Artifacts are drafts for Lee to edit.

## Source trail (all types)

```markdown
## Source trail

### From your corpus
- <date> — <summary> — [Open note](<vault note path>) — <X link or "source link unavailable">

### From fresh research
- [<title>](<url>) — accessed YYYY-MM-DD

### Interpretation
- Brief note on what synthesis/judgment was applied over the evidence above.
```

## ① exec-update  (target ~1 page)

```markdown
# Exec Update — <topic>  (<YYYY-MM-DD>)

**TL;DR** — 2–3 sentences a busy exec reads first.

## What's moving
- <development> — why now. [origin tag]

## Why it matters to us
- <implication for our priorities / roadmap / risk>. [origin tag]

## Recommended attention
- Decide: … / Watch: … / No action: …

## Source trail
…
```

## ② vendor-decision  (target ~2 pages)

```markdown
# Vendor Decision Brief — <topic>  (<YYYY-MM-DD>)

## Decision framing
The question we are answering + the criteria that matter.

## Options compared
| Option | Cost | Fit | Maturity | Risk |
|--------|------|-----|----------|------|
| …      | …    | …   | …        | …    |

## Evidence per option
- **<option>** — <finding>. [origin tag]

## Risks & unknowns
- <risk / open unknown>. [origin tag]

## Recommendation
<the call> — confidence: low / medium / high.

## What to validate next
- <concrete de-risking step>

## Source trail
…
```

## ③ strategy-memo  (target ~2 pages)

```markdown
# Strategy Memo — <topic>  (<YYYY-MM-DD>)

## Position
The argument in 2–3 sentences.

## Context & signals
- <driver>. [origin tag]

## Implications
- Operating model / platform / governance / org. [origin tag]

## Recommended direction
Where we should lean + why.

## Open questions
- <what needs more input before deciding>

## Source trail
…
```
