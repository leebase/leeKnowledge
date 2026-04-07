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
6. For broad sprint execution, prefer Agent-Orch workflows under `playbooks/`
   over ad hoc manual sessions.

---

## Canon

| Document | Role In This Plan |
|----------|-------------------|
| `product-definition.md` | Defines the real user problem and MVP |
| `architecture.md` | Defines the pipeline shape and technical boundaries |
| `project-plan.md` | Defines the phase roadmap |
| `context.md` | Defines current session state and next actions |
| `playbooks/roadmap-sprints.yaml` | Governs multi-sprint execution through Agent-Orch |

---

## Delivery Map

| Sprint | Phase | Goal | Status |
|--------|-------|------|--------|
| Sprint 1 — Foundation | Phase 1 | Establish runnable scaffold, DB, CLI skeleton, tests | ✅ Complete |
| Sprint 2 — Extraction Slice | Phase 2 | Capture raw bookmark payloads and normalize to SQLite | ✅ Complete |
| Sprint 3 — Enrichment Slice | Phase 3 | Expand URLs and enrich unprocessed bookmarks | ✅ Complete |
| Sprint 4 — Export Slice | Phase 4 | Render Markdown vault and wire `sync` end-to-end | ✅ Complete |
| Sprint 5 — Export Hardening | Phase 4 | Close review findings and reach sign-off-ready export behavior | ✅ Complete |

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

**Status:** COMPLETE  
**Sprint Goal:** Deliver one thin vertical slice that captures X bookmark payloads into an immutable raw archive and normalizes those payloads into SQLite bookmark rows with tweet-id deduplication.

Sprint 2 stops at raw capture and canonical bookmark rows; URL expansion, page metadata fetch, and LLM enrichment are deferred to Sprint 3.

### Implementation Plan

Sprint 2 is intentionally narrow: the extractor owns browser access, authentication checks, GraphQL capture, and raw archive persistence; the normalizer owns deterministic raw-to-canonical mapping; SQLite owns deduplication.

**Extractor boundary**
- Launch Chrome with an existing logged-in profile.
- Reach `x.com/i/bookmarks` and confirm the session is authenticated.
- Capture GraphQL `Bookmarks` payloads only; do not invent canonical fields in the extractor.
- Persist the raw archive before any SQLite mutation.
- Pass the archived raw capture to normalization.

**Raw archive rules**
- Write one immutable file per run to `data/raw/bookmarks_YYYY-MM-DD.json` before normalization starts.
- Store verbatim payloads plus capture metadata needed for replay.
- Preserve unknown source fields in raw form.
- Treat the raw archive as append-only for the run; never rewrite it after normalization starts.

**Canonical normalization**
- Convert the archived raw payloads into canonical bookmark rows in `normalizer.py`.
- The canonical row shape is defined by the SQLite schema and keyed by `tweet_id`.
- Use `INSERT OR IGNORE` so reruns are safe.
- Skip or quarantine bad records explicitly rather than guessing.
- Allow only deterministic derivation; no LLM, browser state, or retry heuristics in normalization.

**Fallback sequencing**
1. If Chrome does not reach an authenticated bookmarks page, stop immediately with a readable error.
2. If GraphQL capture yields no bookmark payloads, write the raw archive and then stop before SQLite inserts; SQLite stays untouched on this path.
3. If the raw archive cannot be written, stop before normalization.
4. If normalization encounters a bad record, quarantine or skip it explicitly rather than guessing.
5. DOM fallback is deferred to a later hardening pass and must reuse the same raw contract if introduced.

**Out of scope**
- URL expansion or page-metadata fetch
- LLM enrichment
- Markdown export
- Thread reconstruction
- Topic curation or vault polish

### Required Outputs

| Output | Contract |
|--------|----------|
| Raw archive | `data/raw/bookmarks_YYYY-MM-DD.json` is written before SQLite mutation |
| SQLite rows | `bookmarks` contains canonical rows for captured tweet IDs |
| Dedup safety | Re-running against the same data does not create duplicate `tweet_id` rows |
| Failure signal | Login, capture, archive, or schema problems stop with readable errors and no partial corruption |

