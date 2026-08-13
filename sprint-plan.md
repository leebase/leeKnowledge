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
| Sprint 6 — Topic Index Notes | Phase 5 | Add the first leadership-oriented derived view over the existing corpus | ✅ Complete |
| Sprint 7 — Leadership Synthesis | Phase 5 | Generate recurring leadership briefs from the local corpus | ✅ Complete |
| Sprint 8 — Leadership Metadata | Phase 5 | Add a small decision-oriented metadata layer for triage and prioritization | ✅ Complete |
| Sprint 9 — Curated Collections | Phase 5 | Support initiative-centered collection notes for live strategic work | ✅ Complete |
| Sprint 10 — Universal Source Ingestion | Phase 6 | Add bounded intake paths for URLs, Safari bookmark exports, and deep-research artifacts | ✅ Complete |

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

## Sprint 6 — Topic Index Notes

**Status:** COMPLETE  
**Goal:** Deliver one narrow Level 2 slice: leadership-oriented topic index notes generated from the existing local corpus, with a fixed first-pass taxonomy, stable vault paths, source backlinks, and explicit verification gates.

Sprint 6 is intentionally contract-first. It should prove that leeKnowledge can create useful leadership review surfaces without changing extraction, enrichment, or the per-bookmark export contract.

### Sprint 6 Delivery Contract

Sprint 6 delivers exactly one derived-artifact layer:

- a bounded first-pass leadership taxonomy of four topic notes
- deterministic assignment rules based on existing bookmark and enrichment data
- one stable Markdown note per topic under a dedicated derived area of the vault
- explicit backlinks from every generated topic entry to the source bookmark note and original X post
- rerunnable generation from existing local state only

### Taxonomy Boundaries

Sprint 6 is limited to these four topic keys:

| Topic Key | Include When The Bookmark Primarily Concerns | Explicitly Exclude |
|-----------|----------------------------------------------|--------------------|
| `ai-governance` | AI policy, risk, compliance, safety, regulation, auditability, model controls, or operating guardrails | Generic vendor launches, model benchmarks, or agent implementation tips unless governance/risk is central |
| `enterprise-agents` | Agent workflows, copilots, orchestration, evaluation, human-in-the-loop automation, or enterprise deployment patterns | General model news or data-stack posts unless the operational agent pattern is the main point |
| `data-platform` | Data architecture, pipelines, analytics engineering, semantic layers, observability, data quality, or platform operating models | Pure AI product chatter with no clear data-platform implication |
| `vendor-landscape` | Vendor comparisons, provider launches, pricing, partnerships, competitive movement, or tool/category market scans | General technical advice with no clear vendor or market angle |

Additional Sprint 6 boundary rules:
- No free-form new topics, catch-all notes, or nested taxonomy trees.
- A bookmark may appear in more than one topic note only if it matches deterministic rules for each topic.
- Uncategorized bookmarks remain source notes only; Sprint 6 does not force 100% coverage.
- Topic assignment must come from existing local data fields and deterministic matching rules, not new LLM calls.

### Grouping Rule Plan

Sprint 6 grouping must be implementation-ready and deterministic on day one.

**Inputs read for matching, in order of trust**
1. `enrichments.topic`
2. `enrichments.tags`
3. `enrichments.summary`
4. `bookmarks.text`
5. `bookmarks.raw_urls` only as a weak support signal for `vendor-landscape`

**Matching rules**
- Normalize all candidate text to lowercase before matching.
- Use a versioned in-code keyword map keyed by the four Sprint 6 topic keys.
- Treat `topic` and `tags` as the strongest signals because they are already structured outputs.
- Use `summary` and raw tweet text as fallbacks when structured fields are null or too sparse.
- Allow multi-topic membership only when a bookmark independently matches more than one topic rule.
- Do not create an `other` bucket and do not force topic assignment when no rule matches.

**Planned first-pass keyword shape**
- `ai-governance`: `governance`, `policy`, `regulation`, `regulated`, `risk`, `compliance`, `safety`, `guardrail`, `audit`, `evaluation`, `responsible ai`, `model control`
- `enterprise-agents`: `agent`, `agents`, `agentic`, `copilot`, `orchestration`, `workflow`, `human-in-the-loop`, `evaluation`, `tool use`, `automation`
- `data-platform`: `data platform`, `pipeline`, `etl`, `elt`, `analytics engineering`, `semantic layer`, `warehouse`, `lakehouse`, `observability`, `data quality`, `dbt`
- `vendor-landscape`: `launch`, `pricing`, `vendor`, `partner`, `partnership`, `acquisition`, `comparison`, `benchmark`, `model provider`, `openai`, `anthropic`, `google`, `microsoft`, `snowflake`, `databricks`

**Conflict and ambiguity rules**
- A governance-specific match beats a generic agent or vendor mention when the main framing is risk, compliance, or control.
- A vendor name alone is not enough for `vendor-landscape`; the surrounding text must also imply movement, comparison, pricing, launch, or partnership.
- `evaluation` may contribute to either `ai-governance` or `enterprise-agents`; include both only when the rest of the text supports both frames.
- If only one weak keyword appears in bookmark text and nothing structured supports it, prefer leaving the bookmark uncategorized.

### Topic Note Contract

Each generated topic note must:

- live at `vault/topics/<topic-key>.md`
- declare itself as a generated derived view, not a source record
- include the taxonomy scope or inclusion rule for that topic
- include a short "grouping hints" section so operators can understand why entries appear there
- show a most-recent-first bookmark list for that topic
- include, for every listed bookmark:
  - bookmark note backlink in the exported vault
  - original X status URL backlink
  - author handle
  - bookmark date
  - short visible context such as title, topic, or summary snippet
  - optional matched-signal text such as tags or topic when present

Suggested minimum frontmatter:
- `note_type: topic_index`
- `topic_key`
- `taxonomy_version`
- `generated_at`
- `bookmark_count`

Planned template structure:
1. Frontmatter with generated metadata
2. H1 title using a human-readable topic name
3. Short generated-note disclaimer
4. `## Scope` section with inclusion and exclusion summary
5. `## Grouping hints` section listing the high-level rule families used
6. `## Recent bookmarks` section with newest-first bullet entries
7. `## Generation notes` footer stating that the note is regenerated from local state

### Generator Boundary

Sprint 6 generation must be a pure derived-view step:

- Inputs: existing SQLite bookmark rows, enrichment rows, and deterministic bookmark-note paths
- Outputs: generated topic notes only
- Must not call X, Playwright, or the LLM
- Must not mutate source bookmark-note paths or SQLite source tables
- Must remain rerunnable without re-extracting or re-enriching

### In Scope

- Document the four-topic leadership taxonomy above
- Define deterministic grouping inputs, precedence, and ambiguity rules
- Define the stable vault path and backlink contract for topic notes
- Implement topic-note generation from existing local state
- Add a dedicated CLI entrypoint for derived topic-note generation
- Add automated verification for grouping, rendering, and rerun safety
- Do a human Obsidian usefulness check before sprint closeout

### Out Of Scope

- Weekly or monthly synthesis notes
- New LLM enrichment calls for topic-note generation
- New bookmark-level metadata fields in SQLite
- Additional source ingestion beyond X bookmarks
- Team-sharing, publishing, dashboards, or scoring systems
- Taxonomy expansion beyond the four named Sprint 6 topic keys

### Entry Criteria

- Sprint 5 complete
- Exported bookmark-note contract is stable
- At least one meaningful local corpus exists in SQLite
- The four-topic Sprint 6 taxonomy above is treated as the fixed initial scope

### Required Outputs

| Output | Contract |
|--------|----------|
| Topic taxonomy | The four Sprint 6 topic keys and inclusion/exclusion rules are documented and used as the only initial taxonomy |
| Topic notes | Exactly one generated Markdown note per topic at `vault/topics/<topic-key>.md` |
| Source backlinks | Every topic-note entry links to both the source bookmark note and the original X status URL |
| Rerun safety | Re-running topic generation updates the same files without creating duplicates or path drift |
| Verification record | Automated tests plus a human Obsidian spot-check confirm usefulness and source traceability |

