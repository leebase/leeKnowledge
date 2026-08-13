# leeKnowledge Project Plan

> **Strategic roadmap** — stable, long-term planning document
>
> For tactical execution, see `sprint-plan.md`

---

## Project Overview

**leeKnowledge** is a personal, local-first bookmark-to-knowledge pipeline that now has an MVP-complete core: extract X/Twitter bookmarks, preserve raw captures, normalize into SQLite, enrich with LLM metadata, and export a durable Markdown vault. The next roadmap layer is leadership signal processing built on top of that existing corpus.

The philosophy is **Incremental Delivery**:

> Build the smallest useful primitives first. Validate before scaling.

---

## Objectives

### Primary Objective
Convert ~100-200 personal X bookmarks into a searchable, tagged, summarized Markdown knowledge base that works in Obsidian or any text editor.

### Secondary Objectives
- Preserve raw extraction data so processing can be replayed without re-scraping.
- Support periodic rerun: new bookmarks are added, existing ones are untouched.
- Use existing ChatGPT subscription (via pi harness / lee-llm-router) for LLM enrichment at zero marginal cost.
- Turn the resulting corpus into leadership-oriented derived artifacts such as topic notes and synthesis briefs.

---

## Non-Negotiable Constraints

- Local-first: no cloud services, no hosted infrastructure.
- Personal use only: single user, single account, not for sale.
- Raw data preservation: never lose source material.
- Extraction isolation: if X breaks the scraper, nothing else breaks.

---

## Development Phases

### Phase 0 — Research / Bootstrap

**Status**: ✅ Complete

**Goals**:
- Research extraction strategies across multiple AI assistants.
- Converge on a product definition and architecture.

**Delivered**:
- `research/` — four independent research outputs (ChatGPT, Claude, Gemini, Grok).
- `product-definition.md` — synthesized product spec.
- `architecture.md` — technical architecture.
- `project-plan.md` — this document.

---

### Phase 1 — Foundation / Scaffolding

**Status**: ✅ Complete

**Goal**: Establish the runnable project scaffold, SQLite schema, CLI, tests, and local artifact conventions.

**Delivered**:
- Python package structure under `src/leeknowledge/`
- SQLite bootstrap and schema helpers
- CLI entrypoints for `extract`, `enrich`, `export`, `sync`, and `db`
- Baseline tests for DB initialization and dedup behavior
- Local-only artifact directory conventions and ignore rules

**Exit Criteria Met**:
- `PYTHONPATH=src python3 -m leeknowledge --help`
- Baseline database and dedup tests passed during delivery

---

### Phase 2 — Extraction Slice

**Status**: ✅ Complete

**Goal**: Capture X bookmarks into immutable raw archives and normalize canonical bookmark rows into SQLite.

**Delivered**:
- Chrome-profile Playwright extraction flow
- Authentication checks for `x.com/i/bookmarks`
- GraphQL bookmark capture and immutable raw archive persistence
- Deterministic normalization and SQLite inserts with tweet-id dedup
- End-to-end `extract` CLI wiring and extraction-focused tests

**Exit Criteria Met**:
- `extract` captures bookmark payloads, writes raw archives first, and normalizes into SQLite
- Reruns do not duplicate bookmark rows

---

### Phase 3 — Enrichment Slice

**Status**: ✅ Complete

**Goal**: Expand URLs, fetch best-effort metadata, and persist one validated enrichment row per bookmark.

**Delivered**:
- URL cache resolution and optional metadata fetch
- `config/llm.yaml`-driven enrichment routing through lee-llm-router
- Structured JSON validation with null-placeholder fallback behavior
- Versioned enrichment storage (`model`, `prompt_version`, `schema_version`, `validation_status`)
- End-to-end `enrich` CLI wiring and rerun-safe enrichment tests

**Exit Criteria Met**:
- `enrich` processes only bookmarks without enrichment rows
- Validation failures are stored explicitly without corrupting source data

---

### Phase 4 — Export MVP + Hardening

**Status**: ✅ Complete

**Goal**: Render a durable Markdown vault, wire `sync` end-to-end, and harden export behavior for sign-off-ready MVP use.

