# Architecture: leeKnowledge

## Architectural Overview

leeKnowledge is a **local-first, replayable pipeline** with four stages:

```
Extract → Normalize → Enrich → Export
```

The stages are decoupled by SQLite. Each stage can be run independently and is idempotent. The one hard rule:

> **Extraction is unstable. Everything downstream must be stable.**

The extractor is a replaceable module. If X changes its DOM or GraphQL schema tomorrow, only the extractor changes. Normalization, enrichment, and export never know or care how the data arrived.

---

## Design Principles

1. **Raw before smart** — Persist source JSON before parsing, deduplicating, or enriching.
2. **Simple that works** — No adapter abstractions, no run manifests, no observation models. One extractor, one database, one template.
3. **Replayable stages** — Re-enrich or re-export from SQLite without re-extracting from X.
4. **LLM enriches, never validates** — Extraction correctness comes from tweet IDs and structured data, not AI guesses.
5. **Local-first** — Everything runs on a laptop. No cloud services required.
6. **Dedup downstream** — At 200 bookmarks, re-extract everything each run and let SQLite dedup by tweet ID. Simpler than incremental extraction.

---

## System Context

```
┌──────────────────────────────────────────────────────────┐
│                      macOS Laptop                        │
│                                                          │
│  ┌───────────┐    ┌────────────────────────────────┐     │
│  │  Chrome    │    │       leeKnowledge CLI         │     │
│  │ (profile)  │───▶│  extract / enrich / export /   │     │
│  └───────────┘    │  sync                          │     │
│                   └──────────┬─────────────────────┘     │
│                              │                           │
│            ┌─────────────────▼──────────────────┐        │
│            │         SQLite Database             │        │
│            │  bookmarks | enrichments | urls     │        │
│            └─────────────────┬──────────────────┘        │
│                              │                           │
│            ┌─────────────────▼──────────────────┐        │
│            │       Vault (Markdown files)        │        │
│            │  vault/2025/03/slug-tweetid.md      │        │
│            └────────────────────────────────────┘        │
│                                                          │
│            ┌────────────────────────────────────┐        │
│            │  data/raw/bookmarks_2026-04-07.json │        │
│            │  (immutable extraction archive)     │        │
│            └────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
   x.com/i/bookmarks            pi CLI (openai-codex)
   (Playwright session)         via lee-llm-router
```

---

## Major Components

### 1. CLI (`src/leeknowledge/cli.py`)

Python CLI using Typer. Current command state:

| Command | What it does |
|---------|-------------|
| `extract` | Completed Sprint 2 extraction slice: capture raw bookmark payloads, write the archive, normalize, and insert SQLite rows |
| `enrich` | Completed Sprint 3 enrichment slice: URL expansion, optional page metadata fetch, structured enrichment, and rerun-safe storage |
| `export` | Completed Sprint 4 command: render Markdown vault notes from SQLite |
| `sync` | Completed Sprint 4 command: run extract → enrich → export in sequence |

All four pipeline commands now exist end-to-end. Sprint 5 hardened the export path so it validates SQLite read-only instead of bootstrapping missing state, and so Markdown-sensitive content is rendered in a source-faithful way.

### 2. Extractor (`src/leeknowledge/extractor.py`)

Playwright script that owns browser access and raw capture only.

**Runtime flow**
1. Resolve the Chrome user data directory from `--chrome-profile-dir` or `LEEKNOWLEDGE_CHROME_PROFILE_DIR`; if neither is supplied, fall back to the standard macOS Chrome profile path and fail fast if it does not exist.
2. Launch Chrome with that existing profile and the standard viewport (`1280x800`). Headless mode is opt-in via `--headless` / `LEEKNOWLEDGE_HEADLESS`.
3. Navigate to `https://x.com/i/bookmarks` and abort immediately if X redirects to a login flow or the page title still looks like a sign-in screen.
4. Register a GraphQL response interceptor before scrolling begins and retain only bookmark-shaped payloads.
5. Scroll with randomized 1.5-3.0 second delays until no new payloads are seen for five consecutive polls or 100 attempts are reached.
6. Persist the immutable raw archive to `data/raw/bookmarks_YYYY-MM-DD.json` before any SQLite mutation. If that date's file already exists, create a timestamp-suffixed sibling instead of overwriting.
7. Normalize the archived payloads and insert canonical bookmark rows into SQLite with `INSERT OR IGNORE`.

