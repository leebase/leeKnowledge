# Product Definition: leeKnowledge

## Product Overview

**Name:** leeKnowledge
**Type:** Personal bookmark-to-knowledge pipeline — local-first, single-user
**Purpose:** Extract X/Twitter bookmarks, import a small bounded set of other saved-source artifacts, enrich them with LLM-generated summaries and tags, and produce a durable Markdown knowledge base that works in Obsidian or any text editor.

---

## Problem Statement

X bookmarks are a write-only habit. You save posts while reading — threads, insights, tools, articles — intending to return. You never do, because:

1. X has no useful bookmark search or organization.
2. Bookmarks are chronological — no topics, no tags, no structure.
3. If X changes its product or you lose access, the bookmarks are gone.
4. A saved tweet is just a tweet — no summary, no context, no connection to related content.
5. There is no simple, free way to export your own bookmarks.

The hardest part is **reliable extraction**. Everything else is downstream.

---

## Goals

1. Extract all existing bookmarks (~100-200) via Playwright automation.
2. Save raw extracted data as immutable JSON before any processing.
3. Normalize into SQLite with dedup by tweet ID so reruns are safe.
4. Enrich each bookmark with LLM-generated summary and tags via lee-llm-router (pi harness, ChatGPT subscription).
5. Render each bookmark as a Markdown note with YAML frontmatter.
6. Add bounded non-X intake for direct URLs, Safari bookmark exports/folders, and deep-research artifacts without breaking the shipped X workflow.
7. Preserve one explicit source-identity contract across all intake paths so reruns, dedupe, and downstream notes stay stable.
8. Support rerunning: re-extract everything, dedup downstream, only enrich new items.
9. Keep it local, simple, and maintainable by one person.

---

## Non-Goals

- Mass scraping or multi-account collection.
- Cloud infrastructure, SaaS, or hosted services.
- Custom web UI or frontend application.
- Vector/semantic search (Obsidian search is sufficient for ~200 items).
- X API integration ($200/month, limited to 800 recent — not viable).
- Publishing or redistributing extracted content.
- Perfect thread reconstruction or deleted post recovery.
- Selling this to anyone. This is personal tooling.

---

## Primary User

Lee. A technical user who bookmarks posts on X across domains (AI, theology, health, physics, music, tech), runs Python on macOS, and wants those bookmarks turned into a searchable local knowledge base.

**Profile:**
- ~100-200 existing bookmarks, growing slowly.
- Comfortable running CLI tools and Python scripts.
- Uses or is willing to use Obsidian as a knowledge base viewer.
- Has a ChatGPT subscription ($20/month) for LLM enrichment via pi harness.
- Has Chrome with an active X login on this machine.

---

## Core User Journeys

### 1. Initial Bulk Export
Run `python -m leeknowledge sync`. Playwright opens Chrome, scrolls the bookmarks page, captures all bookmarks via GraphQL interception, saves raw JSON, normalizes to SQLite, enriches with LLM, and writes Markdown files to the vault.

**Duration:** ~5-10 minutes for 200 bookmarks (mostly scroll time + LLM calls).

### 2. Periodic Re-sync
Run the same command weeks later. Extraction re-captures everything (fast at this scale). SQLite dedup skips already-known tweet IDs. Only new bookmarks flow through enrichment and rendering.

### 3. Finding a Saved Bookmark
Open the vault folder in Obsidian (or VS Code, or grep). Search by text, browse by tag or author, or scan the date-organized folders. Each note links back to the original tweet URL.

### 4. Re-enrich Without Re-extracting
Run `python -m leeknowledge enrich` to re-run LLM enrichment against existing SQLite data — e.g., after changing the prompt or switching models. Then `python -m leeknowledge export` to regenerate Markdown.

---

## Functional Requirements

### Extraction
- F1: Launch Chrome with user's existing browser profile (already logged in).
- F2: Navigate to `x.com/i/bookmarks` and scroll to load all bookmarks.
- F3: Intercept GraphQL `Bookmarks` responses to capture structured JSON.
- F4: Capture per bookmark: tweet ID, text, author (username + display name), timestamp, media URLs, linked URLs, conversation ID, in-reply-to ID.
- F5: Save complete raw extraction to `data/raw/bookmarks_YYYY-MM-DD.json` (immutable, append-only by date).
- F6: Fall back to DOM extraction (`data-testid="tweet"`) if GraphQL interception fails.

### Normalization
- F7: Parse raw JSON into canonical bookmark records.
- F8: Store in SQLite with tweet ID as primary key.
- F9: Deduplicate: skip inserts for tweet IDs already in the database.
- F10: Expand t.co URLs to real destinations (with caching).
- F11: Fetch page title and description from linked articles (best-effort, timeout-tolerant).