### Task Board

| ID | Task | Priority | Status | Depends On | Verification |
|----|------|----------|--------|------------|--------------|
| 6.1 | Lock the four-topic taxonomy, keyword-map shape, and ambiguity rules | P0 | ✅ Done | Sprint 5 complete | Sprint and architecture docs name the same topic keys, precedence, and conflict rules |
| 6.2 | Lock the vault path contract, topic-note template structure, and derived-view generator boundary | P0 | ✅ Done | 6.1 | Docs name `vault/topics/<topic-key>.md`, the template sections, and forbid source-truth mutations |
| 6.3 | Implement deterministic topic assignment from existing bookmark + enrichment rows | P0 | ✅ Done | 6.1, 6.2 | Sample corpus produces expected topic membership without new LLM calls |
| 6.4 | Render topic notes with required source backlinks, matched-signal context, and newest-first ordering | P0 | ✅ Done | 6.3 | Generated notes show bookmark-note links, X links, author/date, and readable context |
| 6.5 | Add a dedicated `topics` CLI command and keep it separate from `export` | P0 | ✅ Done | 6.2, 6.4 | Operator can run `python -m leeknowledge topics` after export without re-extracting |
| 6.6 | Add automated coverage for taxonomy rules, stable paths, backlink rendering, command behavior, and rerun safety | P1 | ✅ Done | 6.3, 6.4, 6.5 | `pytest` covers grouping, path stability, backlinks, CLI wiring, and idempotent regeneration |
| 6.7 | Do a human Obsidian spot-check on at least one topic note | P1 | ↪ Deferred to Sprint 7 kickoff | 6.4, 6.5 | At least one topic note is useful for leadership review without manual cleanup |

### Suggested Execution Order

1. Lock taxonomy shape, keyword-map families, and ambiguity rules: 6.1
2. Lock note template sections, path contract, and generator boundary: 6.2
3. Implement grouping and membership tests against representative fixtures: 6.3
4. Render topic-note Markdown with backlinks and visible matched context: 6.4
5. Run the dedicated `topics` CLI command and verify `export` remains bookmark-note only: 6.5
6. Run the added automated coverage for grouping, rendering, CLI behavior, and rerun safety: 6.6
7. Run the human Obsidian usefulness review last, against generated notes from a realistic local corpus: 6.7

### Verification Summary

Sprint 6 implementation and automated verification are complete. The remaining manual usefulness spot-check was deferred into Sprint 7 kickoff so the first Level 2 slice can close with its current code-review follow-ups explicitly tracked.

Automated gates satisfied:

- Only the four named Sprint 6 topic keys are generated
- Topic notes are generated from existing local state without re-extracting from X or calling the LLM
- Generated notes land at `vault/topics/<topic-key>.md` with stable rerun-safe paths
- Every topic-note entry links to both the source bookmark note and the original X status URL
- `export` still renders bookmark notes without silently generating topic notes as a side effect
- `topics` generates exactly four deterministic notes under `vault/topics/` and no catch-all derived files
- `PYTHONPATH=src .venv/bin/python -m pytest` passes for topic taxonomy, grouping, rendering, backlink, CLI, and rerun behavior
- `code-reviews/sprint-6-topic-index-notes-review.md` captures the remaining hardening follow-ups for the shipped slice
- Human Obsidian usefulness confirmation is tracked as Sprint 7 kickoff work rather than a blocker on the Sprint 6 code closeout

### Verification Order

1. Unit-test the keyword map and ambiguity handling before rendering anything.
2. Test grouping over fixture rows that exercise multi-topic, uncategorized, and weak-signal cases.
3. Test Markdown rendering for stable frontmatter, newest-first ordering, and required backlinks.
4. Test the `topics` CLI command against a temporary DB + vault fixture.
5. Run `export`, then `topics`, against a realistic local corpus.
6. Re-run `topics` and confirm the same four files are updated in place with no duplicates or path drift.
7. Do the human Obsidian spot-check after the automated checks pass.

### Manual Test Script

Run these in order during validation.

```bash
PYTHONPATH=src .venv/bin/python -m pytest
PYTHONPATH=src .venv/bin/python -m leeknowledge export
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
find vault/topics -type f | sort
sed -n '1,200p' vault/topics/ai-governance.md
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
```

After the commands, open `vault/` in Obsidian and confirm:
- only the four Sprint 6 topic notes exist under `vault/topics/`
- topic notes are visually distinct from source bookmark notes
- each listed bookmark has both a bookmark-note backlink and an X backlink
- the note reads like a leadership index rather than a random bucket dump
- `sync` still stops at bookmark export and does not generate topic notes unless `topics` is run explicitly

### Risks To Manage During This Sprint

| Risk | Impact | Mitigation |
|------|--------|------------|
| Taxonomy is too broad or too clever | Topic notes become vague and unhelpful | Freeze Sprint 6 to four topic keys with explicit inclusion and exclusion rules |
| Topic assignment from existing enrichment is noisy | Notes lose trust quickly | Prefer deterministic matching plus visible source links over clever inference |
| Mixing topic-note generation into export creates regressions | Existing bookmark export could break | Keep the derived-view layer isolated and add regression coverage |
| Topic notes are traceable but still not useful | False confidence | Require a human Obsidian usefulness check before calling the sprint done |

### Decisions Locked For Sprint 6

| Decision | Rationale |
|----------|-----------|
| Sprint 6 taxonomy is limited to `ai-governance`, `enterprise-agents`, `data-platform`, and `vendor-landscape` | Keeps the first derived-view slice small enough to verify usefulness |
| Topic notes live at `vault/topics/<topic-key>.md` | Makes the derived layer easy to find and rerun safely |
| Every topic entry must link to both the bookmark note and the original X post | Preserves source traceability and trust |
| Topic assignment must use existing local data and deterministic rules only | Avoids turning Sprint 6 into a second enrichment system |
| Topic-note generation ships as a dedicated `topics` CLI command, not an implicit `export` side effect | Keeps the derived layer isolated and reduces regression risk for bookmark-note export |
| Matching precedence is `topic`/`tags` → `summary` → bookmark `text`, with URL domains as weak support only for vendor framing | Improves grouping quality while staying deterministic and bounded |
| Topic notes use one shared template with frontmatter, scope, grouping hints, recent bookmarks, and generation notes | Gives implementation a stable structure before coding starts |

### Sprint 6 Closeout Notes

- Automated verification passed with `PYTHONPATH=src .venv/bin/python -m pytest`
- The dedicated `topics` command shipped separately from `export`
- Sprint 6 review findings R001-R003 remain open in `code-reviews/sprint-6-topic-index-notes-review.md`
- Human Obsidian usefulness review is deferred into Sprint 7 kickoff

## Sprint 7 — Leadership Synthesis

**Status:** COMPLETE  
**Goal:** Deliver the first recurring leadership brief as a derived note layer over the shipped topic notes and the existing bookmark corpus, so Lee can review one time-bounded synthesis note instead of scanning only per-topic indexes.

Sprint 7 shipped the first weekly synthesis layer as a narrow derived-artifact slice. The repo now has a dedicated `synthesize` command, archived weekly brief paths, and a stable latest-brief alias while keeping extraction, enrichment, export, and topic generation as separate explicit stages.

### Delivered

- Dedicated `synthesize` CLI command for explicit weekly generation
- Archived weekly briefs at `vault/synthesis/weekly/YYYY/YYYY-Www.md`
- Latest-brief alias at `vault/briefs/latest-weekly-signals.md`
- Deterministic weekly windowing and evidence-pack selection over topic membership plus SQLite rows
- Required source trail links back to topic notes, bookmark notes, and original X posts
- Sprint 6 trust-gap fixes needed for synthesis confidence folded into the implementation path
- Automated synthesis coverage plus a closeout review documenting remaining quality gaps

