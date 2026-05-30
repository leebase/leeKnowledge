# Strategic Brief — Design Spec

> Status: approved design, pre-implementation
> Date: 2026-05-30
> Author: Lee Harrington (with Claude Code as knowledge advisor)

## Purpose

Turn leeKnowledge from a passive archive of AI/Data reading into a **Strategic Output
Engine** for a Director of Data and AI: generate leadership deliverables on demand by
blending Lee's saved+enriched signal with fresh, fact-checked web research.

This is "Level 3" in `whats-next.md`. It is built as a conversational Claude Code skill
first (to prove the output shapes), with a path to harden the retrieval core into a
`leeknowledge` CLI command later.

## Context & motivation

The first real end-to-end pipeline run (2026-05-30) exposed why output generation — not
more pipeline layers — is the right next move:

- Enrichment quality is good (176/176 valid), but the corpus is **narrow and
  practitioner-flavored** (AI coding tools, agentic engineering), not director-level
  strategy material.
- The 4-topic leadership taxonomy does not fit the corpus (`enterprise-agents` absorbed
  89 of 176; `ai-governance` and `data-platform` got 4 each).
- Leadership metadata is not discriminating (68% `important`, 64% `cross-functional`).
- Extraction lost metadata for most rows (144/176 no author, 40 no date, 38 broken
  base64 node-IDs).

Grounding deliverables in **corpus + active web research** makes these foundation issues
non-blocking: the corpus becomes one evidence source among several, and current external
facts fill the gaps.

## Requirements (locked)

- **Job:** generate leadership deliverables (Strategic Output Engine).
- **Output types:** (1) exec/leadership update, (2) vendor/build-vs-buy decision brief,
  (3) strategy/roadmap memo.
- **Grounding:** per-artifact framing from Lee + corpus evidence + fact-checked web
  research (the `deep-research` skill).
- **Invocation:** conversational skill first; harden the proven flow to CLI later.
- **Non-goals:** changing the existing pipeline/DB/notes; fixing extraction or taxonomy
  (tracked separately); a web UI; auto-send (everything is a draft Lee edits).

## Architecture

A project-local Claude Code skill, `strategic-brief`, living at
`.claude/skills/strategic-brief/SKILL.md` (NOT the AgentFlow `skills/` contract dir,
which `init-agent --update` refreshes).

Five-step flow:

```
1. FRAME     Confirm artifact type + fill only the missing framing fields
             (the decision/question, audience, the ask). Don't interrogate.
2. RETRIEVE  Read state/app.db: FTS over the existing bookmarks_fts index on the
   (corpus)  topic, join enrichments (summary/tags/entities) and leadership_metadata
             (triage). Rank; pull top-N with vault note paths + source links → evidence pack.
3. RESEARCH  Invoke the deep-research skill on a refined query → current,
   (external) fact-checked findings with citations.
4. DRAFT     Fill the type-specific template, blending corpus + research, attributing
             every claim to its origin.
5. SAVE      Write vault/briefs/strategic/YYYY-MM-DD-<type>-<slug>.md (frontmatter +
             split source trail). Iterate conversationally.
```

**Boundaries.** The skill *reads* `state/app.db` (via existing `bookmarks_fts`, no new
code) and *reads* `deep-research`. It only *writes* new markdown under a new
`vault/briefs/strategic/` folder. It never touches the pipeline, the DB, or existing notes.

## Output templates

All three are Markdown + YAML frontmatter (`artifact_type`, `topic`, `generated_at`,
`framing`, evidence counts), end with a split **Source trail**, state a length target up
front, and are explicitly drafts for Lee to edit.

**① Exec / leadership update** (~1 page)
- TL;DR (2–3 sentences) · What's moving (3–5 items, each + why now) · Why it matters to us
  · Recommended attention (decide / watch / no action) · Source trail

**② Vendor / build-vs-buy decision brief** (~2 pages)
- Decision framing + criteria · Options compared (table: option × criteria) · Evidence per
  option (with provenance) · Risks & unknowns · Recommendation + confidence · What to
  validate next · Source trail

**③ Strategy / roadmap memo** (~2 pages)
- Position · Context & signals · Implications (operating model / platform / governance /
  org) · Recommended direction · Open questions · Source trail

## Trust contract (core feature)

Every substantive claim is tagged to one origin; the Source trail is split accordingly:

- `[corpus]` — from saved signal; links the vault note AND the original source. For the
  38 broken base64-ID bookmarks, link the vault note and mark the external link
  *unavailable* rather than emit a dead URL.
- `[research:DATE]` — from fresh deep-research; carries a real citation (URL + access date).
- `[interpretation]` — synthesis/judgment; always labeled, never disguised as fact.

No-fabrication guarantees:
- A claim not tied to corpus or a citation is dropped or explicitly `[interpretation]`.
- Numbers, vendor claims, and dates come from `[research]` (cited) or `[corpus]` (linked) —
  never invented.

## Edge handling

| Situation | Behavior |
|---|---|
| Corpus thin/empty on topic | State it plainly; proceed research-led; flag the gap |
| deep-research unavailable / skipped | Corpus-only draft, banner-marked "not externally verified" |
| Corpus vs research conflict | Surface the conflict explicitly; don't silently pick |
| Stale corpus items | Date-stamp corpus evidence so age is visible vs fresh research |

## Validation gate

Prompt-driven, so "tests" = an acceptance run before trust:
1. Generate one of each type against a real framing.
2. Verify: provenance tags correct & honest; every `[corpus]` link opens a real note;
   every `[research]` claim has a live citation; no unlabeled fabrication; genuinely
   faster than writing it by hand.
3. Fix any underperforming template before declaring it trusted.

Only a type that passes is a candidate for later CLI hardening.

## Later (out of scope for this slice)

- Approach B: extract step-2 retrieval into a tested `leeknowledge evidence`/`query`
  command as the CLI foundation.
- Foundation fixes (extraction metadata recovery, taxonomy that fits, grounded triage) —
  tracked separately; not required for this feature.
