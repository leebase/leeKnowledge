# Using the Strategic Brief

> How to turn your leeKnowledge corpus into leadership deliverables — exec updates,
> vendor/build-vs-buy decision briefs, and strategy memos — grounded in your saved signal
> plus fresh, fact-checked research.
>
> This is the "research assistant" layer for your Director of Data and AI role. For the
> capture/enrich pipeline underneath it, see [using-leeKnowledge.md](using-leeKnowledge.md).

---

## What it is

`strategic-brief` is a Claude Code skill (lives at `.claude/skills/strategic-brief/`). You
ask for a deliverable in plain language; it:

1. **Frames** the request (confirms the type, fills only the gaps).
2. **Retrieves** evidence from your corpus (`state/app.db`, full-text search over your enriched bookmarks).
3. **Researches** the web for current, fact-checked facts (the `deep-research` skill).
4. **Drafts** the deliverable into a leadership-appropriate template.
5. **Saves** it to `vault/briefs/strategic/` for you to edit and use.

It produces **drafts you edit** — never anything auto-sent.

### The three deliverable types

| Type | Use it for | Example ask |
|------|-----------|-------------|
| **exec-update** | A recurring "what's moving and what it means for us" update to leadership | *"exec update on what's moving in agentic coding"* |
| **vendor-decision** | A build-vs-buy / tool / model / platform call with a recommendation | *"vendor brief: should we standardize on one coding-agent platform this quarter?"* |
| **strategy-memo** | A position piece feeding operating-model / platform / governance / roadmap decisions | *"strategy memo on our AI operating model"* |

---

## Before you start (one-time + ongoing)

**One-time:** the corpus must be enriched. This was done on 2026-05-30 (all 176 bookmarks).
If you start fresh on a new machine, run the pipeline first (see
[using-leeKnowledge.md](using-leeKnowledge.md)): `extract`/`import-*` → `enrich` → `export`.

**Each session:** the skill is discovered at Claude Code **startup**. If you just created or
edited it, start a new session so it's invokable.

**Research:** the `deep-research` skill must be available (it is, in this environment). A
research run fans out web searches and takes a few minutes — that's normal.

---

## How to use it

Just describe the deliverable in a Claude Code session. Lead with the type word if you can
("exec update", "vendor brief/decision", "strategy memo") and name the topic. Add the
specifics that matter:

- **The question or decision** — e.g. "whether to standardize on one provider this quarter."
- **The audience** — e.g. "for my staff meeting" / "for the exec team."
- **Any internal context** — your org, constraints, the live initiative it feeds.

You don't have to supply all of it; the skill asks only for what's missing, then proceeds.

### Examples

```
draft a vendor-decision brief on cloud coding-agent platforms — the decision is
whether to standardize on one provider this quarter vs stay multi-provider

exec update on agentic-coding trends for my leadership team — one page

strategy memo on our data platform direction, focused on governance implications
```

### Not every question needs the full flow

If you just want **"what have I seen about X?"** — that's a lookup, not a deliverable. Ask
it directly; the assistant will answer from your corpus without spinning up a research run.

---

## Reading the output

Output lands at `vault/briefs/strategic/YYYY-MM-DD-<type>-<slug>.md` and opens cleanly in
Obsidian. The thing that makes it trustworthy is the **provenance tagging** — every
substantive claim is labelled:

- **`[corpus]`** — from your saved signal. Links the bookmark note (and the original source
  when its link still resolves).
- **`[research:YYYY-MM-DD]`** — from fresh web research, with a real citation.
- **`[interpretation]`** — the assistant's synthesis/judgment. Always labelled, never
  disguised as fact.

Every brief ends with a **Source trail** split into those three buckets, so you can see
exactly where each statement came from before you put your name on it. Numbers and vendor
claims only appear if they're cited (`[research]`) or linked (`[corpus]`) — never invented.

A worked example is already in your vault:
[2026-05-30-vendor-decision-agentic-coding-platform.md](vault/briefs/strategic/2026-05-30-vendor-decision-agentic-coding-platform.md).

---

## Keeping it fresh

The brief is only as current as your corpus + the research run. The research half is always
live. To refresh the corpus half before an important brief:

```bash
# pull in new signal, then re-enrich
PYTHONPATH=src .venv/bin/python -m leeknowledge sync          # X bookmarks: extract → enrich → export
# or for other sources:
PYTHONPATH=src .venv/bin/python -m leeknowledge import-url "https://..."
PYTHONPATH=src .venv/bin/python -m leeknowledge enrich
PYTHONPATH=src .venv/bin/python -m leeknowledge export
```

Then ask for the brief. (Topics/metadata/synthesis layers are optional for briefs — the
skill reads bookmarks + enrichment directly.)

---

## Tips for good briefs

- **Name the decision, not just the topic.** "Should we standardize on one provider this
  quarter?" produces a sharper brief than "coding agents."
- **Say the audience and length.** "One page for the exec team" changes what gets cut.
- **Iterate.** It's a draft — ask for a tighter TL;DR, a different recommendation framing, or
  "make the options table include TCO."
- **Trust the tags.** If something matters for a real decision, check it's `[corpus]` or
  `[research]`, not `[interpretation]`.

---

## Honest limitations

- **Your corpus is narrow and practitioner-flavored** (heavy on hands-on AI-coding content).
  On strategy/governance topics it may be thin — the brief will say so and lean research-led.
- **Research is point-in-time.** Capability/pricing facts are snapshots; the brief date-stamps
  them and flags fast-moving areas.
- **~38 older X bookmarks have broken source links** (a known extraction issue). The brief
  links the vault note as primary and marks the external link "unavailable" rather than emit
  a dead URL.
- **Each research run costs real time and tokens.** Use it for deliverables you'll actually
  use, not idle curiosity (use a plain lookup for that).

---

## Roadmap

Today the brief is conversational (skill-first, to prove the templates). Once the three
types are trusted in real use, the corpus-retrieval step can be hardened into a
`leeknowledge brief` CLI command for repeatable, scriptable runs. See the spec at
`docs/superpowers/specs/2026-05-30-strategic-brief-design.md`.