### Exit Criteria Met

- A weekly synthesis note can now be generated from existing local state without re-extracting from X or re-enriching bookmarks
- The generated note lands at `vault/synthesis/weekly/YYYY/YYYY-Www.md` with stable rerun-safe pathing
- `vault/briefs/latest-weekly-signals.md` is refreshed to point to the generated weekly note
- The weekly note links to topic notes plus the cited bookmark notes and original X posts
- Weekly selection is deterministic for a fixed SQLite snapshot and period key
- `export` still exports bookmark notes only, `topics` still exports topic notes only, and synthesis remains an explicit separate step

### Verification Record

- `PYTHONPATH=src .venv/bin/python -m compileall src`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_synthesis.py`
- Sprint 7 closeout review captured remaining follow-ups in `code-reviews/sprint-7-leadership-synthesis-review.md`

### Follow-Ups Carried Forward

Sprint 7 is functionally complete, but the review identified four hardening items to carry into the next work stream:

- R001: weekly signal bullets should be more evidence-grounded and less count-heavy
- R002: synthesis should detect stale topic notes before linking them as current framing
- R003: `## Worth discussing` should not drop an active fourth topic by fixed taxonomy-order truncation
- R004: synthesis tests should lock the content-level behaviors behind R001-R003

### Decisions Locked For Sprint 7

| Decision | Rationale |
|----------|-----------|
| Sprint 7 starts with weekly synthesis, not both weekly and monthly generation at once | Keeps the first recurring brief slice small enough to verify usefulness |
| The canonical weekly brief is archived at `vault/synthesis/weekly/YYYY/YYYY-Www.md` and mirrored by `vault/briefs/latest-weekly-signals.md` | Preserves historical reruns while giving leadership prep a predictable entrypoint |
| Synthesis reads both topic membership and SQLite bookmark/enrichment rows | Topic notes provide framing, while SQLite provides deterministic period selection and source-truth counts |
| Synthesis ships as a dedicated command separate from `export` and `topics` | Preserves clean stage boundaries and reduces regression risk |
| Source traceability is mandatory from synthesis note to topic note, bookmark note, and original X post | Leadership trust depends on inspectable provenance |
| Candidate selection is deterministic even if section wording later uses an LLM | Prevents Sprint 7 from becoming an opaque second enrichment pipeline |

---

## Sprint 8 — Leadership Metadata

**Status:** COMPLETE  
**Goal:** Add one small decision-oriented metadata layer that helps Lee triage weekly signals and decide what deserves attention now, later, or not at all, without weakening the shipped topic-note and weekly-synthesis contracts.

Sprint 8 stays intentionally narrow. It is not a general scoring engine, a second taxonomy project, or a schema grab-bag. The slice adds only the minimum fields needed to support leadership triage during weekly review.

### Scoped Delivery Contract

Sprint 8 delivers exactly one metadata pass keyed to individual bookmarks and consumed by the existing derived-note layer.

**Locked field set**
- `strategic_relevance` — bounded enum: `monitor`, `important`, `strategic`
- `time_horizon` — bounded enum: `now`, `next-quarter`, `longer-term`
- `organizational_impact` — bounded enum: `team`, `cross-functional`, `company-wide`
- `leadership_question` — one short decision-oriented prompt, or null when the item is not strong enough to warrant one

**Operator meaning of each field**
- `strategic_relevance` answers how strongly the item should compete for leadership attention; `monitor` means useful watchlist context, `important` means likely worth review soon, and `strategic` means the item could materially shape priorities, posture, or decisions.
- `time_horizon` answers when the item is most likely to matter; `now` means active near-term attention, `next-quarter` means likely planning-window relevance, and `longer-term` means directional tracking without immediate action pressure.
- `organizational_impact` answers how broad the likely effect is; `team` stays mostly local, `cross-functional` spans multiple teams or operating groups, and `company-wide` could influence broad posture, policy, platform direction, or leadership communication.
- `leadership_question` answers what concrete follow-up discussion the bookmark may justify; it should frame a decision, tradeoff, or leadership conversation rather than summarize the source.

**Delivery rules**
- Metadata is a derived judgment over existing bookmark and enrichment rows, not new source truth.
- The metadata layer must stay inspectable: bounded enums plus one short question are preferred over opaque numeric scores.
- Metadata must preserve provenance by linking every surfaced item back to the bookmark note, topic note when relevant, and original X post.
- Sprint 8 must improve triage in the weekly leadership flow without forcing changes to extraction, normalization, or bookmark-note export.
- Bookmark-note rendering stays stable; Sprint 8 may surface metadata in synthesis and other derived views before adding it to source-note frontmatter.

### Implementation Plan

Sprint 8 should land as one explicit post-enrichment stage plus one narrow synthesis-rendering update.

**Generation boundary**
- Ship a dedicated `metadata` CLI command rather than folding generation into `export`, `topics`, or `synthesize`.
- Read only from existing local state: `bookmarks`, `enrichments`, and topic membership already derivable from current logic.
- Treat bookmarks with an enrichment row as the default eligible set; topic membership sharpens judgment but is not required for every metadata row.
- Keep prompt/schema validation as strict as enrichment: any invalid response becomes an explicit failed/null metadata row instead of guessed values.

**Storage and rerun rules**
- Use the existing separate `leadership_metadata` SQLite table keyed by `tweet_id`.
- Keep provenance/versioning fields on every row: `model`, `prompt_version`, `schema_version`, `validation_status`, and `generated_at`.
- Distinguish three states clearly:
  1. no row yet — metadata has not been attempted
  2. failed/null row — generation was attempted but unusable
  3. validated row — current metadata is available for rendering
- Default rerun behavior should skip rows that already have a validated current-version record.
- Regenerate rows that are missing, failed, or version-stale, then replace the single row for that `tweet_id` atomically.

**Field rendering rules**
- `strategic_relevance`, `time_horizon`, and `organizational_impact` should render as compact human-readable labels, not badges that imply a hidden score.
- `leadership_question` should render only when both of these are true:
  - the row validated successfully, and
  - the item is triage-worthy enough to justify discussion framing (`strategic`, or `important` with `time_horizon=now`)
- If metadata is missing or failed for a cited bookmark, synthesis should omit labels and questions rather than invent placeholders in the note body.

**Derived-view update boundary**
- Weekly synthesis is the first required consumer of Sprint 8 metadata.
- Topic notes and per-bookmark export stay unchanged in this sprint unless a later hardening need forces a minimal display tweak.
- `export` remains responsible only for bookmark notes under `vault/YYYY/MM/` and must not start reading or rendering leadership metadata implicitly.
- Weekly note sections should remain evidence-first: metadata sharpens prioritization around cited bookmarks, but source summaries, bookmark links, topic links, and X links remain the primary inspection path.

### Contract Decisions

**Where metadata lives**
- Store Sprint 8 metadata in SQLite as a separate derived table keyed by `tweet_id` rather than extending raw bookmark facts.
- Keep independent provenance on every row with the same style of contract used by enrichment: `model`, `prompt_version`, `schema_version`, `validation_status`, and `generated_at`.
- Treat missing metadata as an explicit nullable state; do not invent defaults just to fill the table.

**How metadata is generated**
- Read from existing bookmark rows, enrichment rows, and topic membership only.
- Use one tightly scoped generation step after `enrich` and before or alongside derived-note generation.
- Keep the output schema narrow and validated; invalid responses fall back to a null/failed metadata row rather than guessed values.
- Do not make metadata generation a side effect of `export`, `topics`, or `synthesize`.

**How metadata appears in leadership review**
- Weekly briefs should use metadata to sharpen triage, not to replace evidence.
- Prefer concise labels such as relevance, horizon, and impact near cited items or discussion sections.
- Use `leadership_question` only where it helps frame a concrete follow-up discussion.
- Metadata must not make a weak or stale item look stronger than its underlying evidence.

### Sprint 7 Follow-Up Sequencing For Metadata Trust

