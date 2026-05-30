---
name: strategic-brief
description: Use when Lee asks to draft a leadership deliverable — an exec/leadership update, a vendor / build-vs-buy decision brief, or a strategy/roadmap memo — from his leeKnowledge corpus plus fresh research. Triggers on phrases like "draft a brief on", "vendor brief", "exec update on", "strategy memo about", "prep me on".
---

# Strategic Brief

Generate a leadership deliverable by blending Lee's saved+enriched signal (the
leeKnowledge corpus) with fact-checked web research. Output is a vault-native Markdown
draft Lee edits — never auto-sent.

## When to use

Use when Lee wants one of three artifacts:
- **exec-update** — "what's moving in Data & AI and what it means for us"
- **vendor-decision** — a build-vs-buy / tool / model / platform comparison with a recommendation
- **strategy-memo** — a position piece feeding operating-model / platform / governance / roadmap decisions

If the request is just "what have I seen about X?" (a lookup, not a deliverable), answer
directly from the corpus instead — do not invoke the full flow.

## The five-step flow

1. **Frame** — confirm the artifact type and fill only missing framing fields.
2. **Retrieve** corpus evidence — see `references/corpus-retrieval.md`.
3. **Research** — run the deep-research skill for current, cited external findings.
4. **Draft** — fill the typed template from `references/templates.md`.
5. **Save** — write to `vault/briefs/strategic/` and iterate with Lee.

(Each step is detailed below.)

## Step 1 — Frame

Determine the artifact type (exec-update / vendor-decision / strategy-memo). Then ask
**only for missing** framing fields, in one message:
- The specific question or decision.
- The audience (for exec-update / who reads this).
- Any internal context Lee wants injected (his org, constraints, the live initiative).

Do not interrogate. If type and a usable topic are already clear, confirm in one line and proceed.

## Step 2 — Retrieve corpus evidence

Follow `references/corpus-retrieval.md`. Derive FTS match terms from the framing, run the
query, resolve note paths, and assemble an evidence list noting `broken_source_link`. For
staleness, prefer `created_at` (when the idea is from); fall back to `first_seen_at`
(ingestion time) when `created_at` is null (~40 rows). If empty, flag the gap and continue
research-led.

## Step 3 — Research

Invoke the `deep-research` skill with a query refined from the framing (and shaped by the
gaps the corpus did NOT cover). Capture findings with citations (URL + access date). If
deep-research is unavailable or Lee skips it, produce a corpus-only draft banner-marked
"not externally verified".

## Step 4 — Draft

Load `references/templates.md`, pick the type's template, and fill it by blending corpus
evidence and research. Apply the trust contract below to every substantive claim.

## Step 5 — Save

Write to `vault/briefs/strategic/<YYYY-MM-DD>-<type>-<slug>.md` (create the folder if
missing; date is UTC and must match `generated_at`; slug = kebab-cased topic, ascii, max
~60 chars). Populate frontmatter: `artifact_type`, `topic`, `generated_at` (UTC ISO),
`framing`, `corpus_evidence_count`, `research_source_count`. Print the path and offer to
revise. Never auto-send.

## Trust contract (non-negotiable)

Tag every substantive claim:
- `[corpus]` — links the vault note AND the X source; if `broken_source_link=1`, mark the
  external link "unavailable" rather than emit a dead URL.
- `[research:YYYY-MM-DD]` — carries a real citation (URL + access date).
- `[interpretation]` — synthesis/judgment; always labeled, never disguised as fact.

No-fabrication: a claim not tied to corpus or a citation is dropped or marked
`[interpretation]`. Numbers, vendor claims, and dates come only from `[research]` (cited)
or `[corpus]` (linked) — never invented.

Trail mapping (the Source trail must be verifiable against the body):
- Every inline `[corpus]` claim has a matching entry under "From your corpus"; every
  `[research:DATE]` claim under "From fresh research". Tag and trail are 1:1.
- `[interpretation]` claims carry no citation but must still be summarized in the
  "Interpretation" trail section.
- When corpus and fresh research **corroborate** the same point, tag it `[research:DATE]`
  (the current, citable source) and cross-reference the corpus note in the corpus trail —
  do not manufacture a conflict. Reserve the conflict edge case for genuine disagreement.

## Edge handling

- Corpus thin/empty → say so; proceed research-led; flag the gap.
- deep-research unavailable/skipped → corpus-only draft, banner-marked unverified.
- Corpus vs research conflict → surface the conflict; do not silently pick.
- Stale corpus items → date-stamp corpus evidence so age shows against fresh research.
