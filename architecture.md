# Architecture: leeKnowledge

## Architectural Overview

leeKnowledge is a **local-first, replayable pipeline** with a stable downstream core and bounded source-intake entrypoints:

```
Extract / Import → Normalize → Enrich → Export → Derived Views
```

The stages are decoupled by SQLite. Each stage can be run independently and is idempotent. The one hard rule:

> **Source intake is unstable. Everything downstream must be stable.**

Sprint 9 is the verified leadership-feature baseline. Sprint 10 is now shipped and extends the intake edge from X-only extraction to a small source-agnostic intake surface (`extract`, `import-url`, `import-safari-folder`, `import-research`) without forcing downstream commands to branch on source-specific behavior.

The intake layer is replaceable at the edges. If X changes its DOM or GraphQL schema tomorrow, or a bounded non-X parser needs repair, only the relevant intake path changes. Normalization, enrichment, export, and derived views should consume the same canonical-row semantics regardless of how the data arrived.

---

## Design Principles

1. **Raw before smart** — Persist source JSON or source import artifacts before parsing, deduplicating, or enriching.
2. **Simple that works** — Keep intake bounded to explicit commands and one shared canonical-row contract. No general connector framework, no run manifests, no observation models.
3. **Replayable stages** — Re-enrich or re-export from SQLite without re-running source intake.
4. **LLM enriches, never validates** — Canonical source identity comes from deterministic normalization, not AI guesses.
5. **Local-first** — Everything runs on a laptop. No cloud services required.
6. **Dedup downstream** — X keeps legacy `tweet_id` compatibility; mixed-source intake deduplicates on explicit canonical source identity.

---

## System Context

```
┌─────────────────────────────────────────────────────────────────────┐
│                           macOS Laptop                             │
│                                                                     │
│  ┌───────────────┐   ┌───────────────────────────────────────────┐  │
│  │ Source inputs │──▶│             leeKnowledge CLI              │  │
│  │ X / URLs /    │   │ extract / import-* / enrich / export /    │  │
│  │ Safari /      │   │ topics / metadata / synthesize /          │  │
│  │ research      │   │ collections / sync                        │  │
│  └───────────────┘   └──────────────────┬────────────────────────┘  │
│                                         │                           │
│                    ┌────────────────────▼────────────────────┐      │
│                    │            SQLite Database               │      │
│                    │ bookmarks | enrichments | urls |        │      │
│                    │ leadership_metadata                     │      │
│                    └────────────────────┬────────────────────┘      │
│                                         │                           │
│                    ┌────────────────────▼────────────────────┐      │
│                    │         Vault (Markdown files)           │      │
│                    │ source notes + topics + briefs +        │      │
│                    │ collections                             │      │
│                    └─────────────────────────────────────────┘      │
│                                                                     │
│                    ┌─────────────────────────────────────────┐      │
│                    │ data/raw/*                              │      │
│                    │ immutable source snapshots before       │      │
│                    │ normalization                           │      │
│                    └─────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
         │                                         │
         ▼                                         ▼
   X Playwright session                     pi CLI (openai-codex)
   or bounded local import                  via lee-llm-router
```

---

## Major Components

### 1. CLI (`src/leeknowledge/cli.py`)

Python CLI using Typer. Current command state:

| Command | What it does |
|---------|-------------|
| `extract` | Completed Sprint 2 X-specific extraction slice: capture raw bookmark payloads, write the archive, normalize, and insert SQLite rows |
| `import-url` | Completed Sprint 10 command for bounded direct-URL intake into the shared normalization path |
| `import-safari-folder` | Completed Sprint 10 command for Safari bookmark export/folder intake into the shared normalization path |
| `import-research` | Completed Sprint 10 command for bounded research-artifact intake into the shared normalization path |
| `enrich` | Completed Sprint 3 enrichment slice: URL expansion, optional page metadata fetch, structured enrichment, and rerun-safe storage |
| `export` | Completed Sprint 4 command: render Markdown vault notes from SQLite |
| `topics` | Completed Sprint 6 command: render deterministic topic-index notes from local state |
| `metadata` | Completed Sprint 8 command: generate leadership metadata rows from local state |
| `synthesize` | Completed Sprint 7 command: generate weekly leadership briefs from local state |
| `collections` | Completed Sprint 9 command: render initiative-centered collection notes from local state |
| `sync` | Completed X-path orchestration: run extract → enrich → export in sequence |

The shipped downstream commands remain source-agnostic by contract. Sprint 10 broadens intake while preserving the existing enrichment, export, topic, metadata, synthesis, and collection behavior.

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