Sprint 8 implementation must either close or fence the Sprint 7 review findings before metadata is allowed to amplify weekly notes.

- R001 evidence grounding: synthesis bullets must cite concrete bookmark evidence before metadata labels are added.
- R002 stale-topic detection: synthesis must reject stale topic-note framing before showing metadata alongside topic-backed sections.
- R003 topic truncation: `## Worth discussing` must rank active topics by weekly activity/usefulness rather than taxonomy order before metadata is used to sharpen discussion prompts.
- R004 synthesis regression coverage: tests for the behaviors above should land alongside metadata rendering tests so trust does not depend on manual memory.

If any of R001-R003 remain open during implementation, Sprint 8 must gate metadata display behind the safer path: show metadata only on directly cited bookmark bullets, not as a stronger section-level framing device.

### Non-Goals And Guardrails

- No composite score, weighted ranking formula, or probability model
- No expansion beyond the four locked fields above
- No free-form analyst memo per bookmark beyond the single `leadership_question`
- No changes to the Sprint 6 topic taxonomy as part of this slice
- No monthly synthesis expansion unless needed later by a separate sprint

### In Scope

- Lock the four-field metadata contract, enum values, and non-goals
- Define the separate SQLite storage contract and provenance fields
- Define the generation-stage boundary and failure handling
- Define how weekly briefs should consume metadata without losing evidence-first readability
- Resolve or explicitly sequence the Sprint 7 follow-ups that affect metadata trust
- Add verification for metadata generation, rendering, traceability, and rerun safety

### Out Of Scope

- Large scoring systems or forecasting models
- Broad new taxonomy work beyond the shipped Sprint 6 topic layer
- Publishing or collaboration workflows
- Monthly synthesis expansion
- Rich per-bookmark strategic narratives beyond the single leadership question field

### Required Outputs

| Output | Contract |
|--------|----------|
| Metadata rows | `leadership_metadata` holds at most one current row per `tweet_id`, with explicit provenance and validation status |
| Metadata command | A dedicated `python -m leeknowledge metadata` path exists and does not run implicitly from `export`, `topics`, or `synthesize` |
| Weekly rendering | Weekly briefs show compact relevance/horizon/impact labels and optional leadership questions only for validated, evidence-backed items |
| Trust guardrails | Missing, failed, or stale metadata never renders as fabricated defaults and does not outrank source evidence |
| Verification record | Tests plus a realistic local workflow prove rerun safety, traceability, and evidence-first rendering |

### Task Board

| ID | Task | Priority | Status | Depends On | Verification |
|----|------|----------|--------|------------|--------------|
| 8.1 | Lock the four-field metadata contract, enum values, and non-goals | P0 | ✅ Done | Sprint 7 complete | Sprint docs and architecture name the same fields, allowed values, and exclusions |
| 8.2 | Lock separate SQLite storage plus provenance/versioning for leadership metadata | P0 | ✅ Done | 8.1 | Storage boundaries are explicit and keep metadata distinct from source bookmark facts |
| 8.3 | Define the generation-stage boundary and failure behavior for metadata rows | P0 | ✅ Done | 8.2 | Docs specify inputs, validation, rerun behavior, and null/failed-row handling |
| 8.4 | Sequence or fix Sprint 7 review findings R001-R004 before metadata can amplify synthesis | P0 | ✅ Done | 8.1 | Evidence grounding, stale-topic checks, topic ranking, and regression coverage are fixed or fenced |
| 8.5 | Implement dedicated metadata generation with row eligibility, validation, and atomic rerun behavior | P0 | ✅ Done | 8.2, 8.3, 8.4 | `python -m leeknowledge metadata` writes the expected table rows and skips current validated rows on rerun |
| 8.6 | Update weekly synthesis rendering to consume validated metadata without changing bookmark-note export or topic-note output | P0 | ✅ Done | 8.5 | Weekly briefs show labels/questions only where evidence and metadata status justify them |
| 8.7 | Add automated coverage for metadata generation, synthesis rendering, missing/failed rows, and rerun safety | P1 | ✅ Done | 8.5, 8.6 | `pytest` covers schema validation, command behavior, rendering, and trust guardrails |
| 8.8 | Run realistic end-to-end verification and a human usefulness spot-check | P1 | ↪ Human follow-up remains | 8.6, 8.7 | The metadata-aided weekly brief is more useful for leadership scan without manual cleanup |

### Suggested Execution Order

1. Fix or fence Sprint 7 trust issues first: evidence grounding, stale-topic detection, topic ranking, and synthesis regression coverage.
2. Add metadata table access, row-eligibility selection, and strict schema validation before any rendering changes.
3. Wire the dedicated `metadata` CLI command and prove rerun semantics against missing, failed, and current-version rows.
4. Update weekly synthesis templates/helpers to render compact labels and optional leadership questions only for validated rows.
5. Run automated tests before realistic corpus generation.
6. Run the local operator flow in order: `export → topics → metadata → synthesize`.
7. Do the human usefulness review last against a generated weekly brief.

### Verification Order

1. Unit-test enum validation and null/failed-row persistence for metadata generation.
2. Test rerun behavior for missing, failed, validated, and version-stale metadata rows.
3. Test synthesis rendering for compact labels, optional question display, and omission when metadata is absent or failed.
4. Test the fenced behavior for any still-open Sprint 7 trust issues so metadata cannot overstate weak evidence.
5. Run `PYTHONPATH=src .venv/bin/python -m pytest`.
6. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge export`.
7. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge topics`.
8. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge metadata`.
9. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period 2026-W15`.
10. Inspect the generated weekly brief and confirm metadata improves triage without hiding source evidence.

### Manual Test Script

Run these in order during validation.

```bash
PYTHONPATH=src .venv/bin/python -m pytest
PYTHONPATH=src .venv/bin/python -m leeknowledge export
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
PYTHONPATH=src .venv/bin/python -m leeknowledge metadata
sqlite3 state/app.db "select tweet_id, strategic_relevance, time_horizon, organizational_impact, validation_status from leadership_metadata limit 10;"
PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period 2026-W15
sed -n '1,240p' vault/synthesis/weekly/2026/2026-W15.md
```

After the commands, confirm:
- metadata rows exist only once per `tweet_id`
- failed/null rows are distinguishable from never-generated rows
- weekly briefs render compact metadata labels only for validated items
- `leadership_question` appears only where the item is clearly discussion-worthy
- source bookmark links, topic links, and X links remain the primary trust path

### Sprint 8 Closeout Notes

- The dedicated `metadata` command now generates rerun-safe leadership triage rows in `leadership_metadata`
- Weekly synthesis now consumes current validated metadata when available while staying evidence-first and bookmark-link grounded
- Sprint 7 trust issues are handled in the shipped synthesis path through stale-topic detection, topic ranking, and regression coverage for metadata-aware rendering
- Bookmark-note export and topic-note generation remain separate unchanged stages
- Human usefulness confirmation for the metadata-aided brief remains a follow-up, not a blocker on the sprint code closeout

---

## Sprint 9 — Curated Collections

**Status:** COMPLETE  
**Goal:** Add initiative-centered collection notes for live strategic work by composing the shipped bookmark, topic, synthesis, and metadata layers into a small set of stable evidence-backed collection artifacts.

Sprint 9 is the first slice that should make leeKnowledge directly useful inside active leadership initiatives rather than only as a review surface. The sprint must stay narrow: collection notes are not a full project tracker, CRM, or second PKM system. They are generated initiative briefs that help Lee move from "interesting saved signal" to "evidence I can use in a live strategy thread."

### Scoped Delivery Contract

Sprint 9 delivers exactly one new derived-note layer:

- a bounded checked-in set of active initiative definitions chosen by the operator
- one stable generated Markdown collection note per active initiative
- evidence-backed entries selected from the existing bookmark, topic, synthesis, and metadata layers
- clear source traceability back to bookmark notes and original X posts
- rerunnable regeneration without changing extraction, enrichment, export, topic generation, synthesis, or metadata contracts

