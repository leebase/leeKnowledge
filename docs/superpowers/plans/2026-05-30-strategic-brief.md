# Strategic Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a project-local Claude Code skill, `strategic-brief`, that generates leadership deliverables (exec update, vendor decision brief, strategy memo) by blending Lee's corpus with fact-checked web research.

**Architecture:** A `SKILL.md` orchestrator drives a five-step flow (frame → retrieve corpus evidence → deep-research → draft into a typed template → save to the vault). Corpus retrieval is a documented `sqlite3` query against the existing `bookmarks_fts` index (no new Python). The three output templates and the retrieval query live as reference files loaded on demand. Output is vault-native Markdown with a split `[corpus]`/`[research]`/`[interpretation]` source trail.

**Tech Stack:** Claude Code skill format (Markdown + YAML frontmatter), SQLite FTS5 (`bookmarks_fts`, `bm25`), the `deep-research` skill, the existing `vault/` Markdown conventions.

**Spec:** `docs/superpowers/specs/2026-05-30-strategic-brief-design.md`

---

## File Structure

- Create: `.claude/skills/strategic-brief/SKILL.md` — orchestrator: when-to-use, the five-step flow, the trust contract, edge handling, save conventions.
- Create: `.claude/skills/strategic-brief/references/corpus-retrieval.md` — the exact `sqlite3` evidence query + note-path resolution + broken-link handling.
- Create: `.claude/skills/strategic-brief/references/templates.md` — the three typed output templates and shared conventions.
- Output (created at runtime, not committed): `vault/briefs/strategic/YYYY-MM-DD-<type>-<slug>.md`.

Rationale: SKILL.md stays lean (loaded every invocation); the query and templates are progressive-disclosure references the skill reads only when it reaches those steps.

---

### Task 1: Scaffold the skill with frontmatter and flow skeleton

**Files:**
- Create: `.claude/skills/strategic-brief/SKILL.md`

- [ ] **Step 1: Create SKILL.md with frontmatter and the five-step skeleton**

```markdown
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
```

- [ ] **Step 2: Verify the file exists and has valid frontmatter**

Run: `head -5 .claude/skills/strategic-brief/SKILL.md && echo "---" && test -f .claude/skills/strategic-brief/SKILL.md && echo OK`
Expected: prints the YAML frontmatter (`name:` and `description:` present) followed by `OK`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/strategic-brief/SKILL.md
git commit -m "feat(strategic-brief): scaffold skill with flow skeleton"
```

---

### Task 2: Write and verify the corpus-retrieval reference

**Files:**
- Create: `.claude/skills/strategic-brief/references/corpus-retrieval.md`

- [ ] **Step 1: Write the retrieval reference with the exact query**

````markdown
# Corpus retrieval

Retrieve ranked evidence from `state/app.db` for the framing's topic. No new code — run
this `sqlite3` query directly.

## Query

Replace `QUERY` with FTS5 match terms derived from the framing (OR-join key terms, e.g.
`agent OR agentic OR orchestration`). Replace `N` with the evidence cap (default 25).

```bash
sqlite3 -json state/app.db "
SELECT
  b.tweet_id,
  b.source_name,
  b.author_username,
  b.created_at,
  b.first_seen_at,
  b.source_ref,
  e.summary, e.tags, e.entities, e.topic,
  m.strategic_relevance, m.time_horizon, m.organizational_impact, m.leadership_question,
  CASE WHEN b.tweet_id GLOB '*[A-Za-z=]*' THEN 1 ELSE 0 END AS broken_source_link,
  bm25(bookmarks_fts) AS rank