### Why This Sprint Exists

Extraction is the riskiest part of the product. Once raw payloads are captured and normalized reliably, the downstream pipeline becomes deterministic engineering work.

### Task Board

| ID | Task | Priority | Status | Depends On | Verification |
|----|------|----------|--------|------------|--------------|
| 2.1 | Stand up Python 3.12+ dev environment and install declared deps | P0 | ✅ Done | None | `pip install -e ".[dev]"` succeeds |
| 2.2 | Decide local config defaults for Chrome profile, DB path, and raw output path | P0 | ✅ Done | 2.1 | Config values are documented or encoded clearly, including failure messages for auth and capture stops |
| 2.3 | Implement Chrome launch with existing user profile in `extractor.py` | P0 | ✅ Done | 2.1, 2.2 | Browser opens authenticated session |
| 2.4 | Add navigation/auth check for `x.com/i/bookmarks` | P0 | ✅ Done | 2.3 | Clear error if redirected to login |
| 2.5 | Intercept GraphQL bookmark responses and retain verbatim payloads plus replay metadata in memory | P0 | ✅ Done | 2.4 | At least one `Bookmarks` payload captured |
| 2.6 | Persist immutable archive to `data/raw/bookmarks_YYYY-MM-DD.json` and hand it to normalization | P0 | ✅ Done | 2.5 | Raw file created before normalization and not rewritten during the run |
| 2.7 | Implement deterministic raw-to-canonical parsing in `normalizer.py` | P0 | ✅ Done | 2.5 | Canonical bookmark records produced from sample payloads; malformed records are skipped or quarantined explicitly |
| 2.8 | Insert normalized bookmarks into SQLite with dedup semantics | P0 | ✅ Done | 2.7 | Duplicate tweet IDs are ignored on rerun |
| 2.9 | Wire `extract` CLI command through browser capture, archive write, and normalization | P0 | ✅ Done | 2.6, 2.8 | `python -m leeknowledge extract` runs the slice end-to-end |
| 2.10 | Add automated tests for auth failure, raw archive persistence, normalization, and dedup edge cases | P1 | ✅ Done | 2.7, 2.8 | `pytest` covers parser, duplicate handling, and stop-on-failure behavior |

### Suggested Execution Order

1. Environment and config decisions: 2.1-2.2
2. Browser access and auth checks: 2.3-2.4
3. Capture and archive raw payloads: 2.5-2.6
4. Normalize into canonical SQLite rows: 2.7-2.8
5. Wire the CLI through both stages: 2.9
6. Add parser and dedup coverage: 2.10

### Verification Gates

The sprint is not done until all of these are true:

- `PYTHONPATH=src python3 -m leeknowledge extract` completes against a real,
  logged-in X session
- A new immutable archive appears under `data/raw/` before any SQLite mutation
- SQLite contains bookmark rows with stable tweet IDs
- A rerun does not duplicate existing rows
- `PYTHONPATH=src pytest` passes for raw parsing and dedup behavior
- Failure modes are readable, stop in the right order, and leave no partial corruption

### Manual Test Script

Run these in order during validation. Use a logged-in Chrome profile explicitly if the default macOS profile path is not the one you want.

```bash
python3 --version
pip install -e ".[dev]"
python -m playwright install chromium
PYTHONPATH=src python3 -m leeknowledge extract --chrome-profile-dir "$HOME/Library/Application Support/Google/Chrome"
sqlite3 state/app.db "select count(*) from bookmarks;"
PYTHONPATH=src pytest
PYTHONPATH=src python3 -m leeknowledge extract --chrome-profile-dir "$HOME/Library/Application Support/Google/Chrome"
sqlite3 state/app.db "select count(*) from bookmarks;"
```

