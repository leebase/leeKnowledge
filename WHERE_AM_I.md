# WHERE_AM_I — leeKnowledge

> **Product-level orientation.** Where does this project stand against its goals?
>
> This file tracks progress toward the product vision. For session-level context (what was I working on?), see `context.md`.

---

## Project Health

| Attribute | Value |
|-----------|-------|
| **Project** | leeKnowledge |
| **Profile** | Python Package |
| **Current Phase** | Phase 2 — Extraction |
| **Overall Status** | 🟡 Active build sprint |
| **Last Updated** | 2026-04-07 |

---

## Progress Against Product Goals

> Reference: `product-definition.md` for full success criteria.

### MVP Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Extract bookmarks into raw JSON + SQLite | ⬜ Not started | Active Sprint 2 goal |
| Enrich bookmarks with summaries and tags | ⬜ Not started | Planned Sprint 3 |
| Export Markdown vault for Obsidian | ⬜ Not started | Planned Sprint 4 |
| Product and technical direction defined | ✅ Done | Product, architecture, and sprint plan are established |

### Current Phase Goals

| Goal | Status | Notes |
|------|--------|-------|
| Define product vision and architecture | ✅ Done | Core docs added |
| Establish runnable Phase 1 scaffold | ✅ Done | Package, CLI, DB, tests, and local artifact dirs aligned |
| Capture and normalize first real bookmark payload | ⬜ Not started | Active Sprint 2 goal |

---

## Sprint Position

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 1 — Foundation | Scaffolding, DB, and CLI baseline | ✅ Complete |
| Sprint 2 — Extraction Slice | Raw archive + SQLite normalization | 🟡 Active |
| Sprint 3 — Enrichment Slice | URL expansion + LLM enrichment | ⬜ Planned |
| Sprint 4 — Export Slice | Markdown vault + `sync` | ⬜ Planned |

---

## Product Risks & Blockers

| Risk/Blocker | Impact | Status |
|-------------|--------|--------|
| X DOM / GraphQL changes can break extraction | Extraction is brittle by nature | 🟡 Accepted risk |
| Chrome auth state is required locally | Extraction cannot run without active login | 🟡 Needs local setup |
| LLM config is local-only and not yet created | Enrichment cannot run until configured | 🟡 Expected for later phase |
| Local runtime is still Python 3.9.6 in this shell | Declared deps target Python 3.12+ | 🟡 Needs environment alignment |

---

## Key Decisions Made

Decisions that affect product direction (for technical decisions, see `architecture.md`):

| Decision | Rationale | Date |
|----------|-----------|------|
| Python Package profile selected | Best fit for project goals | 2026-04-07 |
| Product is a personal bookmark-to-knowledge pipeline | Scope stays local-first, single-user, and durable | 2026-04-07 |
| Pipeline stages are Extract → Normalize → Enrich → Export | Keeps unstable scraping isolated from stable downstream stages | 2026-04-07 |
| Sprint work is organized as thin vertical slices | Each sprint should end with runnable value and explicit verification | 2026-04-07 |

---

## What "Done" Looks Like

- [ ] MVP criteria met
- [ ] Lee can run `python -m leeknowledge sync` and produce a browsable Markdown vault
- [ ] Documentation and runbooks are complete enough for future sessions to continue cleanly

---

*Update this file when project milestones are reached or product direction changes. This is your compass — `context.md` is your GPS.*
