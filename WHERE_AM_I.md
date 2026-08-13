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
| **Current Phase** | Phase 6 — Universal Source Intake |
| **Overall Status** | 🟢 Source-agnostic intake baseline is shipped through Sprint 10; the next decision is which post-intake layer to build next |
| **Last Updated** | 2026-04-08 |

---

## Progress Against Product Goals

> Reference: `product-definition.md` for full success criteria.

### MVP Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Extract bookmarks into raw JSON + SQLite | ✅ Done | Sprint 2 extraction slice is closed out |
| Enrich bookmarks with summaries and tags | ✅ Done | Sprint 3 enrichment slice is closed out; rows store explicit model/prompt/schema versions |
| Export Markdown vault for Obsidian | ✅ Done | Sprint 4 implemented export/sync and Sprint 5 hardened read-only DB behavior plus Markdown fidelity |
| Product and technical direction defined | ✅ Done | Product, architecture, and sprint plan are established |

**MVP status:** the full pipeline exists end-to-end, the first hardening pass is complete, and the intake edge now extends beyond X. The remaining work is human-facing sign-off plus choosing the next backlog slice on top of the shipped mixed-source baseline.

### Level 2 Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Define the leadership-signal-processing expansion clearly | ✅ Done | Product definition and architecture now describe the Level 2 direction |
| Pick a first thin derived-artifact slice | ✅ Done | Sprint 6 targets topic index notes |
| Generate useful topic views from the existing corpus | ✅ Done | Sprint 6 shipped deterministic topic notes via the dedicated `topics` command |
| Generate recurring leadership synthesis briefs from the corpus | ✅ Done | Sprint 7 shipped the weekly synthesis layer and latest-brief alias |
| Add bounded leadership metadata for triage and prioritization | ✅ Done | Sprint 8 shipped the dedicated metadata layer and weekly-brief metadata rendering |
| Prepare curated collection notes for live strategic work | ✅ Done | Sprint 9 shipped initiative-centered collection notes plus the checked-in definitions layer |

**Level 2 status:** topic notes, weekly leadership briefs, bounded leadership metadata, and curated collections are now all shipped. Sprint 10 adds the completed multi-source intake baseline on top of that leadership layer, so the next project choice is whether to harden review follow-ups, expand derived usefulness, or explore sharing/publishing paths.

### Current Phase Goals

| Goal | Status | Notes |
|------|--------|-------|
| Define product vision and architecture | ✅ Done | Core docs added |
| Establish runnable Phase 1 scaffold | ✅ Done | Package, CLI, DB, tests, and local artifact dirs aligned |
| Capture and normalize first real bookmark payload | ✅ Done | Sprint 2 extraction slice is closed out |
| Expand URLs and enrich captured bookmarks | ✅ Done | Sprint 3 enrichment slice is closed out and the rerun-safe enrichment contract is documented |
| Render Markdown notes and wire `sync` end-to-end | ✅ Done | Sprint 4 implemented the exporter, note template, sync orchestration, and export tests |
| Generate leadership-oriented topic views from the corpus | ✅ Done | Sprint 6 implemented deterministic topic-note generation from existing local state |
| Generate recurring leadership briefs over the derived corpus | ✅ Done | Sprint 7 implemented weekly synthesis with archived notes plus a latest-brief alias |
| Add a small leadership-metadata layer for triage and prioritization | ✅ Done | Sprint 8 implemented the metadata command plus metadata-aware weekly synthesis |
| Prepare curated collection notes over the shipped leadership layers | ✅ Done | Sprint 9 implemented initiative-centered collection notes over the shipped leadership layers |
| Expand intake from X-only extraction to bounded multi-source ingestion | ✅ Done | Sprint 10 shipped the shared source-identity contract plus `import-url`, `import-safari-folder`, and `import-research` |

---