### Collection Boundaries

Sprint 9 must stay intentionally small and inspectable.

**Collection purpose**
- A collection note exists to support one live leadership initiative, decision area, or strategic workstream.
- Each collection should answer a concrete framing question such as "What external signals should shape our AI operating model?" rather than simply grouping vaguely similar posts.
- Collections are allowed to be selective; they should capture the best current evidence, not every possibly related bookmark.

**Collection limits**
- Start with a small operator-curated set of active initiatives rather than trying to infer all possible collections automatically.
- Do not add free-form per-item annotations beyond lightweight generated context plus any small initiative framing block required by the collection definition.
- Do not turn collection notes into task trackers, owner/status boards, or manually maintained knowledge bases.
- Do not change topic taxonomy, bookmark-note rendering, weekly-brief structure, or metadata schema as part of this sprint.

### Initiative Definition Contract

The first Sprint 9 implementation should use an explicit checked-in definition source for active collections.

**Planned definition source**
- Store the operator-maintained initiative list at `playbooks/curated-collections.yaml`.
- Keep the file small, reviewed, and checked in with the repo so collection behavior stays inspectable.
- Treat the definitions file as configuration for the collection generator, not as a manual note store.

Each initiative definition must include at least:
- `initiative_slug` — stable file-safe identifier used for the note path
- `title` — human-readable initiative name
- `status` — bounded operator label: `active` or `watching`
- `leadership_question` — the decision, posture, or design question the collection is meant to support
- `scope_note` — short explanation of what belongs in the collection
- `topic_keys` — optional preferred Sprint 6 topic keys for framing and candidate narrowing
- `metadata_preferences` — optional bounded hints such as `strategic_relevance`, `time_horizon`, and `organizational_impact`
- `source_window_days` — optional recency window used for default candidate trimming
- `max_items` — bounded note size target so collections stay reviewable

Recommended optional fields for Sprint 9 planning:
- `weekly_priority` — whether recent weekly-brief presence should act as a tie-breaker, not a hard include rule
- `include_tags_any` — small operator hint list for deterministic enrichment-tag matching when topic keys alone are too broad
- `description` — one short human-oriented summary line used only near the note header

**Definition guardrails**
- Keep the first implementation to three to five initiatives total.
- `max_items` should normally stay between 5 and 12.
- `topic_keys` must reuse the Sprint 6 taxonomy; Sprint 9 does not introduce a second topic tree.
- The operator-defined initiative list is the only manual curation layer required in Sprint 9. Bookmark inclusion should still be generated from current local state.

### Initiative Mapping Plan

Sprint 9 should make initiative mapping explicit before any ranking logic is added.

**Initial mapping approach**
1. Operator definitions declare the initiative question and framing hints.
2. The generator builds a candidate set from existing local state only.
3. Each included bookmark carries one or more visible inclusion reasons such as `topic match`, `metadata fit`, `recent weekly mention`, or `tag match`.
4. The rendered note shows those reasons so Lee can understand why an item is present without reading code.

**Planned first-pass example mapping shape**
- `ai-operating-model` → likely `ai-governance` + `enterprise-agents`, prefer `strategic` / `important`, bias toward `now` and `next-quarter`
- `data-platform-strategy` → likely `data-platform`, allow `vendor-landscape` when platform movement is directly relevant
- `vendor-watchlist` → likely `vendor-landscape`, require stronger evidence of launch, pricing, partnership, or comparison activity

The exact initial initiatives should stay operator-chosen, but the implementation should assume that each initiative can be mapped through a small mix of topic keys, metadata preferences, and optional tag hints.

### Source Selection Rules

Sprint 9 item selection should remain deterministic and evidence-first.

**Inputs allowed**
1. exported bookmark-note paths
2. SQLite bookmark rows
3. enrichment fields already stored locally
4. deterministic Sprint 6 topic membership
5. archived weekly synthesis outputs or latest-brief context
6. validated Sprint 8 metadata rows

**Selection pipeline**
1. Start from bookmarks that already have bookmark-note paths and usable local fields.
2. Build a candidate pool when at least one initiative signal matches:
   - topic membership matches an initiative `topic_keys` hint
   - enrichment `topic` or `tags` match an initiative hint
   - validated metadata fits an initiative preference
   - the bookmark was cited in a recent weekly brief relevant to the same framing
3. Drop weak candidates that only have a single loose text/tag signal with no supporting topic, metadata, or weekly context.
4. Rank the remaining candidates with visible precedence instead of a hidden score:
   - strongest: topic-key match plus validated metadata fit
   - next: topic-key match plus recent weekly mention
   - next: topic-key match only or metadata fit plus strong tag match
   - weakest allowed: one strong direct fit to the initiative question with no conflicting evidence
5. Trim to `max_items`, preferring newer items inside the same precedence bucket while still allowing one or two older anchor items when they are clearly stronger evidence.

**Selection guidance**
- Use validated metadata to prioritize within a candidate set, not to invent collection membership without source evidence.
- Weekly-brief presence is a boost, not a requirement; collections must still work when no recent synthesis mention exists.
- Allow a bookmark to appear in more than one initiative collection when the evidence genuinely supports both contexts.
- If no bookmarks satisfy the initiative definition, still generate the collection note with an explicit empty-state message and preserved framing.
- If multiple bookmarks say nearly the same thing, prefer the clearer or more leadership-relevant evidence rather than filling the note with duplicates.

### Collection Note Contract

Each generated collection note must:
- live at `vault/collections/<initiative-slug>.md`
- declare itself as a generated initiative view, not source truth
- state the initiative title, current status, and leadership question up front
- include a short scope section so the operator knows why items belong there
- include links to relevant topic notes and recent weekly briefs when available
- show a bounded most-relevant item list rather than an exhaustive dump
- include, for every surfaced item:
  - bookmark-note backlink
  - original X status URL backlink
  - author handle
  - bookmark date
  - short evidence context such as summary snippet, topic, or matched reason
  - compact metadata labels when the metadata row validated successfully
  - visible inclusion reasons so the initiative mapping stays inspectable

Suggested minimum frontmatter:
- `note_type: curated_collection`
- `initiative_slug`
- `initiative_title`
- `status`
- `generated_at`
- `bookmark_count`
- `source_window`
- `definition_version`

Suggested template structure:
1. Frontmatter
2. H1 title
3. Generated-note disclaimer
4. `## Leadership question`
5. `## Scope`
6. `## Why these items are here` summarizing the initiative mapping hints in plain English
7. `## Related views` with topic-note and weekly-brief links when present
8. `## Current evidence` with bounded initiative-backed entries
9. `## Gaps or watch items` empty-state or thin-signal guidance when evidence is sparse
10. `## Generation notes` explaining that the note is regenerated from local state

**Entry rendering rules**
- Surface the best reason first, such as a matching topic, a validated `strategic` label, or a recent weekly citation.
- Keep each item concise enough to scan in Obsidian without opening every source note.
- Do not render metadata labels when the row is missing or failed.
- Do not summarize past the available evidence; missing context should stay visible as missing context.

### Generator Boundary

Sprint 9 collection generation must remain a pure derived-view step:
- Inputs: existing local state plus the checked-in initiative definitions
- Outputs: generated collection notes only
- Must not call X or Playwright
- Must not require a new LLM pass just to build collections
- Must not mutate bookmark notes, topic notes, synthesis notes, or SQLite source tables
- Must remain runnable after `export`, `topics`, `metadata`, and `synthesize` without folding into those commands implicitly

### In Scope

- Lock the initiative-definition contract, checked-in definition path, and stable vault path for collection notes
- Define the bounded note shape, required backlinks, visible inclusion reasons, and evidence context for each collection entry
- Define deterministic initiative mapping and selection guidance across topic membership, weekly context, and validated metadata
- Keep the collection layer selective, rerunnable, and useful for active strategic work
- Add verification for stable paths, empty states, traceability, rerun-safe regeneration, and real-work usefulness