**Operator configuration**
- `LEEKNOWLEDGE_RAW_DIR` overrides the raw archive directory.
- `LEEKNOWLEDGE_DB_PATH` overrides the SQLite path.
- `LEEKNOWLEDGE_CHROME_PROFILE_DIR` points at the Chrome user data directory or profile path; `LEEKNOWLEDGE_CHROME_USER_DATA_DIR` is accepted as a legacy alias.
- `LEEKNOWLEDGE_HEADLESS` toggles headless Chrome runs.
- The `extract` command leaves SQLite untouched until after the raw archive is persisted and normalization succeeds; an empty capture writes the archive and stops before any database file is created.

**Extractor boundary:**
- Allowed: browser launch, auth detection, response capture, raw archive persistence, and retry/stop decisions.
- Not allowed: canonical field mapping, deduplication, SQLite writes, URL expansion, page-metadata fetches, or enrichment.
- Unknown source fields must be preserved in raw form rather than discarded.

**Fallback sequencing:**
1. If Chrome does not reach an authenticated bookmarks page, stop immediately with a readable error.
2. If GraphQL capture yields no bookmark payloads, write the raw archive and then stop before SQLite inserts; the database is not created on this path.
3. If the raw archive cannot be written, stop before normalization.
4. If normalization encounters a bad record, quarantine or skip it explicitly rather than guessing.
5. DOM fallback is deferred to a later hardening pass and must use the same raw archive contract if it is ever introduced.

**Anti-detection:**
- Random scroll delays: `random.uniform(1.5, 3.0)` seconds.
- Standard viewport: 1280x800.
- No proxy rotation (single personal account, low frequency).
- Run at most weekly.

### 3. Normalizer (`src/leeknowledge/normalizer.py`)

Transforms raw captured archives into canonical SQLite records:
- Reads only the archived raw capture format produced by the extractor.
- Extracts the canonical bookmark fields required by the current schema: `tweet_id`, `text`, `author_username`, `author_display_name`, `created_at`, `conversation_id`, `in_reply_to_id`, `media_urls`, `raw_urls`, and `first_seen_at`.
- Treats `tweet_id` as the only identity key and uses `INSERT OR IGNORE` for reruns.
- Skips or quarantines records that do not have a stable `tweet_id` or cannot satisfy the required SQLite shape; the extractor is never asked to repair them.
- Defers URL expansion and page-metadata fetch to later pipeline stages; normalization stays deterministic and replayable.

**Normalization rules:**
- Normalization is deterministic and must not depend on browser state or LLM output.
- Source payloads remain the provenance record; canonical rows are derived, not authoritative.
- Missing optional fields are allowed if the canonical SQLite schema can represent them.
- Missing required fields must fail explicitly instead of being silently guessed.

### 4. Enricher (`src/leeknowledge/enricher.py`)

For each bookmark without an enrichment row:
1. Resolve every URL in `raw_urls` through `url_cache` and cache `resolved_url`, `page_title`, `page_description`, and `cached_at`. URL expansion is best-effort; failures keep the original URL, and metadata fetch failures keep null title/description fields instead of blocking enrichment.
2. Load the LLM configuration from `config/llm.yaml` through `lee-llm-router`; the `enricher` role owns the provider/model/temperature/timeout contract, while the prompt and schema version constants live in code so every stored row can be traced back to a specific contract. If you are running the full workflow through Agent-Orch, pin the entire run with `AGENT_ORCH_PI_MODEL=<model>` because per-step model selection is not available yet.
3. Build a prompt from tweet text, author fields, resolved URL data, and any fetched page metadata.
4. Call LLM via `lee-llm-router` using the pi harness.
5. Require one structured JSON object with:
   - `summary`: 1-2 sentence description of the key insight
   - `tags`: array of short lowercase tags
   - `entities`: array of short strings naming relevant people, organizations, tools, or concepts
   - `topic`: single topic label