Validation order matters: confirm auth and raw capture first, then inspect SQLite, then rerun to prove dedup safety. The raw archive path and database path may also be overridden with `LEEKNOWLEDGE_RAW_DIR` and `LEEKNOWLEDGE_DB_PATH`.

### Risks To Manage During This Sprint

| Risk | Impact | Mitigation |
|------|--------|------------|
| X changes GraphQL shape or blocks interception | Capture may fail completely | Preserve raw files first and validate parsed fixtures before wiring SQLite |
| Chrome profile selection is wrong | Extraction cannot authenticate | Make profile path explicit and validate early |
| Raw payload shape is messier than expected | Normalizer work expands | Preserve raw files first and build parser from fixtures |
| Local Python version is below target | Runtime/dependency drift | Move to Python 3.12 environment before deeper work |
| Playwright launches but login session is stale | Manual run fails late | Add early auth detection and clear guidance |
| Empty capture reaches normalization | Could corrupt the sprint signal | Fail fast before archive-to-SQLite handoff |

### Decisions Needed During The Sprint

| Decision | Why It Matters | Preferred Timing |
|----------|----------------|------------------|
| Chrome profile path strategy | Determines whether extraction is reliable on Lee's machine | Before 2.3 |
| Raw archive naming granularity | Affects replayability and auditability | Before 2.6 |
| Canonical bookmark field minimums | Defines what "successful normalization" means | Before 2.7 |
| Whether DOM fallback is ever admitted into Sprint 2 | Affects selector work and failure behavior | Before extractor implementation starts |

### Closeout Checklist

- [x] Mark completed tasks above
- [x] Update `context.md` with new current work and next actions
- [x] Update `WHERE_AM_I.md` for milestone progress
- [x] Add a result entry to `result-review.md` for the Sprint 2 handoff
- [x] Record extractor-specific technical decisions in `architecture.md`

---

## Sprint 3 — Enrichment Slice

**Status:** COMPLETE  
**Sprint Goal:** Expand URLs, validate structured enrichment output, and persist one enrichment row per bookmark that does not already have one.

Sprint 3 stopped at idempotent enrichment and URL cache maintenance; export, topic curation, and any re-enrichment history workflow are deferred to Sprint 4 or later.

### Implementation Plan

Sprint 3 delivered a thin vertical slice around deterministic URL expansion, structured LLM output, and safe SQLite persistence. The enricher owns model routing and validation; the URL cache owns replayable resolution; SQLite owns deduplication by `tweet_id`.

**Config and versioning**
- Keep provider, model, temperature, and timeout settings in `config/llm.yaml`.
- Resolve the enricher role through `lee-llm-router` and the pi harness; when running the workflow through Agent-Orch, pin the whole run with `AGENT_ORCH_PI_MODEL=<model>` instead of trying to route per step.
- Store `model` from the resolved config plus explicit `prompt_version` and `schema_version` constants with every enrichment row.
- Bump `prompt_version` whenever the prompt body changes and `schema_version` whenever the output shape or validation contract changes.

**Enrichment flow**
- Load bookmarks that do not yet have an enrichment row.
- Expand each `raw_urls` entry through `url_cache` and refresh `resolved_url`, `page_title`, `page_description`, and `cached_at` on success.
- Optionally fetch page metadata; missing metadata must not block persistence.
- Build a prompt from tweet text, author fields, resolved URLs, and any fetched metadata.
- Request exactly one JSON object with `summary`, `tags`, `entities`, and `topic`.
- Validate the response before any write; malformed JSON or missing required fields fall back to the null placeholder path.

**Persistence rules**
- Store one row per `tweet_id` in `enrichments`.
- Persist `summary`, `tags`, `entities`, `topic`, `model`, `prompt_version`, `schema_version`, `validation_status`, and `enriched_at`.
- Leave existing enrichment rows unchanged on rerun.
- Record null enrichment placeholders instead of inventing structured data when the response cannot be validated.

