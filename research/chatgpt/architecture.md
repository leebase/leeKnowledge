# architecture.md

## Architectural overview

The system is a **local-first, replayable ingestion and knowledge-generation pipeline** with one hard rule:

> **Extraction is unstable. Everything downstream must be stable.**

The architecture therefore separates the system into two zones:

1. **Unstable extraction zone**  
   Browser exporters, userscripts, Playwright sessions, and any future X API adapter.

2. **Stable knowledge zone**  
   Raw run store, canonical normalization, enrichment, artifact rendering, indexing, and retrieval.

The stable zone only consumes a versioned raw bundle contract. It never depends on DOM selectors, GraphQL operation names, or third-party exporter internals.

## Design principles

1. **Raw before smart**  
   Persist source data before parsing, dedupe, enrichment, or note generation.

2. **Import-first, automate later**  
   MVP begins with reliable import of user-generated local exports. First-party browser automation is an optional adapter, not a prerequisite.

3. **Observation-based ingestion**  
   Treat each sync as a set of bookmark observations, not as a destructive overwrite of “the current truth.”

4. **Local-first by default**  
   Laptop-compatible storage, indexing, and operation.

5. **AI enriches, never validates extraction**  
   Extraction correctness is determined by contracts, tests, and audits, not by LLM guesses.

6. **Every stage replayable**  
   Re-run normalization, enrichment, or rendering from raw bundles without re-extracting.

7. **Replaceable adapters**  
   New extractors, renderers, or LLM providers plug in behind stable interfaces.

## System context

### External systems
- X web application
- Optional X API
- Optional LLM provider or local model runtime
- Optional external web pages for URL expansion and metadata capture

### Local system components
- CLI orchestrator
- Extraction adapters
- Raw run store
- Canonical data store
- Artifact renderer
- Retrieval index
- Vault output directory

## Major components

### 1. CLI orchestrator
A Python CLI drives all workflows:
- `import-run`
- `normalize`
- `render`
- `enrich`
- `index`
- `sync`
- `replay`
- `audit`

Recommended stack:
- Python 3.12+
- Typer for CLI
- Pydantic for schemas
- SQLAlchemy or SQLModel for persistence
- Jinja2 or equivalent templating for Markdown output

### 2. Extraction adapters
A pluggable adapter layer that emits raw run bundles.

Supported adapters by architecture:

#### A. `export-import` adapter (**recommended MVP**)
Ingests JSON/CSV/HTML exports produced by browser-local tools.

Why this is the default:
- lowest implementation risk,
- lowest operational complexity,
- easiest to validate,
- easiest to keep local,
- no direct dependency on X API pricing,
- no mandatory headless automation.

Representative current tools demonstrate this pattern today, including `twitter-web-exporter` and `smaug`.

#### B. `playwright-session` adapter (**post-MVP, experimental**)
Uses a persistent logged-in browser profile and optionally network interception to extract bookmark data from the web app.

Use only after the raw bundle contract is stable. This adapter exists for convenience, not because the rest of the system requires it.

#### C. `x-api` adapter (**post-MVP, optional**)
Uses authenticated bookmark endpoints and folder endpoints where the user chooses to pay for API access. X’s public docs confirm bookmark lookup, folder lookup, bookmark-specific OAuth scopes, and current rate limits. X’s public pricing docs now describe pay-per-use billing rather than a single public fixed-plan assumption.

### 3. Raw run store
Immutable filesystem-based store for extraction outputs.

Recommended layout:

```text
data/
  raw/
    2026-04-07T22-14-03Z_export-import/
      manifest.json
      source-metadata.json
      items.ndjson
      attachments/
      logs/
  replay/
  cache/
vault/
  bookmarks/
  topics/
  syntheses/
state/
  app.db
```

`manifest.json` contains:
- `run_id`
- `adapter_type`
- `adapter_version`
- `captured_at`
- `source_format`
- `input_files`
- `item_count`
- `warnings`
- `hashes`

### 4. Canonical normalizer
Transforms raw items into stable domain records:

- `Bookmark`
- `BookmarkObservation`
- `Author`
- `Folder`
- `UrlReference`
- `MediaReference`
- `Enrichment`
- `Artifact`

The normalizer performs:
- schema validation,
- ID extraction,
- author normalization,
- URL parsing,
- quote/reply/thread hint extraction,
- folder mapping,
- duplicate detection,
- incomplete-record quarantine.

### 5. Enrichment pipeline
Runs after normalization.

Tasks:
- concise summary,
- tag generation,
- named-entity extraction,
- topic classification,
- backlink suggestions,
- optional weekly or topical synthesis.

All enrichment outputs are:
- optional,
- versioned,
- reproducible from raw/canonical inputs,
- stored separately from source truth.

### 6. Artifact renderer
Produces durable outputs:
- per-bookmark Markdown notes,
- per-thread Markdown notes,
- topic pages,
- run reports,
- audit reports.

### 7. Local retrieval layer
MVP retrieval:
- SQLite metadata tables
- SQLite FTS5 full-text index