### Out Of Scope

- Full project-management workflows, action tracking, or owner/status systems
- A broad new taxonomy of dozens of collections
- New source ingestion or extraction changes
- A new LLM summarization stage dedicated only to collections
- Editing bookmark source notes or changing existing weekly/topic contracts

### Required Outputs

| Output | Contract |
|--------|----------|
| Initiative definitions | A checked-in bounded list of active collection definitions exists and is the only required manual curation layer |
| Collection notes | One generated note per active initiative at `vault/collections/<initiative-slug>.md` |
| Source traceability | Every surfaced item links to the bookmark note and original X post, with related topic/weekly links when available |
| Selective evidence | Notes stay bounded and decision-oriented rather than dumping every matching bookmark |
| Rerun safety | Regeneration updates the same files in place without duplicate artifacts or side effects on other stages |

### Task Board

| ID | Task | Priority | Status | Depends On | Verification |
|----|------|----------|--------|------------|--------------|
| 9.1 | Lock the checked-in initiative-definition file path, schema, and bounded allowed values | P0 | ✅ Done | Sprint 8 complete | Docs name `playbooks/curated-collections.yaml`, required fields, and bounded status/size rules |
| 9.2 | Lock the collection-note template, frontmatter contract, and visible inclusion-reason rendering | P0 | ✅ Done | 9.1 | Docs and architecture name the same file path, note sections, and per-item evidence fields |
| 9.3 | Define deterministic initiative mapping and candidate-selection precedence across topics, weekly context, tags, and validated metadata | P0 | ✅ Done | 9.1, 9.2 | Selection rules stay inspectable and do not rely on hidden scoring |
| 9.4 | Implement collection-note generation from existing local state plus initiative definitions | P0 | ✅ Done | 9.3 | Sample collections render to `vault/collections/` without changing other artifacts |
| 9.5 | Add a dedicated collection-generation CLI step separate from `export`, `topics`, `metadata`, and `synthesize` | P0 | ✅ Done | 9.4 | Operator can generate collections explicitly after the existing derived steps |
| 9.6 | Add automated coverage for definition parsing, path stability, traceability, candidate selection, bounded note size, empty states, and rerun safety | P1 | ✅ Done | 9.4, 9.5 | `pytest` covers deterministic generation plus sparse-evidence behavior |
| 9.7 | Run a human usefulness check against at least one live initiative collection and record whether the note helped a real decision thread | P1 | ↪ Post-roadmap follow-up | 9.4, 9.5 | One collection note is genuinely useful for active strategy work without manual cleanup |

### Suggested Execution Order

1. Keep the checked-in initiative-definition file path, schema, and first three to five initiative mappings aligned with `playbooks/curated-collections.yaml`.
2. Keep the note template, frontmatter, related-view links, and visible inclusion-reason shape aligned across docs and implementation.
3. Keep deterministic candidate assembly and precedence over existing local state inspectable in docs and code.
4. Implement collection-note generation and keep output bounded by initiative-level `max_items`.
5. Add the explicit CLI entrypoint and keep it separate from existing commands.
6. Add automated coverage for definition parsing, selection precedence, rendering, empty states, and rerun behavior.
7. Run automated verification before any human usefulness review.
8. Run a human spot-check last against one real initiative collection.

### Verification Order

1. Unit-test initiative-definition parsing, bounded enum handling, and required-field validation.
2. Test candidate selection for topic-backed, metadata-backed, weekly-backed, overlapping, duplicate-signal, and empty-collection cases.
3. Test Markdown rendering for stable frontmatter, required backlinks, related-view links, visible inclusion reasons, and bounded entry counts.
4. Test rerun behavior so the same initiative slug rewrites the same note path.
5. Run `PYTHONPATH=src .venv/bin/python -m pytest`.
6. Run the local operator flow in order: `export → topics → metadata → synthesize → collections`.
7. Inspect one generated collection note in Obsidian and confirm it helps with a live strategic question.
8. Record one concrete usefulness check: whether the collection changed a meeting agenda, follow-up list, or leadership prep decision.

### Manual Test Script

Run these in order during validation.

```bash
PYTHONPATH=src .venv/bin/python -m pytest
PYTHONPATH=src .venv/bin/python -m leeknowledge export
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
PYTHONPATH=src .venv/bin/python -m leeknowledge metadata
PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period 2026-W15
PYTHONPATH=src .venv/bin/python -m leeknowledge collections
find vault/collections -type f | sort
sed -n '1,240p' vault/collections/<initiative-slug>.md
```

After the commands, confirm:
- each active initiative produced exactly one stable collection note
- every surfaced item links back to a bookmark note and original X post
- the note includes a clear leadership question, scope statement, and visible reason each item is present
- metadata sharpens prioritization but does not hide source evidence
- the collection reads like execution support for a live initiative, not a generic topic dump
- at least one operator can point to a concrete next-step benefit from the note, even if that benefit is simply better meeting prep or better source recall

### Risks To Manage During This Sprint

| Risk | Impact | Mitigation |
|------|--------|------------|
| Collections become vague duplicates of topic notes | The new layer adds little value | Require an initiative question, scope note, visible inclusion reasons, and related-view links so the artifact is clearly for live work |
| Metadata dominates weak evidence | Operators may over-trust the collection | Use metadata only for prioritization within evidence-backed candidates |
| Operator curation scope grows too large | The sprint turns into manual KM | Limit manual input to a small initiative-definition list only |
| Collections sprawl into exhaustive dumps | Notes become unreadable and unhelpful | Keep `max_items` bounded and prefer selective evidence |
| Weekly-brief presence becomes a hidden dependency | Sparse periods would make collections look empty or broken | Treat weekly mentions as a tie-breaker, not a required source of membership |
| Collection generation leaks into other commands | Existing stage boundaries erode | Ship collections as an explicit dedicated step only |

### Decisions Locked For Sprint 9

| Decision | Rationale |
|----------|-----------|
| Collection notes are tied to active initiatives, not broad evergreen themes | Keeps Sprint 9 aligned to live strategic work rather than duplicating topic indexes |
| The only manual curation layer is a bounded initiative-definition list stored at `playbooks/curated-collections.yaml` | Preserves inspectability without creating a maintenance-heavy system |
| Collections live at `vault/collections/<initiative-slug>.md` | Gives the new layer a stable, discoverable rerun-safe path |
| Every collection entry must link to both the bookmark note and the original X post | Preserves trust and source traceability |
| Every surfaced item must also show a visible inclusion reason | Keeps initiative mapping inspectable and prevents opaque ranking behavior |
| Topic notes, weekly briefs, and validated metadata can inform collection selection, but collection notes remain evidence-first | Prevents weak abstractions from outranking source material |
| Weekly-brief presence is a prioritization hint, not a hard membership requirement | Keeps collections useful even in quieter periods |
| Collection generation stays a dedicated explicit command | Preserves stage boundaries and reduces regression risk |

---

### Sprint 9 Closeout Notes

- Automated verification passed with `PYTHONPATH=src .venv/bin/python -m compileall src` and `PYTHONPATH=src .venv/bin/python -m pytest`
- The dedicated `collections` command shipped separately from `export`, `topics`, `metadata`, and `synthesize`
- `playbooks/curated-collections.yaml` is now the checked-in manual curation layer for the shipped collection slice
- Sprint 9 review findings R001-R004 remain open in `code-reviews/sprint-9-curated-collections-review.md`
- Human usefulness confirmation for curated collections remains a post-roadmap follow-up rather than a blocker on the Level 2 roadmap closeout

## Sprint 10 — Universal Source Ingestion

**Status:** COMPLETE  
**Goal:** Extend the shipped X baseline into a small, bounded source-intake layer that also supports explicit URL, Safari bookmark folder/export, and deep-research artifact imports while preserving existing export, topic, synthesis, and metadata contracts.

Sprint 10 is now the shipped mixed-source intake baseline, with Sprint 9 still serving as the verified leadership-layer closeout underneath it.