### Enrichment
- F12: For each un-enriched bookmark, call LLM via lee-llm-router (pi harness, openai-codex provider).
- F13: Generate: 1-2 sentence summary, 3-5 topic tags, named entities (people, orgs, tools, concepts).
- F14: Store enrichment results in a separate SQLite table (keyed by tweet ID + model version).
- F15: Enrichment is optional — bookmarks without enrichment still get exported as plain notes.

### Export
- F16: Render each bookmark as a Markdown file with YAML frontmatter.
- F17: Frontmatter includes: tweet_id, author, date, url, tags, entities, summary, topic.
- F18: Organize vault by `vault/YYYY/MM/<slug>-<tweet_id>.md`.
- F19: Support full re-export from SQLite without re-extracting.

### Universal Source Intake
- F20: Preserve the existing X extraction contract and map X rows to `source_name=x`, `source_type=x_bookmark`, `source_item_id=<tweet_id>`, while keeping `tweet_id` as the legacy compatibility key.
- F21: Support `import-url` for one explicit URL per input item with deterministic identity from the canonicalized absolute URL.
- F22: Support `import-safari-folder` for one Safari bookmark item per parsed export record with deterministic identity from folder lineage plus canonicalized bookmark URL.
- F23: Support `import-research` for one accepted item inside a Markdown, JSON, JSONL, or CSV research artifact with deterministic identity from artifact identity plus a stable per-record locator.
- F24: Every non-X normalized row must carry `source_name`, `source_type`, `source_item_id`, and `source_ref`; downstream compatibility uses `canonical_item_id = tweet_id` for X rows and `<source_name>:<source_type>:<source_item_id>` otherwise.
- F25: Raw import artifacts must be written before normalization, and malformed per-record inputs must be quarantined with explicit reasons and record locators instead of guessed into canonical rows.
- F26: Existing export and derived stages must remain backward compatible: X note paths and X backlinks stay unchanged, while mixed-source rows flow through enrichment, export, topics, metadata, synthesis, and collections through shared canonical-row semantics rather than per-command branching.

### CLI
- F27: `extract` — run Playwright extraction only.
- F28: `import-url` — import one or more explicit URLs into the shared normalization path.
- F29: `import-safari-folder` — import Safari bookmark export/folder artifacts into the shared normalization path.
- F30: `import-research` — import deep-research artifacts into the shared normalization path.
- F31: `enrich` — run LLM enrichment on un-enriched bookmarks only.
- F32: `export` — regenerate all Markdown from SQLite.
- F33: `sync` — run extract + enrich + export in sequence for the existing X path; non-X imports remain explicit commands.

---

## Non-Functional Requirements

- **Reliability:** A failed run must not corrupt existing data. Raw JSON is saved before processing. SQLite operations are idempotent.
- **Performance:** The full pipeline handles 200 bookmarks in under 10 minutes. Reruns with no new bookmarks complete in under a minute (dedup short-circuits).
- **Privacy:** No data leaves the machine except LLM calls via pi harness. No cookies, credentials, or raw data committed to git.
- **Maintainability:** Extraction logic is isolated — changing how X is scraped does not require changes to normalization, enrichment, or export.
- **Portability:** Vault output is plain Markdown with YAML frontmatter. Works in Obsidian, VS Code, any text editor.

---

## Constraints

- Chrome with active X login on macOS is required for extraction.
- X's DOM and GraphQL schema can change without notice — the extractor is inherently brittle.
- Playwright automation may violate X's terms — accepted risk for personal archival of own data.
- Pi harness / ChatGPT subscription is required for enrichment (can be skipped if unavailable).
- Human-like scroll delays (2-3 seconds) mean extraction is intentionally slow to avoid detection.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| X changes GraphQL schema | High | Medium | Fall back to DOM extraction; extractor is isolated |
| X detects automation | Low (at this scale) | Medium | Human-like delays, weekly frequency, personal account only |
| Cookies expire mid-run | Medium | Low | Fail clearly, user re-logs in Chrome |
| LLM enrichment quality is poor | Medium | Low | Enrichment is optional; doesn't affect raw data |
| Playwright version breaks | Low | Low | Pin version, update as needed |

---

## Definition of Done — MVP

1. `python -m leeknowledge sync` extracts all bookmarks, normalizes, enriches, and writes Markdown.
2. Raw JSON is preserved in `data/raw/` and never modified.
3. Reruns deduplicate by tweet ID — no duplicate notes, no re-enrichment of known items.
4. Each Markdown note has: tweet text, author, date, URL, summary, tags.
5. The vault opens in Obsidian and bookmarks are browsable by tag, date, and author.
6. A manual spot-check of 20 bookmarks shows acceptable fidelity.

---

## Future Possibilities (Not MVP)

- Bookmark folder support (if X Premium exposes folders).
- Thread reconstruction (concatenate multi-post threads into single notes).
- Topic index pages (auto-generated MOC notes per topic).
- Semantic search via local embeddings.
- Browser extension for capture-at-bookmark-time.
- Weekly synthesis notes ("what I bookmarked this week").