Post-MVP retrieval:
- local embedding store (recommended: LanceDB or equivalent)
- hybrid lexical + semantic search
- optional local FastAPI query service

### 8. Observability and audit layer
Tracks:
- extraction run metadata,
- per-stage durations,
- duplicate counts,
- unresolved thread counts,
- invalid raw items,
- enrichment failures,
- render diffs,
- completeness audits.

## Data flow / pipeline stages

### Stage 0: Trigger
Manual command, scheduled task, or drag-and-drop import.

### Stage 1: Extract or import
The adapter produces a raw run bundle.

### Stage 2: Persist raw bundle
Write bundle to immutable storage before any transformations.

### Stage 3: Normalize
Map raw items into canonical entities and observations.

### Stage 4: Merge and dedupe
Update the local catalog with first-seen/last-seen observations.

### Stage 5: Enrich
Run optional URL expansion, metadata extraction, and LLM enrichment.

### Stage 6: Render
Generate Markdown notes and topic artifacts.

### Stage 7: Index
Update SQLite FTS and any optional vector index.

### Stage 8: Audit
Produce a sync report with duplicates, unresolved items, and completeness metrics.

## Extraction architecture

## Why extraction is isolated

Extraction is the only layer tied directly to:
- X UI changes,
- GraphQL shape changes,
- exporter breakage,
- session handling,
- policy risk.

X’s own automation guidance explicitly warns against non-API website scripting, while open-source exporters show that browser-local extraction is still practically workable today. The architecture must therefore support browser extraction without letting browser fragility leak into the rest of the system.

## Adapter contract

Each extractor must emit the same contract:

### `ExtractionRunBundle`
- `run_id`
- `adapter_type`
- `adapter_version`
- `captured_at`
- `source_account_handle`
- `source_format_version`
- `items[]`
- `attachments[]`
- `warnings[]`
- `stats`

### `RawBookmarkEnvelope`
- `source_post_id` or best available stable key
- `raw_payload`
- `capture_position`
- `folder_refs`
- `capture_context`
- `raw_hash`

This contract prevents downstream code from knowing whether the data came from:
- a userscript export,
- a Chrome extension export,
- Playwright network interception,
- or the official API.

## Recommended extraction modes

### Mode 1: User-driven export/import
This is the recommended default for MVP.

Operational pattern:
1. User runs a supported exporter in their normal logged-in browser.
2. User saves export locally.
3. `bookmark-vault import-run <file>` ingests it.
4. The system writes an immutable raw bundle and continues from there.

Benefits:
- simplest implementation,
- strongest observability,
- low risk of hidden browser-automation bugs,
- easy to test with fixtures.

### Mode 2: Convenience sync with Playwright
Post-MVP only.

Operational pattern:
1. Start headed browser with persistent local profile.
2. Navigate to bookmarks page or folder page.
3. Intercept rendered network responses or page data.
4. Stop incremental fetch when a configurable threshold of already-known posts has been observed.
5. Save raw bundle.

Guardrails:
- never required for core correctness,
- run locally only,
- no proxy rotation,
- conservative pacing,
- user-controlled scheduling.

### Mode 3: Optional API sync
Post-MVP only.

Operational pattern:
1. Authenticate with OAuth.
2. Read bookmarks and folders via official endpoints.
3. Convert API response into the same raw bundle contract.
4. Let the rest of the pipeline behave identically.

Use case:
- user explicitly wants the policy-safer path for increments,
- user is willing to accept cost/credit usage and whatever completeness the API practically yields.

## Incremental sync strategy

The system must not depend on a guaranteed `bookmarked_at` timestamp.

Recommended strategy:
- maintain `BookmarkObservation` rows per run,
- store local `first_seen_at` and `last_seen_at`,
- store `capture_position` for each run,
- on incremental browser syncs, stop after `N` consecutive already-known post IDs,
- run periodic full or deeper integrity sweeps to catch ordering anomalies.

This makes incremental sync practical even when the source only gives reverse-chronological bookmark order and post IDs.

## Processing and enrichment architecture

### Canonical schema

Recommended operational tables:

#### `sync_runs`
- `run_id`
- `adapter_type`
- `adapter_version`
- `started_at`
- `completed_at`
- `status`
- `item_count`
- `warning_count`
- `error_count`

#### `raw_items`
- `raw_item_id`
- `run_id`
- `source_post_id`
- `raw_hash`
- `capture_position`
- `raw_json`
- `quarantined`

#### `bookmarks`
- `post_id`
- `canonical_url`
- `text`
- `created_at`
- `author_id`
- `conversation_id`
- `quote_post_id`
- `reply_to_post_id`
- `source_status`

#### `bookmark_observations`
- `observation_id`
- `post_id`
- `run_id`
- `first_seen_at`
- `last_seen_at`
- `capture_position`
- `folder_id`
- `source_bookmarked_at` nullable

#### `authors`
- `author_id`
- `username`
- `display_name`
- `profile_url`

#### `folders`
- `folder_id`
- `folder_name`
- `source`