**Failure handling**
1. If the local LLM config is missing or cannot be parsed, fail before any enrichment writes.
2. If URL expansion times out, keep the original URL and continue.
3. If page metadata fetch fails, keep null metadata fields and continue.
4. If the LLM request times out, errors, or returns malformed JSON, write the null enrichment placeholder and continue with the next bookmark.
5. If validation rejects a response, write the null enrichment placeholder and preserve the failure status for review.
6. If the enrichments row already exists, skip it instead of rewriting history.

### Delivered

- `config/llm.yaml` contract for enricher provider/model settings and code-level prompt/schema version constants
- URL cache upserts keyed by `original_url`
- Optional page title/description fetch
- Strict structured prompt and JSON validation
- `enrich` CLI command over un-enriched bookmarks only
- Versioned enrichment storage with null-placeholder handling

### Entry Criteria

- Sprint 2 complete
- At least one usable dataset exists in SQLite
- Local LLM config is available
- Bookmarks contain `raw_urls` for expansion

### Task Board

| ID | Task | Priority | Status | Depends On | Verification |
|----|------|----------|--------|------------|--------------|
| 3.1 | Finalize LLM config shape, provider routing, and version constants | P0 | ✅ Done | Sprint 2 complete | `config/llm.yaml` loads and version constants are documented |
| 3.2 | Implement URL cache resolution and optional metadata fetch | P0 | ✅ Done | 3.1 | URL cache rows upsert and rerun reuses cached data |
| 3.3 | Define enrichment schema, storage columns, and null-placeholder behavior | P0 | ✅ Done | 3.1 | SQLite schema stores `model`, `prompt_version`, `schema_version`, and `validation_status` |
| 3.4 | Implement prompt building, LLM call, and strict JSON validation | P0 | ✅ Done | 3.2, 3.3 | Valid sample output persists; malformed output fails into placeholder path |
| 3.5 | Wire `enrich` CLI to process only un-enriched bookmarks | P0 | ✅ Done | 3.4 | `python -m leeknowledge enrich` runs end-to-end on eligible rows |
| 3.6 | Add automated tests for malformed JSON, timeout, rerun idempotence, and cache reuse | P1 | ✅ Done | 3.4, 3.5 | `pytest` covers validation, placeholder, and rerun behavior |

### Suggested Execution Order

1. LLM config and versioning contract: 3.1
2. URL cache and metadata fetch: 3.2
3. Enrichment schema and placeholder behavior: 3.3
4. Prompting, validation, and persistence: 3.4
5. CLI wiring and rerun skipping: 3.5
6. Test coverage and repair: 3.6

### Verification Gates

The sprint is not done until all of these are true:

- `PYTHONPATH=src python3 -m leeknowledge enrich` processes eligible bookmarks
- A second run does not create duplicate enrichment rows
- URL cache entries are reused on rerun
- Malformed JSON is recorded as a null enrichment placeholder without inventing values
- Stored rows include the configured model and the explicit prompt/schema version fields
- `PYTHONPATH=src pytest` passes for validation, cache reuse, and rerun behavior

### Manual Test Script

Run these in order during validation.

```bash
python3 --version
pip install -e ".[dev]"
PYTHONPATH=src python3 -m leeknowledge enrich
sqlite3 state/app.db "select count(*) from enrichments;"
sqlite3 state/app.db "select tweet_id, model, prompt_version, schema_version, validation_status from enrichments limit 5;"
PYTHONPATH=src pytest
PYTHONPATH=src python3 -m leeknowledge enrich
sqlite3 state/app.db "select count(*) from enrichments;"
```

Validation order matters: confirm config load and validation first, then inspect SQLite, then rerun to prove idempotence and cache reuse.

### Risks To Manage During This Sprint

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM config drift or missing local config | Enrichment cannot start | Fail fast before any writes and document the required `config/llm.yaml` shape |
| Schema changes without version bumps | Replay ambiguity | Store explicit `prompt_version` and `schema_version` values in every row |
| URL expansion or metadata fetch timeouts | Slower runs | Keep enrichment best-effort and preserve original URLs and null metadata |
| Malformed model output | Bad or partial data | Validate strictly and write the null enrichment placeholder |
| Rerun rewrites existing rows | Loss of provenance | Skip existing `tweet_id` rows and keep the single-row contract |