This sprint is the first post-roadmap expansion and should unlock your stated use cases:
- import any URL directly,
- import Safari folder/export artifacts,
- import deep-research outputs (Markdown, JSON, CSV, JSONL).

### In Scope

- Add a bounded source adapter interface in `extractor.py` for three new entrypoints:
  - `import-url`
  - `import-safari-folder`
  - `import-research`
- Keep raw provenance immutable and source-agnostic:
  - store adapter-specific raw input under `data/raw/` before any SQLite mutation,
  - preserve unknown fields in a `raw_payload`-style envelope,
  - include `source_name`, `source_type`, `source_item_id`, `source_ref` on canonical rows.
- Keep downstream `enrich`, `export`, `topics`, `synthesize`, `metadata`, and `collections` unchanged in behavior.
- Add deterministic dedupe and idempotent reruns for non-X sources.
- Add explicit import-focused failures with clear operator messages:
  - bad source input,
  - parse/shape issues by format,
  - missing required source-identity fields,
  - quarantine path for unrecoverable records.

### Out of Scope

- Unbounded connector framework for arbitrary APIs.
- Automatic deep browsing or full-page enrichment inside import commands.
- Redesigning derived leadership stages.
- Any source-authored prompt changes.

### Entry Criteria

- Sprint 9 is complete.
- `architecture.md` and `product-definition.md` already describe source-agnostic intake and adapter boundaries.
- Local SQLite schema compatibility for `source_name`, `source_type`, `source_item_id`, `source_ref` is confirmed or explicitly migrated.
- Real local corpus exists in `state/app.db` for cross-layer regression checks.

### Acceptance Contract

#### Shared identity rules

- Every normalized row must resolve to exactly one stable source identity.
- Identity fields for acceptance are: `tweet_id` (legacy X-only), `source_name`, `source_type`, `source_item_id`, `source_ref`, and derived downstream `canonical_item_id` semantics.
- Existing X rows keep `tweet_id` as the legacy identifier and additionally map to `source_name=x`, `source_type=x_bookmark`, `source_item_id=<tweet_id>`.
- Non-X rows may leave `tweet_id` null, but they must provide `source_name`, `source_type`, `source_item_id`, and `source_ref` together.
- Downstream compatibility key: `canonical_item_id = tweet_id` for X rows, otherwise `<source_name>:<source_type>:<source_item_id>`.
- `source_ref` is provenance for humans and note rendering; it is not a substitute for `source_item_id` during dedupe.
- Identity derivation must be deterministic from raw input alone and must not depend on enrichment, export, or any derived-stage rewrite.

#### Adapter-specific acceptance rules

| Command | Accepted input unit | Required canonical identity fields | Acceptance notes |
|---------|---------------------|------------------------------------|------------------|
| `import-url` | One explicit URL per CLI argument or input record | `source_name=manual`, `source_type=import_url`, `source_item_id` derived deterministically from the canonicalized absolute URL, `source_ref` set to that canonical URL | Re-importing the same canonical URL must map to the same canonical row even if the operator supplied a differently formatted equivalent URL |
| `import-safari-folder` | One Safari bookmark item from the provided export/folder artifact | `source_name=safari`, `source_type=bookmark_export`, `source_item_id` derived deterministically from folder lineage plus canonicalized bookmark URL, `source_ref` set to the canonical URL | Raw provenance must retain the export path and folder lineage so the bookmark can be traced back even when the canonical row dedupes cleanly |
| `import-research` | One accepted record inside a Markdown/JSON/JSONL/CSV research artifact | `source_name=research`, `source_type=artifact_item`, `source_item_id` derived deterministically from artifact identity plus per-record locator, `source_ref` set to artifact path and/or embedded source URL when available | The same artifact rerun must yield the same record identities; sibling records in one artifact must not collide |

Adapter-specific identity constraints:
- `import-url`: formatting-only URL differences must canonicalize to the same identity.
- `import-safari-folder`: the same URL in different Safari folder lineages may remain distinct when lineage differs; lineage is part of the identity contract.
- `import-research`: artifact identity plus locator is mandatory so sibling records in one imported artifact cannot collide.

#### Quarantine acceptance rules

- Raw import artifacts are always written before normalization or quarantine decisions.
- Whole-input failure stops before SQLite mutation only when the input cannot be opened or parsed at all.
- Per-record failures after raw capture are quarantined, not guessed:
  - missing canonical URL,
  - missing folder lineage for Safari identity derivation,
  - unreadable research row or unsupported row shape,
  - unstable or duplicate source identity within the same import artifact.
- Quarantine output must preserve: adapter name, raw artifact path, rejection reason, and record locator/provenance such as URL, folder path, file path, line number, or row number.
- Quarantine is evidence, not a placeholder-row mechanism: rejected records stay inspectable but must not create guessed canonical rows.
- Valid sibling records still normalize and insert; quarantine is non-blocking for the rest of the artifact.

#### Backward-compatibility acceptance rules

- Existing `extract` + `enrich` + `export` behavior for X bookmarks stays unchanged, including current `tweet_id`-based note paths and X backlinks.
- `export`, `topics`, `metadata`, `synthesize`, and `collections` must consume mixed-source rows through shared canonical-row fields plus `canonical_item_id` semantics, not through command-specific branches.
- Non-X rows must export as normal source notes with stable local links, but X-only fields such as status URLs remain conditional on X provenance.
- Mixed-source imports must not require any derived stage to know whether a row came from `import-url`, `import-safari-folder`, or `import-research`.
- Any downstream code that still reads `tweet_id` must continue to work for X rows while gaining non-X support through shared `canonical_item_id` handling rather than by changing X note-path behavior.

### Required Outputs

| Output | Contract |
|--------|----------|
| Raw records | One raw import artifact per invocation per adapter is written before normalization |
| Canonical rows | `bookmarks` stores source-identity fields and retains `tweet_id` compatibility for existing X rows |
| Adapter CLI | `import-url`, `import-safari-folder`, and `import-research` are runnable independently from `extract` |
| Quarantine visibility | Rejected records are preserved with explicit reasons and raw-provenance links instead of being silently skipped |
| Backward compatibility | Existing `extract` + `enrich` + `export` flows remain stable for X bookmarks and mixed-source rows keep downstream stages source-agnostic |
| Idempotence | Repeating the same import yields no duplicates at the canonical identity level |
| Visibility | `sprint-plan.md`, `context.md`, `architecture.md`, and `project-plan.md` keep the shipped Sprint 10 intake contract explicit |

### Task Board

| ID | Workstream | Task | Priority | Status | Depends On | Verification |
|----|------------|------|----------|--------|------------|--------------|
| 10.1 | Foundation | Finalize the source-identity contract used by normalizer and DB keys (`tweet_id`, `source_name`, `source_type`, `source_item_id`, `source_ref`) plus `canonical_item_id` compatibility semantics | P0 | ✅ Done | Sprint 9 complete | DB schema and normalizer tests accept X rows, non-X identity forms, and shared downstream row-key resolution |
| 10.2 | Adapter dispatch | Add shared intake adapter dispatch for URL, Safari, and research imports in the CLI/extractor layer, including immutable raw snapshot writing before normalization | P0 | ✅ Done | 10.1 | Running any new import command writes one adapter-specific raw snapshot and routes through one shared dispatch path |
| 10.3 | Parser → normalizer mapping | Implement `import-url` parser and normalizer path with deterministic URL/source-item-id generation | P0 | ✅ Done | 10.2 | Re-imported same canonical URLs are deduplicated and formatting-only URL differences do not fork identities |
| 10.4 | Parser → normalizer mapping | Implement `import-safari-folder` input parser(s) for common Safari bookmark export formats with folder-lineage identity derivation | P0 | ✅ Done | 10.2 | Folder lineage plus canonical URL become stable provenance and identity inputs; malformed items quarantine cleanly |
| 10.5 | Parser → normalizer mapping | Implement `import-research` parser for Markdown, JSON, JSONL, and CSV research artifacts | P0 | ✅ Done | 10.2 | Imported research rows render and export like source notes and preserve artifact-local locators |
| 10.6 | Idempotence strategy | Lock adapter-level dedupe behavior, rerun semantics, and mixed-source downstream row-key compatibility | P0 | ✅ Done | 10.1, 10.3, 10.4, 10.5 | Re-running the same adapter input yields no duplicate canonical rows or note-path drift |
| 10.7 | Quarantine path | Implement adapter-specific quarantine path plus import-level validation errors | P1 | ✅ Done | 10.3, 10.4, 10.5 | Known malformed inputs do not corrupt normalized rows and are surfaced as quarantined records with raw-provenance details |
| 10.8 | Verification | Add adapter test coverage for parser shape, dedupe semantics, quarantine behavior, and idempotent reruns | P1 | ✅ Done | 10.6, 10.7 | `pytest` includes fixture-driven tests for each adapter, quarantine cases, and rerun behavior |
| 10.9 | Handoff updates | Add CLI smoke and end-to-end command script in handoff docs and operator docs once verification is stable | P1 | ✅ Done | 10.8 | `python -m leeknowledge import-url`, `import-safari-folder`, and `import-research` are documented in a real local flow with follow-on pipeline checks |