#### `urls`
- `url_id`
- `post_id`
- `original_url`
- `expanded_url`
- `title`
- `description`
- `fetch_status`

#### `enrichments`
- `enrichment_id`
- `post_id`
- `kind`
- `provider`
- `model`
- `prompt_version`
- `output_json`
- `created_at`

#### `artifacts`
- `artifact_id`
- `post_id`
- `artifact_kind`
- `path`
- `content_hash`
- `renderer_version`

### URL expansion and linked-content capture

MVP:
- resolve short URLs,
- capture final URL, title, and description,
- store fetch status and timestamps.

Post-MVP:
- article extraction with per-domain allowlist,
- cached raw article HTML or cleaned text,
- PDF or media-specific extractors.

### Thread reconstruction

MVP thread policy:
- best effort only,
- prefer using already captured context,
- do not spider the full social graph,
- if parent or quoted posts are unavailable, render partial context explicitly.

This preserves fidelity without making the system depend on expansive extra fetching.

## Storage architecture

### Primary storage
- Filesystem for raw bundles and Markdown artifacts
- SQLite for operational metadata and FTS

### Why SQLite
- trivial local deployment,
- easy backups,
- strong enough for personal scale,
- works well with replayable batch workflows,
- can later be migrated or mirrored into Postgres.

### File outputs
- `/vault/bookmarks/YYYY/MM/<slug>-<post_id>.md`
- `/vault/topics/<topic>.md`
- `/vault/syntheses/YYYY-WW.md`

### Artifact format
Each note contains:
- YAML frontmatter
- short summary
- original post text
- author metadata
- original X URL
- expanded URLs
- thread/quote references
- extraction/enrichment provenance

## Retrieval/query architecture

### MVP
- text search through SQLite FTS5,
- filters on author, folder, date range, tags, linked domain,
- “open note” workflow in Obsidian-compatible vault.

### Post-MVP
- embed normalized text plus summary,
- store embeddings locally,
- hybrid retrieval:
  - lexical recall from FTS,
  - semantic rerank from vector search.

### Query surfaces
- CLI search
- optional local web UI
- optional “answer over notes” command that cites local notes, not raw LLM memory

## AI/LLM integration points

AI is allowed in four places only:

1. **Post summary**
2. **Tags and entities**
3. **Topic-page generation**
4. **Periodic synthesis notes**

AI is explicitly not responsible for:
- extracting post IDs,
- determining dedupe keys,
- validating completeness,
- deciding whether a bookmark exists,
- storing source truth.

### LLM design rules
- provider abstraction (`ollama`, `anthropic`, `openai-compatible`)
- prompt versioning
- structured JSON outputs
- stored outputs per version
- manual re-run on model upgrades

## Failure handling and observability

### Failure-handling strategy
- raw persistence is atomic per run,
- normalization writes invalid records to quarantine,
- enrichment failures do not block rendering of source notes,
- rendering failures do not delete prior successful artifacts,
- index rebuild is always replayable.

### Metrics to record
- posts discovered
- duplicates detected
- notes rendered
- unresolved URLs
- unresolved thread references
- enrichment success rate
- export completeness estimate
- run duration

### Completeness audit
After each extraction run:
- compare imported count against source run stats,
- inspect first and last few items,
- sample random bookmarks,
- report changes from previous run.

## Security and secrets handling

### Default policy
- local execution only,
- no secrets in repo,
- `.env` and profile data gitignored,
- OS keychain or encrypted file for credentials where used.

### Browser-session rules
- persistent profile stored locally only,
- no remote headless browser service in MVP,
- no cookie sharing between machines by default,
- explicit “purge session” command.

### Data sensitivity
Bookmark exports may contain private or deleted content snapshots. Treat raw bundles and vault outputs as personal archives.

## Operational concerns

### Scheduling
- manual by default,
- optional cron / launchd / Task Scheduler weekly sync,
- optional monthly integrity sweep.

### Backups
- raw bundle directory,
- SQLite database,
- vault directory.

### Upgrade strategy
- version extraction adapters,
- version canonical schemas,
- version artifact templates,
- provide migration commands.

## Extension points / replaceable components

1. Extraction adapters
2. URL fetchers
3. LLM providers
4. Artifact renderers
5. Retrieval backends
6. UI layer

## Recommended implementation stack

### Core
- Python
- Playwright (Python) for optional direct browser adapter
- SQLite + FTS5
- Jinja2
- Pydantic

### Optional
- Trafilatura or readability-style extractor for linked articles
- LanceDB for local vectors
- FastAPI for a local query UI/API

## Explicit architecture decisions

1. **Do not start with AWS, Lambda, SQS, Pinecone, or a hosted Next.js app.**  
   That is the wrong complexity level for a personal-scale system.

2. **Do not make Playwright the only ingestion path.**  
   Playwright is an adapter, not the product core.

3. **Do not make the official X API a hard dependency for MVP.**  
   Support it later behind the same raw contract.

4. **Do make raw capture immutable and replayable.**

5. **Do make Markdown the primary user-visible artifact and SQLite the primary operational index.**