FROM bookmarks_fts
JOIN bookmarks b ON b.rowid = bookmarks_fts.rowid
LEFT JOIN enrichments e ON e.tweet_id = b.tweet_id
LEFT JOIN leadership_metadata m ON m.tweet_id = b.tweet_id
WHERE bookmarks_fts MATCH 'QUERY'
ORDER BY rank
LIMIT N;"
```

Lower `bm25` rank = more relevant (FTS5 returns ascending relevance). `ORDER BY rank` is correct.

## Resolve the vault note path for an evidence item

Exported note filenames end with the lowercased `tweet_id`. Find the note path by globbing:

```bash
ls vault/**/*<tweet_id-lowercased>*.md 2>/dev/null
```

Use that path for the `[corpus]` "Open note" link.

## Broken source links

When `broken_source_link = 1` (base64 node-ID, ~38 rows), the X URL in `source_ref` will
not resolve. Link the vault note as primary and mark the external link **unavailable** —
do NOT emit a dead URL.

## Empty result

If the query returns no rows, the corpus is thin on this topic. Say so plainly, proceed
research-led, and flag the gap in the artifact.
````

- [ ] **Step 2: Verify the query runs and returns shaped evidence**

Run:
```bash
sqlite3 -json state/app.db "SELECT b.tweet_id, e.summary, m.strategic_relevance, CASE WHEN b.tweet_id GLOB '*[A-Za-z=]*' THEN 1 ELSE 0 END AS broken FROM bookmarks_fts JOIN bookmarks b ON b.rowid=bookmarks_fts.rowid LEFT JOIN enrichments e ON e.tweet_id=b.tweet_id LEFT JOIN leadership_metadata m ON m.tweet_id=b.tweet_id WHERE bookmarks_fts MATCH 'agent OR agentic' ORDER BY bm25(bookmarks_fts) LIMIT 5;"
```
Expected: JSON array of up to 5 rows, each with `tweet_id`, a non-null `summary`, a `strategic_relevance`, and a `broken` flag (0 or 1). Confirms FTS, the joins, and broken-ID detection all work.

- [ ] **Step 3: Verify note-path resolution finds a real note**

Run: `id=$(sqlite3 state/app.db "SELECT lower(tweet_id) FROM bookmarks WHERE source_name='x' LIMIT 1;"); ls vault/**/*"$id"*.md 2>/dev/null | head`
Expected: prints at least one real `vault/2026/MM/...md` path. Confirms `[corpus]` links will resolve.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/strategic-brief/references/corpus-retrieval.md
git commit -m "feat(strategic-brief): add verified corpus-retrieval reference"
```

---

### Task 3: Write the three output templates

**Files:**
- Create: `.claude/skills/strategic-brief/references/templates.md`

- [ ] **Step 1: Write the templates reference with all three shapes and shared conventions**

````markdown
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
````

- [ ] **Step 2: Verify every template has the required sections and the source-trail split**

Run:
```bash
f=.claude/skills/strategic-brief/references/templates.md
for h in "exec-update" "vendor-decision" "strategy-memo" "From your corpus" "From fresh research" "Interpretation"; do grep -q "$h" "$f" && echo "OK: $h" || echo "MISSING: $h"; done
```
Expected: six `OK:` lines, no `MISSING:`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/strategic-brief/references/templates.md
git commit -m "feat(strategic-brief): add three typed output templates"
```

---

### Task 4: Complete the SKILL.md body (steps, trust contract, edge handling, save)

**Files:**
- Modify: `.claude/skills/strategic-brief/SKILL.md`

- [ ] **Step 1: Append the detailed step instructions, trust contract, edge handling, and save conventions**

Append the following below the skeleton:

````markdown
## Step 1 — Frame

Determine the artifact type (exec-update / vendor-decision / strategy-memo). Then ask
**only for missing** framing fields, in one message:
- The specific question or decision.
- The audience (for exec-update / who reads this).
- Any internal context Lee wants injected (his org, constraints, the live initiative).

Do not interrogate. If type and a usable topic are already clear, confirm in one line and proceed.

## Step 2 — Retrieve corpus evidence

Follow `references/corpus-retrieval.md`. Derive FTS match terms from the framing, run the
query, resolve note paths, and assemble an evidence list noting `broken_source_link` and
`created_at`/`first_seen_at` (for staleness). If empty, flag the gap and continue research-led.

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
missing; slug = kebab-cased topic). Populate frontmatter counts. Print the path and offer
to revise. Never auto-send.

## Trust contract (non-negotiable)

Tag every substantive claim:
- `[corpus]` — links the vault note AND the X source; if `broken_source_link=1`, mark the
  external link "unavailable" rather than emit a dead URL.
- `[research:YYYY-MM-DD]` — carries a real citation (URL + access date).
- `[interpretation]` — synthesis/judgment; always labeled, never disguised as fact.

No-fabrication: a claim not tied to corpus or a citation is dropped or marked
`[interpretation]`. Numbers, vendor claims, and dates come only from `[research]` (cited)
or `[corpus]` (linked) — never invented.

## Edge handling

- Corpus thin/empty → say so; proceed research-led; flag the gap.
- deep-research unavailable/skipped → corpus-only draft, banner-marked unverified.
- Corpus vs research conflict → surface the conflict; do not silently pick.
- Stale corpus items → date-stamp corpus evidence so age shows against fresh research.
````

- [ ] **Step 2: Verify SKILL.md references both reference files and covers the contract**

Run:
```bash
f=.claude/skills/strategic-brief/SKILL.md
for h in "references/corpus-retrieval.md" "references/templates.md" "deep-research" "Trust contract" "vault/briefs/strategic" "\[interpretation\]"; do grep -q "$h" "$f" && echo "OK: $h" || echo "MISSING: $h"; done
```
Expected: six `OK:` lines, no `MISSING:`.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/strategic-brief/SKILL.md
git commit -m "feat(strategic-brief): complete orchestrator body and trust contract"
```