6. Validate the response before storage; extra keys are ignored, but missing or mistyped required fields are rejected.
7. Store the validated result in the `enrichments` table keyed by `tweet_id`, together with the configured `model`, `prompt_version`, `schema_version`, `validation_status`, and `enriched_at` timestamp. If validation or transport fails, write the null enrichment placeholder instead of inventing values.

**Validation contract**
- Use a strict model or equivalent schema guard for `summary`, `tags`, `entities`, and `topic`.
- Coerce nothing that changes meaning; missing required fields fail explicitly.
- Normalize tag casing, strip empty strings, and deduplicate list entries before persistence.
- Treat malformed JSON, wrong field types, and transport errors as validation failures.

**Rerun and versioning semantics:**
- The default `enrich` command is idempotent at the tweet ID level.
- Existing enrichment rows are left unchanged on rerun.
- URL cache rows may be refreshed independently of the enrichment row.
- `model` is recorded from the resolved config, `prompt_version` changes when the prompt body changes, and `schema_version` changes when the structured output contract changes.
- Sprint 3 keeps one enrichment row per tweet; a future explicit re-enrichment workflow can layer on history without changing this contract.

**LLM integration:**
```python
from lee_llm_router import LLMRouter, load_config

config = load_config("config/llm.yaml")
router = LLMRouter(config)
response = router.complete(role="enricher", messages=[...])
```

**Config (`config/llm.yaml`):**
```yaml
llm:
  default_role: enricher
  providers:
    pi_harness:
      type: codex_cli
      command: pi
      args: ["--provider", "openai-codex", "--print"]
      response_format: json
      text_field: output_text
      timeout: 60.0
  roles:
    enricher:
      provider: pi_harness
      model: gpt-4o
      temperature: 0.3
      json_mode: true
      timeout: 60.0
```

When choosing a local model, keep the provider on `pi_harness` and update only the enricher role fields in `config/llm.yaml`; do not try to route per step inside the workflow definition.

**Enrichment prompt returns:**
```json
{
  "summary": "1-2 sentence description of the key insight",
  "tags": ["ai", "safety", "alignment"],
  "entities": ["Andrej Karpathy", "OpenAI", "GPT-4", "RLHF"],
  "topic": "ai"
}
```

### 5. Exporter (`src/leeknowledge/exporter.py`)

Current implementation: reads bookmarks + enrichments from SQLite, renders Markdown notes, writes them atomically into the vault contract, and powers the `sync` orchestration path.

**Vault and path contract**
- Default vault root is the repo-local `vault/` directory.
- The vault root may be overridden by `--vault-dir` or `LEEKNOWLEDGE_VAULT_DIR`; export must not depend on X, Chrome, or the LLM.
- Notes are written under `vault/YYYY/MM/<slug>-<tweet_id>.md`, where `YYYY/MM` comes from `created_at` when available and falls back to `first_seen_at`.
- `slug` is derived deterministically from the tweet text or author/text combo, lowercased and hyphenated; if no stable slug can be formed, fall back to `tweet-<tweet_id>`.
- Reruns must be idempotent at the file level: the same source row yields the same path, and the exporter replaces the existing file atomically instead of creating a conflicting duplicate.
- Export validates the SQLite path and required schema read-only before querying. Missing files or stale schemas fail with readable errors instead of being created or migrated during export.

