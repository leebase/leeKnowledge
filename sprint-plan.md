# leeKnowledge Sprint Plan

> **Tactical execution plan** for active delivery.
>
> This file is the project's short-horizon execution contract. It should answer:
> what sprint is active, what "done" means, what must be shipped next, how work
> is sequenced, how it will be verified, and what must be updated for handoff.

---

## AgentFlow Operating Rules

1. Work in thin vertical slices that end in a runnable, verifiable capability.
2. Keep sprint scope tactical. Product and architecture decisions belong in
   `product-definition.md`, `project-plan.md`, and `architecture.md`.
3. Every sprint must name explicit exit criteria and verification commands.
4. If scope changes, update this file before or alongside the code.
5. At sprint closeout, update `context.md`, `WHERE_AM_I.md`, and
   `result-review.md` so another agent can continue without re-discovery.

---

## Canon

| Document | Role In This Plan |
|----------|-------------------|
| `product-definition.md` | Defines the real user problem and MVP |
| `architecture.md` | Defines the pipeline shape and technical boundaries |
| `project-plan.md` | Defines the phase roadmap |
| `context.md` | Defines current session state and next actions |

---

## Delivery Map

| Sprint | Phase | Goal | Status |
|--------|-------|------|--------|
| Sprint 1 — Foundation | Phase 1 | Establish runnable scaffold, DB, CLI skeleton, tests | ✅ Complete |
| Sprint 2 — Extraction Slice | Phase 2 | Capture raw bookmark payloads and normalize to SQLite | 🟡 Active |
| Sprint 3 — Enrichment Slice | Phase 3 | Expand URLs and enrich unprocessed bookmarks | ⬜ Planned |
| Sprint 4 — Export Slice | Phase 4 | Render Markdown vault and wire `sync` end-to-end | ⬜ Planned |

---

## Sprint 1 — Foundation

**Status:** COMPLETE  
**Why it mattered:** The project needed a stable local scaffold before touching
the brittle X extraction problem.

### Delivered

- Lowercase Python package `leeknowledge`
- Runnable module entrypoint and CLI skeleton
- SQLite bootstrap with bookmark, enrichment, URL cache, and FTS tables
- Baseline DB tests
- Local-only artifact directories and `.gitignore`
- Core planning docs aligned to the defined product

### Exit Criteria Met

- `PYTHONPATH=src python3 -m leeknowledge --help`
- `PYTHONPATH=src pytest`

---

## Sprint 2 — Extraction Slice

**Status:** ACTIVE  
**Sprint Goal:** Ship the first real pipeline slice that:
1. opens X bookmarks in a logged-in browser session,
2. captures raw payloads to `data/raw/`,
3. normalizes bookmark records into SQLite,
4. can be rerun safely without duplicate inserts.

### Why This Sprint Exists

Extraction is the hardest and riskiest part of the product. Once raw payloads
are captured and normalized reliably, the downstream pipeline becomes mostly
deterministic engineering work.

### Sprint Boundaries

**In scope**
- Browser launch using an existing Chrome profile
- Navigate to `x.com/i/bookmarks`
- GraphQL `Bookmarks` interception
- Scroll/loading loop with stop condition
- Immutable raw JSON archive per run
- Raw payload parsing into canonical bookmark records
- SQLite insert with dedup by tweet ID
- `extract` CLI wired end-to-end
- Real-world manual validation against Lee's account

**Out of scope**
- URL expansion and metadata fetch
- LLM enrichment
- Markdown export
- Vault polish and topic curation
- Thread reconstruction

### Sprint Deliverables

| Deliverable | Description | Done When |
|-------------|-------------|-----------|
| Working extractor | Browser automation reaches bookmarks and collects payloads | At least one successful raw archive exists in `data/raw/` |
| Working normalizer | Captured payloads become canonical rows in SQLite | `bookmarks` table contains inserted bookmark rows |
| Safe rerun behavior | Re-running extraction does not duplicate rows | Second run inserts zero duplicates for previously seen tweet IDs |
| Clear failure path | Auth/schema failures stop with readable errors | Failures do not silently corrupt DB or raw archives |

### Task Board

| ID | Task | Priority | Status | Depends On | Verification |
|----|------|----------|--------|------------|--------------|
| 2.1 | Stand up Python 3.12+ dev environment and install declared deps | P0 | ⬜ Todo | None | `pip install -e ".[dev]"` succeeds |
| 2.2 | Decide local config defaults for Chrome profile, DB path, and raw output path | P0 | ⬜ Todo | 2.1 | Config values are documented or encoded clearly |
| 2.3 | Implement Chrome launch with existing user profile in `extractor.py` | P0 | ⬜ Todo | 2.1, 2.2 | Browser opens authenticated session |
| 2.4 | Add navigation/auth check for `x.com/i/bookmarks` | P0 | ⬜ Todo | 2.3 | Clear error if redirected to login |
| 2.5 | Intercept GraphQL bookmark responses and store raw payloads in memory | P0 | ⬜ Todo | 2.4 | At least one `Bookmarks` payload captured |
| 2.6 | Implement scroll loop with no-new-content stop condition | P1 | ⬜ Todo | 2.5 | Payload count stabilizes and run exits cleanly |
| 2.7 | Persist immutable archive to `data/raw/bookmarks_YYYY-MM-DD.json` | P0 | ⬜ Todo | 2.5 | Raw file created before normalization |
| 2.8 | Implement payload parsing in `normalizer.py` | P0 | ⬜ Todo | 2.5 | Canonical bookmark records produced from sample payload |
| 2.9 | Insert normalized bookmarks into SQLite with dedup semantics | P0 | ⬜ Todo | 2.8 | Duplicate tweet IDs are ignored on rerun |
| 2.10 | Wire `extract` CLI command through extractor and normalizer | P0 | ⬜ Todo | 2.7, 2.9 | `python -m leeknowledge extract` runs the slice |
| 2.11 | Add DOM fallback when GraphQL interception yields nothing | P1 | ⬜ Todo | 2.10 | Empty interception path still returns bookmark candidates |
| 2.12 | Add automated tests for payload normalization and dedup edge cases | P1 | ⬜ Todo | 2.8, 2.9 | `pytest` covers parser and duplicate handling |
| 2.13 | Run manual end-to-end spot check against real account | P0 | ⬜ Todo | 2.10 | Raw archive and DB rows match expected bookmark sample |
| 2.14 | Run second extraction to confirm idempotent inserts | P0 | ⬜ Todo | 2.13 | Second run produces no duplicate rows |