---

### Task 5: Acceptance dry-run (the validation gate)

**Files:**
- Output (not committed): `vault/briefs/strategic/<...>.md` (one per type)

- [ ] **Step 1: Reload skills so the new skill is discoverable**

In a fresh Claude Code turn, confirm `strategic-brief` appears in the available skills list.
Expected: the skill is listed (skills are discovered at session start; start a new session if needed).

- [ ] **Step 2: Generate one vendor-decision brief against a real framing**

Invoke the skill with a real framing, e.g.: "draft a vendor-decision brief on cloud coding-agent platforms; the decision is whether to standardize on one provider this quarter."
Expected: a saved file at `vault/briefs/strategic/<date>-vendor-decision-*.md` following template ②.

- [ ] **Step 3: Verify the trust contract holds on the generated brief**

For the generated file, check by hand and with:
```bash
f=$(ls -t vault/briefs/strategic/*vendor-decision*.md | head -1)
grep -cE "\[corpus\]|\[research:|\[interpretation\]" "$f"   # >0 origin tags present
grep -A20 "Source trail" "$f"                                # split trail present
```
Acceptance criteria (manual): (a) origin tags present and honest; (b) every `[corpus]`
"Open note" link opens a real vault note; (c) every `[research]` claim has a live citation;
(d) no unlabeled fabricated claim; (e) genuinely faster than writing it by hand.

- [ ] **Step 4: Repeat for exec-update and strategy-memo**

Generate one of each against a real framing; apply the same acceptance criteria. Fix any
underperforming template in `references/templates.md` and re-run before declaring that type trusted.

- [ ] **Step 5: Commit any template fixes from the acceptance run**

```bash
git add .claude/skills/strategic-brief/references/templates.md
git commit -m "fix(strategic-brief): tighten templates from acceptance run"
```

(Generated artifacts under `vault/briefs/strategic/` are local output — do not commit unless Lee wants a sample checked in.)

---

## Self-Review

**Spec coverage:** three output types → Task 3 templates + Task 4 draft step ✓; grounding (framing + corpus + research) → Tasks 1/2/4 steps ✓; trust contract → Task 4 ✓; edge handling → Task 4 ✓; validation gate → Task 5 ✓; placement in `.claude/skills/` (not AgentFlow `skills/`) → Task 1 ✓; reads existing `bookmarks_fts`/`deep-research`, writes only new vault folder → Tasks 2/4 ✓.

**Placeholder scan:** no TBD/TODO; every file step shows the actual content; every verification step has an exact command + expected output.

**Type consistency:** frontmatter keys (`artifact_type`, `topic`, `generated_at`, `framing`, `corpus_evidence_count`, `research_source_count`), the three type ids (`exec-update`, `vendor-decision`, `strategy-memo`), origin tags (`[corpus]`, `[research:DATE]`, `[interpretation]`), `broken_source_link`, and the output path `vault/briefs/strategic/` are used identically across Tasks 1–5.