### Implementation Sequence And Dependencies

#### 1. Adapter dispatch baseline

Start by making the shared intake path explicit before any adapter-specific parsing:
- lock the one shared raw-capture contract,
- route `import-url`, `import-safari-folder`, and `import-research` through the same dispatch boundary,
- keep raw snapshot write-before-normalize behavior identical across adapters.

**Depends on:** 10.1  
**Enables:** 10.3, 10.4, 10.5

#### 2. Parser → normalizer mapping

Implement adapter mappings in the order of lowest ambiguity to highest ambiguity:
1. `import-url` — smallest shape surface, best first proof of canonical URL identity.
2. `import-safari-folder` — adds folder-lineage provenance and export-shape parsing.
3. `import-research` — last because it has the widest format and locator surface.

Each adapter must produce the same minimum canonical identity tuple and hand unknown fields forward in raw/quarantine payloads instead of inventing repairs.

**Depends on:** 10.2  
**Enables:** 10.6, 10.7

#### 3. Idempotence strategy

After all three parser paths can normalize records, lock rerun behavior before broad regression work:
- prove identity derivation is stable per adapter,
- prove equivalent URL formatting does not fork `import-url` rows,
- prove Safari lineage + canonical URL yields stable Safari identities,
- prove research artifact identity + locator yields stable per-record research identities,
- verify downstream note generation uses shared canonical-item semantics rather than adapter-specific branches.

**Depends on:** 10.1, 10.3, 10.4, 10.5  
**Enables:** 10.8

#### 4. Quarantine path

Add quarantine only after parser outputs are concrete enough to classify failures accurately:
- whole-input read/parse failure stops before SQLite mutation,
- per-record failure after raw capture writes quarantine output with adapter, raw artifact path, reason, and record locator,
- valid sibling rows still insert.

This should be implemented after the parser contracts exist, but before final verification, so tests can lock the rejection reasons and provenance shape.

**Depends on:** 10.3, 10.4, 10.5  
**Enables:** 10.8

#### 5. Verification

Run verification only after idempotence and quarantine behavior are both explicit:
- adapter fixture tests,
- rerun/idempotence checks,
- quarantine regression cases,
- mixed-source `enrich → export → topics → metadata → synthesize → collections` checks.

**Depends on:** 10.6, 10.7  
**Enables:** 10.9

#### 6. Handoff updates

Update governed handoff docs last, after command behavior and verification commands are stable:
- keep `sprint-plan.md` aligned to what shipped,
- keep `context.md`, `architecture.md`, and `project-plan.md` aligned to the shipped intake contract,
- capture the real verification flow in `result-review.md` during the later documentation/closeout steps.

**Depends on:** 10.8

### Suggested Execution Order

1. 10.1 source-identity contract and schema compatibility.
2. 10.2 adapter dispatch and shared raw-capture path.
3. 10.3 `import-url` implementation as the first parser-normalizer proof.
4. 10.4 `import-safari-folder` implementation after URL identity is stable.
5. 10.5 `import-research` implementation after Safari lineage rules are clear.
6. 10.6 idempotence and downstream canonical-item checks across all adapters.
7. 10.7 quarantine and operator-visible failure paths.
8. 10.8 fixture, rerun, quarantine, and mixed-source regression verification.
9. 10.9 handoff and operator-doc updates once the verification script is final.

### Verification Script (Sprint 10)

```bash
PYTHONPATH=src .venv/bin/python -m pytest
PYTHONPATH=src .venv/bin/python -m leeknowledge import-url https://example.com/insight
PYTHONPATH=src .venv/bin/python -m leeknowledge import-safari-folder --input "$HOME/Library/Safari/Bookmarks.plist"
PYTHONPATH=src .venv/bin/python -m leeknowledge import-research ./research/research-sample.md
PYTHONPATH=src .venv/bin/python -m leeknowledge enrich
PYTHONPATH=src .venv/bin/python -m leeknowledge export
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
PYTHONPATH=src .venv/bin/python -m leeknowledge metadata
PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period 2026-W15
PYTHONPATH=src .venv/bin/python -m leeknowledge collections
PYTHONPATH=src .venv/bin/python -m pytest tests/test_db.py tests/test_import*.py tests/test_topics.py tests/test_export.py
```

Replace fixture paths with local test artifacts and verify that imported rows appear in `vault/` without disrupting non-import workflows.

### Risks To Manage

| Risk | Impact | Mitigation |
|------|--------|------------|
| Non-X record identity is unstable across reruns | Duplicate rows or accidental collisions | Define canonical `source_item_id` format per adapter and test it |
| Safari/research formats drift | Parser breaks on common exports | Keep adapters bounded, add fixture coverage, and preserve unknown fields in raw payload |
| Operator confusion between imported and native X records | Trust and traceability issues | Include `source_name`, `source_type`, `source_ref` in source note frontmatter and backlinks |
| Existing derived commands regress on partial metadata | Downstream trust regression | Keep derived-command interfaces read-only and verify existing commands still pass |

### Exit Checklist

- [x] Source identity contract is explicitly defined and migration-safe
- [x] `import-url`, `import-safari-folder`, and `import-research` each have a documented acceptance rule for `source_name`, `source_type`, `source_item_id`, and `source_ref`
- [x] Quarantine behavior is explicit for whole-input failures and per-record failures after raw capture
- [x] Three import commands are runnable with fixture-backed validation
- [x] Raw ingest artifacts are immutable and inspectable
- [x] Import paths are idempotent and produce stable canonical rows
- [x] `PYTHONPATH=src .venv/bin/python -m pytest` includes adapter coverage
- [x] Derived pipeline (`export`, `topics`, `metadata`, `synthesize`, `collections`) remains stable after mixed-source imports

## Ready Queue

These are not active sprint commitments yet, but they are the next likely
delivery slices after Sprint 10. There is intentionally no active Sprint 11
commitment until the next layer is chosen against the completed Sprint 10
contract above.

1. Triage and sequence the Sprint 7-9 review findings into a focused hardening sprint now that Sprint 10 is closed.
2. Decide whether the next expansion should add sharing/publishing workflows after the shipped multi-source intake baseline.
3. Revisit monthly synthesis only after weekly briefs, metadata, curated collections, and source intake prove useful in real use.

---

## Definition Of Done For Any Sprint

A sprint is only done when:

1. The promised slice works end-to-end at the level claimed in the sprint goal.
2. Verification has been run, not assumed.
3. Failure cases are handled clearly enough that Lee would not be surprised.
4. `sprint-plan.md`, `context.md`, and other handoff docs reflect reality.

---

*Update this file whenever sprint scope, status, sequencing, or exit criteria change.*