**Markdown note contract**
- YAML frontmatter must preserve the source identity and enrichment provenance: `tweet_id`, `author_username`, `author_display_name`, `created_at`, `topic`, `tags`, `summary`, `entities`, `raw_urls`, `resolved_urls`, `model`, `prompt_version`, `schema_version`, `validation_status`, and `enriched_at`.
- The body must keep the tweet text visible as source content, followed by any resolved links or references, and end with a link back to the original tweet.
- Missing enrichment data should remain visible as null or empty fields rather than being fabricated.
- Jinja2 templates own the formatting; the template output must stay source-grounded and readable in plain text or Obsidian.
- Tweet text and summaries render inside fenced `text` blocks so source content stays literal.
- Resolved-link titles and descriptions are Markdown-escaped before rendering so punctuation cannot alter note structure.

**Implemented in Sprint 4**
- `export` loads bookmark and enrichment rows from SQLite, builds a render context, and feeds that context into a Jinja2 note template stored under `src/leeknowledge/templates/`.
- The template renders the note title, frontmatter, tweet text, enrichment provenance, and resolved links without inventing missing facts.
- File paths follow the stable vault contract above, and the exporter writes atomically so reruns replace the same file instead of forking duplicates.
- `sync` remains a sequential orchestrator: extract → enrich → export. It must halt immediately on the first failing stage, preserve outputs from earlier stages, and never try to export from a failed upstream run.
- Operator validation happens in two places: automated fidelity tests compare rendered notes to SQLite rows, and a human opens the vault in Obsidian to confirm a sample note is legible, searchable, and faithfully rendered.

**Sprint 5 hardening completed**
- Export now validates the SQLite path read-only and fails fast instead of bootstrapping database state.
- Markdown-sensitive content is escaped or fenced so note structure stays stable for real-world tweets and metadata.
- Verification and follow-up review were rerun in a Python 3.12+ dev environment with `.[dev]` installed.

**Export contract**
- Export reads only SQLite state and may not mutate extraction or enrichment tables.
- `sync` orchestrates extract → enrich → export in sequence, but each stage remains runnable on its own.
- Export may re-render files from the same database state, but it must not invent missing metadata or alter source facts.
- Export fidelity checks must compare rendered notes back to the SQLite row data and the note must not drop tweet text, provenance, or resolved URL information.

---

## Data Model

### SQLite Schema (`state/app.db`)

```sql
CREATE TABLE bookmarks (
    tweet_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    author_username TEXT,
    author_display_name TEXT,
    created_at TIMESTAMP,
    conversation_id TEXT,
    in_reply_to_id TEXT,
    media_urls TEXT,            -- JSON array
    raw_urls TEXT,              -- JSON array of t.co URLs
    first_seen_at TIMESTAMP NOT NULL
);

CREATE TABLE enrichments (
    tweet_id TEXT PRIMARY KEY,
    summary TEXT,
    tags TEXT,                  -- JSON array
    entities TEXT,              -- JSON array
    topic TEXT,
    model TEXT,
    prompt_version TEXT,
    schema_version TEXT,
    validation_status TEXT,
    enriched_at TIMESTAMP,
    FOREIGN KEY (tweet_id) REFERENCES bookmarks(tweet_id)
);

CREATE TABLE url_cache (
    original_url TEXT PRIMARY KEY,
    resolved_url TEXT,
    page_title TEXT,
    page_description TEXT,
    cached_at TIMESTAMP
);
```

**FTS5 index for full-text search:**
```sql
CREATE VIRTUAL TABLE bookmarks_fts USING fts5(
    tweet_id,
    text,
    author_username,
    content=bookmarks,
    content_rowid=rowid
);
```

---

## Directory Layout

```
leeKnowledge/
  src/leeknowledge/
    __init__.py
    __main__.py           # Entry point: python -m leeknowledge
    cli.py                # Typer CLI
    extractor.py          # Playwright extraction
    normalizer.py         # Raw JSON → SQLite
    enricher.py           # LLM enrichment via lee-llm-router
    exporter.py           # SQLite → Markdown
    db.py                 # SQLite connection and schema
    templates/
      bookmark.md.j2      # Jinja2 template for notes
  config/
    llm.yaml              # lee-llm-router config
  data/
    raw/                  # Immutable extraction archives
  state/
    app.db                # SQLite database
  vault/                  # Markdown output (Obsidian-compatible)
    2025/
      03/
  tests/
  pyproject.toml
```