**Delivered**:
- Markdown note template and exporter over SQLite state
- Stable vault path contract under `vault/YYYY/MM/<slug>-<tweet_id>.md`
- `sync` orchestration across extract → enrich → export
- Export regression tests
- Sprint 5 hardening for read-only DB validation and Markdown-fidelity safety

**Exit Criteria Met**:
- `export` renders notes from SQLite without bootstrapping a missing DB
- `sync` runs the full pipeline in order and stops on failure
- MVP is complete and documented as the project baseline

---

### Phase 5 — Leadership Signal Processing

**Status**: ✅ Complete

**Goal**: Add leadership-oriented derived artifacts on top of the MVP corpus without changing extraction or source-truth contracts.

**Delivered roadmap slices**:
- **Sprint 6 — Topic Index Notes**: shipped deterministic topic views over the corpus
- **Sprint 7 — Leadership Synthesis**: shipped recurring weekly leadership briefs generated from the local corpus
- **Sprint 8 — Leadership Metadata**: shipped a small decision-oriented metadata layer for prioritization and triage
- **Sprint 9 — Curated Collections**: shipped initiative-centered collection notes for active strategic work

**Closeout state**:
- Sprint 9 closed the planned Level 2 roadmap and remains the verified leadership-feature baseline.
- Sprint 10 universal source ingestion is now shipped and extends the product baseline to bounded multi-source intake.
- Sprint 7-9 review findings remain explicit follow-up hardening work for the next sprint to sequence.

---

### Phase 6 — Universal Source Intake

**Status**: ✅ Complete

**Goal**: Expand leeKnowledge from an X-first pipeline into a source-agnostic intake system with bounded URL, Safari bookmark export, and deep-research artifact imports while keeping downstream enrichment, export, and leadership views unchanged.

**Delivered roadmap slice**:
- **Sprint 10 — Universal Source Ingestion**: shipped `import-url`, `import-safari-folder`, and `import-research` on top of a shared canonical source-identity contract

**Post-closeout focus**:
- Sequence the next sprint against the shipped mixed-source intake baseline.
- Triage the Sprint 7-9 review findings into explicit hardening or backlog work.
- Decide whether the next expansion is hardening, publishing/sharing, or another derived artifact layer.

---

## Architecture Principles

1. **Simple that works** — no abstractions beyond what's needed now.
2. **Raw before smart** — persist source data before transforming.
3. **Extraction isolation** — scraper is replaceable, pipeline is stable.
4. **Replayable stages** — re-enrich or re-export without re-scraping.
5. **LLM is additive** — system works without enrichment.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| CLI | Typer |
| Browser automation | Playwright (Python) |
| Database | SQLite + FTS5 |
| Data models | Pydantic |
| LLM integration | lee-llm-router (pi harness, openai-codex) |
| Markdown rendering | Jinja2 |
| URL expansion | httpx |
| Config | PyYAML |

---

## Risks

| Risk | Mitigation |
|------|------------|
| X changes GraphQL schema | DOM fallback extractor (Phase 2, task 2.11) |
| X detects automation | Human-like delays, weekly frequency, personal scale |
| LLM enrichment quality | Enrichment is optional; doesn't affect raw data |
| Scope creep | Phase gating — each phase has "done when" criteria |
| Playwright version breaks | Pin version, update as needed |

---

## Success Metrics

- All ~100-200 bookmarks extracted and preserved as raw JSON.
- Each bookmark has a Markdown note with summary and tags.
- Vault is browsable in Obsidian by topic, author, and date.
- Rerun after adding new bookmarks processes only the new ones.
- Total pipeline runtime under 10 minutes for full sync.

---

## Current Status

**Phase**: 6 (Universal Source Intake) — COMPLETE
**Leadership Baseline**: Verified complete through Sprint 9
**Mode**: 2 (Collaborative)
**Active Sprint**: None currently locked
**Next Milestone**: Choose and scope the first post-Sprint-10 implementation layer against the shipped mixed-source baseline

---

## Guiding Philosophy

> Turn bookmarked knowledge into durable personal artifacts. Simple tools, local data, no lock-in.

Keep implementations minimal. Validate before scaling.

---

*End of Project Plan*
