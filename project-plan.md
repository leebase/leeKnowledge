# leeKnowledge Project Plan

> **Strategic roadmap** — stable, long-term planning document
>
> For tactical execution, see `sprint-plan.md`

---

## Project Overview

**leeKnowledge** is a personal pipeline that extracts X/Twitter bookmarks, enriches them with LLM-generated metadata, and produces a durable Markdown knowledge base.

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

---

## Non-Negotiable Constraints

- Local-first: no cloud services, no hosted infrastructure.
- Personal use only: single user, single account, not for sale.
- Raw data preservation: never lose source material.
- Extraction isolation: if X breaks the scraper, nothing else breaks.

---

## Development Phases

### Phase 0 — Research / Bootstrap

**Status**: COMPLETE

**Goals**:
- Research extraction strategies across multiple AI assistants.
- Converge on a product definition and architecture.

**Deliverables**:
- `research/` — four independent research outputs (ChatGPT, Claude, Gemini, Grok).
- `product-definition.md` — synthesized product spec.
- `architecture.md` — technical architecture.
- `project-plan.md` — this document.

---

### Phase 1 — Project Scaffolding + Database

**Goal**: Runnable Python project with SQLite schema and CLI skeleton.

**Core components**:
1. Python project structure with pyproject.toml.
2. SQLite database with schema (bookmarks, enrichments, url_cache, FTS5 index).
3. Typer CLI with stub commands (extract, enrich, export, sync).

**Tasks**:
- [ ] 1.1 Initialize pyproject.toml (deps: typer, playwright, pydantic, httpx, jinja2, pyyaml, lee-llm-router)
- [ ] 1.2 Create directory structure: `src/leeknowledge/`, `config/`, `data/raw/`, `state/`, `vault/`, `tests/`
- [ ] 1.3 Create `db.py` — SQLite connection, schema creation, dedup insert helper
- [ ] 1.4 Create `cli.py` — Typer app with stub commands
- [ ] 1.5 Create `__main__.py` entry point
- [ ] 1.6 Write tests: DB creation, schema validation, insert + dedup
- [ ] 1.7 Set up .gitignore (data/, state/, config/llm.yaml, .env)

**Success Criteria**:
- `python -m leeknowledge --help` prints all four commands.
- Tests pass for database creation and dedup behavior.

---

### Phase 2 — Extraction

**Goal**: Playwright extracts all bookmarks from X, saves raw JSON, normalizes to SQLite.

**Components**:
1. `extractor.py` — Playwright automation with GraphQL interception.
2. `normalizer.py` — Raw JSON parsing into canonical SQLite records.
3. DOM fallback extractor for when GraphQL fails.

**Tasks**:
- [ ] 2.1 Install Playwright and Chromium
- [ ] 2.2 Create `extractor.py` — Chrome launch with user profile, navigate to bookmarks
- [ ] 2.3 Implement GraphQL response interception (filter `Bookmarks` in URL)
- [ ] 2.4 Implement scroll loop with randomized delays, stop after 5 no-new-content retries
- [ ] 2.5 Implement auth check — detect login redirect, abort with clear message
- [ ] 2.6 Save raw JSON to `data/raw/bookmarks_YYYY-MM-DD.json`
- [ ] 2.7 Create `normalizer.py` — parse GraphQL payload into bookmark records
- [ ] 2.8 Extract fields: tweet_id, text, author, timestamp, conversation_id, media_urls, raw_urls
- [ ] 2.9 SQLite insert with dedup (INSERT OR IGNORE)
- [ ] 2.10 Wire `extract` CLI command end-to-end
- [ ] 2.11 Implement DOM fallback extractor
- [ ] 2.12 Test with real account: verify count, spot-check 10 bookmarks
- [ ] 2.13 Test rerun: verify no duplicates on second extraction

**Success Criteria**:
- `python -m leeknowledge extract` captures all bookmarks to SQLite.
- Raw JSON preserved in `data/raw/`.
- Second run produces zero new inserts.

---

### Phase 3 — URL Expansion + Enrichment

**Goal**: Expand short URLs, enrich bookmarks with LLM summaries and tags.

**Components**:
1. URL expansion with caching.
2. LLM enrichment via lee-llm-router (pi harness, openai-codex).

**Tasks**:
- [ ] 3.1 URL expansion: httpx HEAD follow-redirects, cache in url_cache table
- [ ] 3.2 Page title/description fetch (best-effort, 5s timeout)
- [ ] 3.3 Create `config/llm.yaml` for lee-llm-router
- [ ] 3.4 Create `enricher.py` — query un-enriched bookmarks, build prompts, call router
- [ ] 3.5 Design enrichment prompt → structured JSON (summary, tags, entities, topic)
- [ ] 3.6 Handle malformed LLM responses gracefully (log + skip)
- [ ] 3.7 Store enrichments in SQLite (tweet_id, summary, tags, entities, topic, model, enriched_at)
- [ ] 3.8 Wire `enrich` CLI command
- [ ] 3.9 Test: only un-enriched bookmarks are processed on rerun
- [ ] 3.10 Test: malformed LLM output doesn't crash pipeline

**Success Criteria**:
- `python -m leeknowledge enrich` enriches all bookmarks.
- Reruns skip already-enriched items.
- Failures are logged, not fatal.

---

### Phase 4 — Export + Polish

**Goal**: Generate Markdown vault, wire sync command, validate end-to-end.

**Components**:
1. Jinja2 Markdown template with YAML frontmatter.
2. Exporter that reads SQLite and writes vault files.
3. Sync command orchestrating the full pipeline.

**Tasks**:
- [ ] 4.1 Create Jinja2 template `templates/bookmark.md.j2`
- [ ] 4.2 Create `exporter.py` — read SQLite, render Markdown, write to vault/YYYY/MM/
- [ ] 4.3 Slug generation: first ~40 chars of text + tweet_id
- [ ] 4.4 Wire `export` CLI command
- [ ] 4.5 Wire `sync` CLI command (extract → enrich → export)
- [ ] 4.6 Build FTS5 index population into export step
- [ ] 4.7 Test: vault opens in Obsidian, tags browsable, notes render correctly
- [ ] 4.8 Test: full end-to-end `sync` on real account
- [ ] 4.9 Test: re-export after template change updates notes without re-enriching
- [ ] 4.10 Spot-check 20 bookmarks for fidelity

**Success Criteria**:
- `python -m leeknowledge sync` runs the full pipeline.
- Vault opens in Obsidian with browsable, tagged, summarized notes.
- MVP complete.

---

### Phase 5 — Future (Optional)

**Potential**:
- Bookmark folder support (if X Premium exposes folders).
- Thread reconstruction (multi-post threads as single notes).
- Topic index pages (auto-generated MOC notes per topic).
- Semantic search via local embeddings.
- Browser extension for capture-at-bookmark-time.
- Weekly synthesis notes.

*Not required for initial success.*

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

**Phase**: 0 (Research) — COMPLETE
**Next Phase**: 1 (Scaffolding + Database)
**Mode**: 2 (Collaborative)
**Next Milestone**: Runnable CLI with SQLite schema

---

## Guiding Philosophy

> Turn bookmarked knowledge into durable personal artifacts. Simple tools, local data, no lock-in.

Keep implementations minimal. Validate before scaling.

---

*End of Project Plan*