---

## Markdown Note Format

```markdown
---
tweet_id: "1234567890"
author_username: "username"
author_display_name: "Display Name"
created_at: "2025-03-15T12:34:56Z"
topic: "ai"
tags:
  - llm
  - safety
summary: "Karpathy argues that RLHF is misaligned with true capability development."
entities:
  - Andrej Karpathy
  - OpenAI
  - GPT-4
raw_urls:
  - "https://t.co/example"
resolved_urls:
  - "https://example.com/article"
model: "gpt-5.4-mini"
prompt_version: 3
schema_version: 2
validation_status: "valid"
enriched_at: "2025-03-16T08:00:00Z"
---

# @username — 2025-03-15

> Karpathy argues that RLHF is fundamentally misaligned...

[Full tweet text rendered here]

## Resolved Links
- [Article Title](https://example.com/article)

## Source
- [View on X](https://x.com/username/status/1234567890)
```

---

## Pipeline Data Flow

### Stage 1: Extract
```
Chrome (logged in) → Playwright → GraphQL interception → raw archive
```

### Stage 2: Normalize
```
Raw archive → deterministic parser → canonical bookmark rows
           → dedup by tweet_id → SQLite bookmarks table
```

### Stage 3: Enrich
```
Un-enriched bookmarks → URL resolution + optional metadata fetch + cache → prompt builder → lee-llm-router (pi/openai-codex)
                                                               → validated enrichment row
```

### Stage 4: Export
```
bookmarks + enrichments → Jinja2 template → vault/YYYY/MM/<slug>-<id>.md
```

---

## Failure Handling

| Failure | Response |
|---------|----------|
| Not logged in to X | Playwright detects redirect to login page, aborts with clear message |
| GraphQL interception yields nothing | Abort the extract run and leave the database unchanged |
| Scroll stalls (no new bookmark payloads) | Retry until five consecutive polls yield nothing, then stop after persisting the archive |
| Raw archive write fails | Stop before SQLite mutation; do not partially normalize |
| Normalizer cannot produce a required canonical field | Skip or quarantine the bad record and report it explicitly |
| URL expansion timeout | Store the original URL, continue |
| Page metadata fetch fails | Keep null title/description fields and continue |
| LLM enrichment fails for one bookmark | Log warning, store a null enrichment placeholder, continue with rest |
| LLM returns malformed JSON | Log warning, store a null enrichment placeholder, do not invent values |
| SQLite insert conflict (duplicate) | INSERT OR IGNORE — this is expected behavior on reruns |

---

## Security and Privacy

- Raw JSON, SQLite, and vault are all local files — no cloud dependency.
- Chrome profile path is not stored in config — resolved at runtime.
- `data/`, `state/`, `config/llm.yaml`, and any `.env` files are gitignored.
- No cookies, tokens, or credentials are stored by leeKnowledge itself.
- Pi harness handles ChatGPT auth independently.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12+ |
| CLI | Typer |
| Browser automation | Playwright (Python) |
| Database | SQLite + FTS5 |
| Data models | Pydantic |
| LLM integration | lee-llm-router (codex_cli provider, pi harness) |
| Markdown rendering | Jinja2 |
| URL expansion | httpx (async) |
| Config | PyYAML |

---

## Explicit Decisions

1. **No adapter abstractions.** One extractor. If it breaks, fix it. Don't pre-build for extractors that don't exist.
2. **No observation/run model.** Dedup by tweet ID is sufficient at this scale. No need to track first_seen/last_seen per run.
3. **No vector search.** Obsidian's built-in search handles 200 items fine.
4. **No cloud anything.** Local SQLite, local files, local LLM calls via pi.
5. **Re-extract everything on each run.** At 200 bookmarks, full re-extraction is faster than building incremental logic. Dedup happens in SQLite.
6. **Enrichment is separate from export.** You can re-export without re-enriching, and re-enrich without re-extracting.
