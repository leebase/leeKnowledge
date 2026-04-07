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

Python CLI using Typer. Four commands:

| Command | What it does |
|---------|-------------|
| `extract` | Run Playwright, save raw JSON, normalize to SQLite |
| `enrich` | LLM-enrich un-enriched bookmarks via lee-llm-router |
| `export` | Regenerate all Markdown from SQLite |
| `sync` | Run extract + enrich + export in sequence |

### 2. Extractor (`src/leeknowledge/extractor.py`)

Playwright script that:
1. Launches Chrome with the user's existing profile (`--user-data-dir`).
2. Navigates to `x.com/i/bookmarks`.
3. Registers a response interceptor for GraphQL `Bookmarks` queries.
4. Scrolls with randomized delays (2-3 seconds) until no new content loads.
5. Collects all intercepted bookmark payloads.
6. Saves complete raw JSON to `data/raw/bookmarks_YYYY-MM-DD.json`.
7. Returns parsed bookmark records for normalization.

**Fallback:** If GraphQL interception yields no results, fall back to DOM extraction using `data-testid="tweet"` selectors.

**Anti-detection:**
- Random scroll delays: `random.uniform(1.5, 3.0)` seconds.
- Standard viewport: 1280x800.
- No proxy rotation (single personal account, low frequency).
- Run at most weekly.

### 3. Normalizer (`src/leeknowledge/normalizer.py`)

Transforms raw extracted data into canonical SQLite records:
- Extracts tweet ID, text, author, timestamp, URLs, media, conversation ID.
- Deduplicates by tweet ID (INSERT OR IGNORE).
- Expands t.co URLs to real destinations (cached in `url_cache` table).
- Fetches page title/description for linked articles (best-effort, 5-second timeout).

### 4. Enricher (`src/leeknowledge/enricher.py`)

For each bookmark not yet enriched:
1. Builds a prompt with tweet text, author, and linked article title (if available).
2. Calls LLM via `lee-llm-router` using the pi harness with `openai-codex` provider.
3. Requests structured JSON: summary, tags, entities, topic.
4. Stores result in the `enrichments` table keyed by tweet ID.

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
```

**Enrichment prompt returns:**
```json
{
  "summary": "1-2 sentence description of the key insight",
  "tags": ["ai", "safety", "alignment"],
  "entities": {
    "people": ["Andrej Karpathy"],
    "organizations": ["OpenAI"],
    "tools": ["GPT-4"],
    "concepts": ["RLHF"]
  },
  "topic": "ai"
}
```

### 5. Exporter (`src/leeknowledge/exporter.py`)

Reads all bookmarks + enrichments from SQLite and renders Markdown files:
- One file per bookmark: `vault/YYYY/MM/<slug>-<tweet_id>.md`.
- YAML frontmatter with all metadata.
- Tweet text as body.
- Linked URLs expanded inline.
- Link back to original tweet.

Uses Jinja2 templates for rendering.

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
    entities TEXT,              -- JSON object
    topic TEXT,
    model TEXT,
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
author: "@username"
author_name: "Display Name"
date: 2025-03-15
url: "https://x.com/username/status/1234567890"
topic: "ai"
tags:
  - llm
  - safety
summary: "Karpathy argues that RLHF is misaligned with true capability development."
entities:
  people:
    - Andrej Karpathy
  organizations:
    - OpenAI
  tools:
    - GPT-4
---

# @username — 2025-03-15

Karpathy argues that RLHF is fundamentally misaligned...

[Full tweet text]

---

**Links:**
- [Article Title](https://example.com/article)

[View on X](https://x.com/username/status/1234567890)
```

---

## Pipeline Data Flow

### Stage 1: Extract
```
Chrome (logged in) → Playwright → GraphQL interception → raw JSON file
                                                        → parsed records
```

### Stage 2: Normalize
```
Parsed records → dedup by tweet_id → SQLite bookmarks table
              → expand t.co URLs → url_cache table
```

### Stage 3: Enrich
```
Un-enriched bookmarks → prompt builder → lee-llm-router (pi/openai-codex)
                                       → enrichments table
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
| GraphQL interception yields nothing | Fall back to DOM extraction |
| Scroll stalls (no new content) | Retry 3 times, then stop and process what was captured |
| URL expansion timeout | Store original t.co URL, continue |
| LLM enrichment fails for one bookmark | Log warning, skip that bookmark, continue with rest |
| LLM returns malformed JSON | Log warning, store null enrichment, bookmark still exported without enrichment |
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