### 2a. Intake adapters (Sprint 10 shipped boundary)

Sprint 10 broadens intake without changing the downstream pipeline contract.

**Shared intake boundary**
- `extract` remains the X-specific Playwright path.
- `import-url`, `import-safari-folder`, and `import-research` are bounded local import commands, not a general connector system.
- Every intake path must write one immutable raw snapshot before normalization begins.
- Every accepted normalized row must resolve one stable identity tuple: `source_name`, `source_type`, `source_item_id`, `source_ref`, plus `tweet_id` for legacy X compatibility when applicable.
- Unknown adapter-specific fields stay in raw/quarantine payloads instead of being guessed into canonical fields.

**Adapter acceptance intent**
- `import-url`: one explicit URL per input item; identity comes from the canonicalized absolute URL.
- `import-safari-folder`: one Safari bookmark item per parsed export record; identity comes from folder lineage plus canonicalized bookmark URL.
- `import-research`: one accepted record per artifact row/item; identity comes from artifact identity plus stable per-record locator.

**Downstream rule**
- Once a row is normalized, enrichment, export, topics, metadata, synthesis, and collections should not need to care whether it came from X extraction or a bounded non-X import path.

### 3. Normalizer (`src/leeknowledge/normalizer.py`)

Transforms raw captured archives into canonical SQLite records:
- Reads only archived raw capture/import formats produced by the intake layer.
- Extracts the canonical bookmark fields required by the shared schema: `tweet_id`, `source_name`, `source_type`, `source_item_id`, `source_ref`, `text`, `author_username`, `author_display_name`, `created_at`, `conversation_id`, `in_reply_to_id`, `media_urls`, `raw_urls`, and `first_seen_at`.
- Preserves X compatibility by mapping X rows to `source_name=x`, `source_type=x_bookmark`, `source_item_id=<tweet_id>`, while keeping `tweet_id` as the legacy compatibility key.
- Requires non-X rows to provide `source_name`, `source_type`, `source_item_id`, and `source_ref` together, with downstream compatibility through `canonical_item_id = tweet_id` for X rows and `<source_name>:<source_type>:<source_item_id>` otherwise.
- Uses deterministic identity derivation from raw input alone and rerun-safe inserts keyed by the shared canonical identity contract.
- Skips or quarantines records that cannot satisfy the required identity and schema shape; the intake layer is never asked to repair them heuristically.
- Defers URL expansion and page-metadata fetch to later pipeline stages; normalization stays deterministic and replayable.

**Normalization rules:**
- Normalization is deterministic and must not depend on browser state or LLM output.
- Source payloads remain the provenance record; canonical rows are derived, not authoritative.
- Missing optional fields are allowed if the canonical SQLite schema can represent them.
- Missing required source-identity fields must fail explicitly instead of being silently guessed.

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
- The vault root may be overridden by `--vault-dir` or `LEEKNOWLEDGE_VAULT_DIR`; export must not depend on source-specific intake state, Chrome, or the LLM.
- X rows keep the shipped note-path contract under `vault/YYYY/MM/<slug>-<tweet_id>.md` so Sprint 9 remains the stable closeout baseline.
- Non-X rows should use the same date-partitioned vault layout but derive a stable path from the shared canonical identity rather than forcing fake tweet IDs.
- `slug` is derived deterministically from visible source text or equivalent human-readable context; if no stable slug can be formed, fall back to the canonical identity.
- Reruns must be idempotent at the file level: the same source row yields the same path, and the exporter replaces the existing file atomically instead of creating a conflicting duplicate.
- Export validates the SQLite path and required schema read-only before querying. Missing files or stale schemas fail with readable errors instead of being created or migrated during export.

**Markdown note contract**
- YAML frontmatter must preserve source identity and enrichment provenance, including `tweet_id`, `source_name`, `source_type`, `source_item_id`, `source_ref`, `author_username`, `author_display_name`, `created_at`, `topic`, `tags`, `summary`, `entities`, `raw_urls`, `resolved_urls`, `model`, `prompt_version`, `schema_version`, `validation_status`, and `enriched_at`.
- The body must keep source text visible, followed by any resolved links or references, and end with the most specific available source backlink (X status URL for X rows, otherwise source reference material).
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
    tweet_id TEXT UNIQUE,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    canonical_item_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    author_username TEXT,
    author_display_name TEXT,
    created_at TIMESTAMP,
    conversation_id TEXT,
    in_reply_to_id TEXT,
    media_urls TEXT,            -- JSON array
    raw_urls TEXT,              -- JSON array
    first_seen_at TIMESTAMP NOT NULL
);