### Suggested Execution Order

1. Environment and config decisions: 2.1-2.2
2. Browser access and auth checks: 2.3-2.4
3. Capture raw payloads first: 2.5-2.7
4. Normalize and store safely: 2.8-2.10
5. Add fallback and coverage: 2.11-2.12
6. Prove it on the real workflow: 2.13-2.14

### Verification Gate

The sprint is not done until all of these are true:

- `PYTHONPATH=src python3 -m leeknowledge extract` completes against a real,
  logged-in X session
- A new immutable archive appears under `data/raw/`
- SQLite contains bookmark rows with stable tweet IDs
- A rerun does not duplicate existing rows
- Automated tests pass
- Failure modes are readable and non-destructive

### Manual Test Script

Run these in order during validation:

```bash
python3 --version
pip install -e ".[dev]"
python -m playwright install chromium
PYTHONPATH=src python3 -m leeknowledge extract
sqlite3 state/app.db "select count(*) from bookmarks;"
PYTHONPATH=src pytest
PYTHONPATH=src python3 -m leeknowledge extract
sqlite3 state/app.db "select count(*) from bookmarks;"
```

### Risks To Manage During This Sprint

| Risk | Impact | Mitigation |
|------|--------|------------|
| X changes GraphQL shape or blocks interception | Capture may fail completely | Keep extractor isolated and ship DOM fallback |
| Chrome profile selection is wrong | Extraction cannot authenticate | Make profile path explicit and validate early |
| Raw payload shape is messier than expected | Normalizer work expands | Preserve raw files first and build parser from fixtures |
| Local Python version is below target | Runtime/dependency drift | Move to Python 3.12 environment before deeper work |
| Playwright launches but login session is stale | Manual run fails late | Add early auth detection and clear guidance |

### Decisions Needed During The Sprint

| Decision | Why It Matters | Preferred Timing |
|----------|----------------|------------------|
| Chrome profile path strategy | Determines whether extraction is reliable on Lee's machine | Before 2.3 |
| Raw archive naming granularity | Affects replayability and auditability | Before 2.7 |
| Canonical bookmark field minimums | Defines what "successful normalization" means | Before 2.8 |
| Whether DOM fallback ships in same sprint | Affects scope and resilience | Reassess after 2.10 |

### Closeout Checklist

- [ ] Mark completed tasks above
- [ ] Update `context.md` with new current work and next actions
- [ ] Update `WHERE_AM_I.md` for milestone progress
- [ ] Add a result entry to `result-review.md` if the slice is working
- [ ] Record any extractor-specific technical decisions in `architecture.md`

---

## Sprint 3 — Enrichment Slice

**Status:** PLANNED  
**Goal:** Enrich unprocessed bookmarks with summary, tags, entities, and topic
via `lee-llm-router`, with safe storage in SQLite.

### Planned Deliverables

- URL expansion with caching
- Optional page title/description fetch
- Structured enrichment prompt and response validation
- `enrich` CLI command for un-enriched bookmarks only
- Rerun safety and malformed-response handling

### Entry Criteria

- Sprint 2 complete
- At least one usable dataset exists in SQLite
- Local LLM config is available

---

## Sprint 4 — Export Slice

**Status:** PLANNED  
**Goal:** Turn SQLite bookmarks plus enrichment data into a browsable Markdown
vault and wire `sync` end-to-end.

### Planned Deliverables

- Jinja2 note rendering
- File naming and directory strategy
- `export` CLI command
- `sync` orchestration across all stages
- Manual Obsidian validation and fidelity spot checks

### Entry Criteria

- Sprint 3 complete
- SQLite has both bookmarks and enrichment data

---

## Ready Queue

These are not active sprint commitments yet, but they are the next likely
delivery slices once the current sprint exits cleanly.

1. Support re-enrichment by model/prompt version instead of only one row per tweet.
2. Generate topic-level index notes after export.
3. Add fixtures from real captured payloads for regression testing.
4. Add a safe dry-run mode for extraction diagnostics.

---

## Definition Of Done For Any Sprint

A sprint is only done when:

1. The promised slice works end-to-end at the level claimed in the sprint goal.
2. Verification has been run, not assumed.
3. Failure cases are handled clearly enough that Lee would not be surprised.
4. `sprint-plan.md`, `context.md`, and other handoff docs reflect reality.

---

*Update this file whenever sprint scope, status, sequencing, or exit criteria change.*