### Decisions Needed During The Sprint

| Decision | Why It Matters | Preferred Timing |
|----------|----------------|------------------|
| Exact `config/llm.yaml` provider/model defaults | Determines whether enrichment can run locally without edits | Before 3.1 |
| Prompt and schema version naming convention | Makes stored rows traceable across prompt changes | Before 3.3 |
| Null-placeholder fields versus validation status values | Defines what failure looks like in SQLite | Before 3.3 |
| Whether page metadata fetch uses the same retry budget as URL expansion | Affects total runtime and failure behavior | Before 3.2 |

---

## Sprint 4 — Export Slice

**Status:** COMPLETE  
**Goal:** Turn SQLite bookmarks plus enrichment data into a browsable Markdown vault and wire `sync` end-to-end.

Sprint 4 shipped the first end-to-end export path and completed successfully through the resumed Agent-Orch run `63e50cd3b7d9`. The slice is functionally complete, but the review that followed opened a hardening sprint before final sign-off.

### Scoped Delivery Contract

Sprint 4 delivered deterministic export and orchestration:

- Render one Markdown note per bookmark from SQLite only
- Place notes in a stable vault layout that Obsidian can browse directly
- Preserve source text, enrichment provenance, and resolved link metadata in each note
- Make `export` rerunnable without duplicate or conflicting files
- Make `sync` run extract → enrich → export sequentially and stop on the first failing stage
- Validate the rendered vault with golden tests plus manual fidelity spot checks

### Delivered

- Jinja2 note rendering for bookmark + enrichment rows
- Stable vault path generation under `vault/YYYY/MM/<slug>-<tweet_id>.md`
- Atomic note replacement on rerun
- Live `export` CLI wiring
- Live `sync` orchestration across extract → enrich → export
- Export-focused automated coverage in `tests/test_export.py`
- Agent-Orch implementation, documentation, repair/verify, review, and closeout passes

### Review Findings Carried Forward

- R001: the review shell did not have `pytest` installed, so the final review could not validate the suite in the intended Python 3.12+ dev environment
- R002: `export` currently bootstraps SQLite state via `initialize_database()` instead of failing read-only on a missing DB path
- R003: Markdown-sensitive tweet text, summaries, and resolved-link metadata are interpolated without escaping and can alter note structure

### Exit Criteria Met

- `PYTHONPATH=src python3 -m leeknowledge export` rendered Markdown notes from SQLite
- `PYTHONPATH=src python3 -m leeknowledge sync` ran extract → enrich → export in order
- Export wrote notes into the stable vault path contract and replaced files atomically on rerun
- `tests/test_export.py` was added and passed during the implementation/repair flow

---

## Sprint 5 — Export Hardening

**Status:** COMPLETE  
**Goal:** Fix the Sprint 4 review findings so export is read-only safe, Markdown-fidelity safe, and sign-off ready in the documented dev environment.

Sprint 5 is intentionally narrow. The export and sync slice already exists; this sprint closes the defects and validation gaps discovered in the first review.

### Scoped Delivery Contract

Sprint 5 is limited to remediation and sign-off hardening:

- Make `export` fail clearly when the SQLite database path is missing
- Ensure export does not initialize or migrate SQLite state on a read-only path
- Escape or fence Markdown-sensitive source text and link metadata so note structure remains stable
- Add tests that lock the fixes in place
- Re-run verification and review in the documented Python 3.12+ dev environment

### In Scope

- `src/leeknowledge/exporter.py` read-only DB validation changes
- `src/leeknowledge/templates/bookmark.md.j2` and any helper changes needed for Markdown escaping
- Export-specific tests for missing DB and Markdown-sensitive content
- Dev-environment verification for `pytest`
- Handoff docs updated to reflect the post-hardening state