CREATE TABLE enrichments (
    canonical_item_id TEXT PRIMARY KEY,
    tweet_id TEXT UNIQUE,
    summary TEXT,
    tags TEXT,                  -- JSON array
    entities TEXT,              -- JSON array
    topic TEXT,
    model TEXT,
    prompt_version TEXT,
    schema_version TEXT,
    validation_status TEXT,
    enriched_at TIMESTAMP,
    FOREIGN KEY (canonical_item_id) REFERENCES bookmarks(canonical_item_id)
);

CREATE TABLE url_cache (
    original_url TEXT PRIMARY KEY,
    resolved_url TEXT,
    page_title TEXT,
    page_description TEXT,
    cached_at TIMESTAMP
);
```

**Schema intent for Sprint 10**
- X rows keep `tweet_id` populated and derive `canonical_item_id = tweet_id`.
- Non-X rows may leave `tweet_id` null but must populate `source_name`, `source_type`, `source_item_id`, `source_ref`, and `canonical_item_id`.
- `canonical_item_id` is the shared downstream join/dedupe key; `tweet_id` remains the legacy X-compatibility field.

**FTS5 index for full-text search:**
```sql
CREATE VIRTUAL TABLE bookmarks_fts USING fts5(
    canonical_item_id,
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
canonical_item_id: "1234567890"
tweet_id: "1234567890"
source_name: "x"
source_type: "x_bookmark"
source_item_id: "1234567890"
source_ref: "https://x.com/username/status/1234567890"
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

[Full source text rendered here]

## Resolved Links
- [Article Title](https://example.com/article)

## Source
- [View on X](https://x.com/username/status/1234567890)
```

---

## Pipeline Data Flow

### Stage 1: Extract / Import
```
X Playwright extraction or bounded local import command
→ immutable raw snapshot
```

### Stage 2: Normalize
```
Raw snapshot → deterministic parser → canonical bookmark rows
             → dedup by canonical_item_id with tweet_id compatibility for X
             → SQLite bookmarks table
```

### Stage 3: Enrich
```
Un-enriched canonical rows → URL resolution + optional metadata fetch + cache → prompt builder → lee-llm-router (pi/openai-codex)
                                                                      → validated enrichment row
```

### Stage 4: Export
```
bookmarks + enrichments → Jinja2 template → stable source-note path
```

### Stage 5: Derived Views
```
source notes + SQLite state → topics / metadata / synthesize / collections
```

---

## Failure Handling

| Failure | Response |
|---------|----------|
| Not logged in to X | Playwright detects redirect to login page, aborts with clear message |
| GraphQL interception yields nothing | Abort the extract run and leave the database unchanged |
| Import input cannot be opened or parsed at all | Stop before SQLite mutation after reporting the adapter-specific read/parse error |
| Scroll stalls (no new bookmark payloads) | Retry until five consecutive polls yield nothing, then stop after persisting the archive |
| Raw snapshot write fails | Stop before SQLite mutation; do not partially normalize |
| Normalizer cannot produce required source identity | Quarantine or reject the bad record explicitly; do not guess canonical rows |
| Duplicate canonical identity on rerun | Treat as expected idempotent behavior |
| URL expansion timeout | Store the original URL, continue |
| Page metadata fetch fails | Keep null title/description fields and continue |
| LLM enrichment fails for one bookmark | Log warning, store a null enrichment placeholder, continue with rest |
| LLM returns malformed JSON | Log warning, store a null enrichment placeholder, do not invent values |

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

1. **No general connector framework.** Keep intake bounded to the shipped X extractor plus explicit Sprint 10 import commands. If one path breaks, fix that path without inventing a broad plugin system.
2. **No observation/run model.** Source identity and canonical-row dedupe are sufficient at this scale. No need to track first_seen/last_seen per run beyond existing row timestamps.
3. **No vector search.** Obsidian's built-in search handles this corpus size fine.
4. **No cloud anything.** Local SQLite, local files, local LLM calls via pi.
5. **X note-path compatibility is preserved.** Sprint 9 remains the verified closeout baseline, so X keeps `tweet_id`-based identity and note-path behavior while non-X intake joins through `canonical_item_id`.
6. **Enrichment and derived views stay separate from intake.** You can re-export, re-topic, re-score metadata, resynthesize, or rebuild collections without re-running source intake.