## Sprint Position

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 1 — Foundation | Scaffolding, DB, and CLI baseline | ✅ Complete |
| Sprint 2 — Extraction Slice | Raw archive + SQLite normalization | ✅ Complete |
| Sprint 3 — Enrichment Slice | URL expansion + LLM enrichment | ✅ Complete |
| Sprint 4 — Export Slice | Markdown vault + `sync` | ✅ Complete |
| Sprint 5 — Export Hardening | Review findings, fidelity, and sign-off | ✅ Complete |
| Sprint 6 — Topic Index Notes | First derived leadership view over the corpus | ✅ Complete |
| Sprint 7 — Leadership Synthesis | Recurring leadership brief over the derived corpus | ✅ Complete |
| Sprint 8 — Leadership Metadata | Small decision-oriented metadata layer for triage and prioritization | ✅ Complete |
| Sprint 9 — Curated Collections | Initiative-centered collection notes for live strategic work | ✅ Complete |
| Sprint 10 — Universal Source Ingestion | Bounded multi-source intake on top of a shared canonical identity contract | ✅ Complete |

---

## Product Risks & Blockers

| Risk/Blocker | Impact | Status |
|-------------|--------|--------|
| X DOM / GraphQL changes can break extraction | Extraction is brittle by nature | 🟡 Accepted risk |
| Chrome auth state is required locally | Extraction cannot run without active login | 🟡 Needs local setup |
| LLM config is local-only and not yet created | Enrichment cannot run until configured | 🟡 Expected for later phase |
| Local runtime is still Python 3.9.6 in this shell | Declared deps target Python 3.12+ | 🟡 Needs environment alignment |
| Human Obsidian review of metadata-aided weekly-brief and curated-collection usefulness is still deferred | Final UX confidence for the shipped leadership-prep artifacts still depends on one manual spot-check | 🟡 Follow-up |
| Sprint 9 review findings R001-R004 remain open | The new collection layer still has explicit rerun-safety, usefulness, note-fidelity, and validation follow-ups | 🟡 Follow-up |

---

## Key Decisions Made

Decisions that affect product direction (for technical decisions, see `architecture.md`):

| Decision | Rationale | Date |
|----------|-----------|------|
| Python Package profile selected | Best fit for project goals | 2026-04-07 |
| Product is a personal bookmark-to-knowledge pipeline | Scope stays local-first, single-user, and durable | 2026-04-07 |
| Pipeline stages are Extract → Normalize → Enrich → Export | Keeps unstable scraping isolated from stable downstream stages | 2026-04-07 |
| Sprint work is organized as thin vertical slices | Each sprint should end with runnable value and explicit verification | 2026-04-07 |
| Level 2 begins with derived topic notes rather than broad synthesis automation | Proves leadership usefulness before expanding scope | 2026-04-07 |
| Weekly synthesis ships before bookmark-level metadata enrichment | Validates the recurring leadership-brief surface before adding new triage fields | 2026-04-08 |
| Leadership metadata ships before curated collections | Gives collection notes a bounded triage layer to compose instead of inventing ad hoc ranking rules inside collections | 2026-04-08 |
| Curated collections complete the planned Level 2 roadmap and shift the next decision to post-roadmap direction | Closes the original leadership-layer sequence before choosing multi-source or sharing work | 2026-04-08 |
| Sprint 10 makes bounded multi-source intake part of the shipped product baseline rather than a speculative extension | Lets the next sprint assume shared source identity and explicit import commands already exist | 2026-04-08 |

---

## What "Done" Looks Like

- [x] MVP criteria implemented and hardened through Sprint 5
- [x] Lee can run `python -m leeknowledge sync` and produce a browsable Markdown vault
- [x] Documentation and runbooks are complete enough for future sessions to continue cleanly
- [x] First Level 2 topic-note artifact is implemented
- [x] First recurring weekly leadership brief artifact is implemented
- [x] Bounded leadership metadata layer is implemented
- [x] First curated collection layer is implemented with initiative-centered generated notes
- [ ] Human usefulness check confirms the weekly-brief and curated-collection layers are genuinely valuable in live use

---

*Update this file when project milestones are reached or product direction changes. This is your compass — `context.md` is your GPS.*