### Out of Scope

- New product features beyond the existing export contract
- Extraction logic changes unrelated to export correctness
- Re-enrichment history or vault index-note work

### Entry Criteria

- Sprint 4 complete
- Review findings R001-R003 documented in `code-reviews/review-2026-04-07.md`
- Existing export and sync code present in `src/leeknowledge/exporter.py` and `src/leeknowledge/cli.py`

### Task Board

| ID | Task | Priority | Status | Depends On | Verification |
|----|------|----------|--------|------------|--------------|
| 5.1 | Remove export-time DB bootstrapping and fail fast on missing SQLite path | P0 | ✅ Done | Sprint 4 complete | `export` raises a readable error and does not create `state/app.db` when the DB path is absent |
| 5.2 | Add automated coverage for missing-DB export behavior | P0 | ✅ Done | 5.1 | Test proves `export_markdown()` does not create or migrate a missing DB |
| 5.3 | Escape or fence Markdown-sensitive tweet text, summaries, and resolved-link metadata | P0 | ✅ Done | Sprint 4 complete | Exported notes preserve literal content for `#`, `*`, and Markdown link syntax |
| 5.4 | Add automated coverage for Markdown-fidelity edge cases | P0 | ✅ Done | 5.3 | Tests prove note structure remains stable for Markdown-heavy content |
| 5.5 | Re-run the full export verification flow in Python 3.12+ with dev dependencies installed | P0 | ✅ Done | 5.2, 5.4 | `PYTHONPATH=src pytest` passes in the intended dev environment |
| 5.6 | Re-run code review and sync handoff docs to the hardened state | P1 | ✅ Done | 5.5 | Review findings are cleared or explicitly downgraded, and docs match reality |

### Verification Gates

Sprint 5 is not done until all of these are true:

- `PYTHONPATH=src python3 -m leeknowledge export` fails clearly on a missing DB path and does not create SQLite state
- `PYTHONPATH=src python3 -m leeknowledge export` still renders notes correctly from a valid DB
- Markdown-sensitive tweet text, summaries, and resolved-link metadata render without corrupting note structure
- `PYTHONPATH=src pytest` passes in the documented Python 3.12+ dev environment
- A follow-up review no longer reports R002 or R003 as open issues

### Exit Criteria Met

- Missing SQLite paths now fail before export opens a writable database handle
- Export validates required tables and columns read-only and reports stale schemas clearly
- Summary/tweet content render in fenced literal blocks and resolved-link metadata is Markdown-escaped
- `PYTHONPATH=src .venv/bin/python -m pytest` passed under Python 3.12.13
- `PYTHONPATH=src .venv/bin/python -m leeknowledge export` passed against a valid smoke DB and failed cleanly against a missing DB
- Follow-up review in `code-reviews/sprint-5-export-hardening-review.md` found no new blocking issues

### Manual Test Script

Run these in order during validation.

```bash
python3 --version
pip install -e ".[dev]"
PYTHONPATH=src pytest
PYTHONPATH=src python3 -m leeknowledge export
find vault -type f | sort | head
PYTHONPATH=src python3 -m leeknowledge sync
```

After the commands, spot-check one exported note in Obsidian or a plain Markdown viewer and confirm:
- literal tweet text is preserved even when it contains Markdown syntax
- resolved links remain readable
- the note still carries frontmatter provenance and the X back-link

### Risks To Manage During This Sprint

| Risk | Impact | Mitigation |
|------|--------|------------|
| Escaping changes the visible note format too aggressively | Notes become harder to read | Prefer the smallest escaping or fenced-block approach that preserves fidelity |
| Read-only DB validation is too strict | Valid operator workflows break | Test both missing-DB and normal export paths before sign-off |
| Review rerun uses the wrong interpreter again | Sign-off remains ambiguous | Do the rerun inside the documented Python 3.12+ dev environment only |

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
