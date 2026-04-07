# product-definition.md

## Product Overview

**Name:** BookmarkBrain (working title)
**Type:** Personal knowledge management tool — local-first, single-user
**Purpose:** Convert a personal X/Twitter bookmark collection into a durable, queryable knowledge base stored as Markdown files in an Obsidian-compatible vault.

---

## Problem Statement

X bookmarks are a graveyard. A user saves content while reading — articles, threads, insights, tools — intending to return. They never do, because there is no way to find what they saved, rediscover it by topic, or extract the embedded knowledge into their personal thinking system.

The specific failure modes:

1. **No search**: X's native bookmark search is limited and not integrated with any personal knowledge workflow.
2. **No organization**: Bookmarks are chronological by default. No topic grouping, no entity extraction, no structure.
3. **No durability**: If X disappears, changes its product, or the user loses access, the bookmarks are gone.
4. **No enrichment**: A saved tweet is just a tweet. The system adds nothing — no summary, no tags, no connection to related content.
5. **No extraction path**: Until 2025, there was no practical way to export your own bookmarks programmatically without paying $200/month for API access.

The hardest problem — which is also the gating constraint — is **reliable extraction of bookmarks from X**. Everything else is downstream of solving this.

---

## Goals

1. Extract all existing bookmarks (full historical backlog, not just recent 800).
2. Store raw bookmark data in a durable local format before any processing.
3. Normalize and enrich each bookmark into a structured Markdown note with consistent frontmatter.
4. Organize notes into an Obsidian-compatible vault browsable by topic, author, and date.
5. Support incremental sync — new bookmarks can be added to the vault without re-processing the full history.
6. Enable full-text and tag-based search via Obsidian natively.
7. Optionally enrich bookmarks with LLM-generated summaries and topic tags.
8. Reconstruct threads as single notes where possible.

---

## Non-Goals

**For MVP:**
- No custom web UI or frontend application
- No vector database or semantic search (Obsidian search is sufficient for MVP)
- No real-time or webhook-triggered sync
- No multi-user support
- No cloud infrastructure or remote hosting
- No scraping content from other users — only authenticated user's own bookmarks
- No redistribution of tweet content

**Ever (out of scope):**
- Commercialization or SaaS productization
- Enterprise/team features
- Analytics dashboards or trend detection at scale
- Integration with X's paid API tier (unless free tier becomes available)

---

## Primary Users

**Single user:** The person who built and runs the system for their own personal use. Technical enough to run Python scripts, comfortable with Obsidian, owns an X account with an existing bookmark collection.

Profile:
- Has 500–10,000+ existing bookmarks accumulated over months or years
- Bookmarks content across domains: tech, theology, health, writing, AI, physics
- Uses Obsidian or is willing to adopt it as the knowledge base viewer
- Runs on macOS or Windows laptop

---

## Core User Journeys

### Journey 1: Initial Bulk Export
The user runs the ingestion CLI once. It opens a browser session using stored cookies, scrolls their X bookmarks page, captures all bookmarks into a local SQLite database, and then runs the processing pipeline to generate the full Obsidian vault.

Expected duration: 2–4 hours unattended for large collections (thousands of bookmarks).

### Journey 2: Weekly Incremental Sync
The user runs the sync command weekly. The extractor captures recently added bookmarks (those after the last sync timestamp), processes only the new items, and adds notes to the vault. Existing notes are not modified unless explicitly requested.

Expected duration: 5–15 minutes for a typical week's additions.

### Journey 3: Finding a Saved Bookmark
The user opens Obsidian, uses the search or tag panel to find notes on a topic. They navigate from the note to the original tweet via the embedded URL. They may follow backlinks to related notes on the same entity or theme.

### Journey 4: Replaying Enrichment
The user upgrades the summarization prompt or switches LLM providers. They re-run the enrichment stage against existing raw data in SQLite without re-scraping. Updated notes are written to the vault.

---

## Functional Requirements

### Extraction
- F1: Authenticate to X using stored session cookies (no username/password required at runtime)
- F2: Navigate to x.com/i/bookmarks and scroll to load full bookmark list
- F3: Intercept GraphQL responses OR extract from DOM — whichever is more stable at runtime
- F4: Capture: tweet ID, tweet text, author username, author display name, timestamp, media URLs, linked URLs, conversation ID, in-reply-to ID
- F5: Store raw captured data in SQLite before any processing
- F6: Deduplicate by tweet ID — never insert a duplicate
- F7: Track last sync timestamp for incremental mode
- F8: Support folder-based bookmark extraction if the user uses X's bookmark folders feature

### Processing
- F9: Expand t.co URLs to real destinations
- F10: Fetch page title and description from linked articles (best-effort, timeout-tolerant)
- F11: Reconstruct threads: if a bookmarked tweet is part of a thread, fetch the full thread chain and concatenate into a single note
- F12: Normalize tweet text (decode HTML entities, handle Unicode)
- F13: Extract author metadata for frontmatter

### Enrichment (Optional, Configurable)
- F14: Generate a 1–3 sentence summary per tweet or thread using LLM
- F15: Generate topic tags using LLM (from a configurable controlled vocabulary or open-ended)
- F16: Extract named entities (people, organizations, tools, concepts) for frontmatter
- F17: Support Claude API or local Ollama as LLM provider (configurable via env var)

### Storage
- F18: Write one Markdown file per bookmark (or per thread) to the vault directory
- F19: Frontmatter must include: tweet_id, author, date, url, tags, entities, summary (if enriched), topic
- F20: Organize vault by year/month subdirectory by default; optionally by topic
- F21: Maintain SQLite as the source of truth for processing state
- F22: Support re-export (regenerate all Markdown from SQLite without re-scraping)

### Operations
- F23: CLI interface with commands: `extract`, `process`, `enrich`, `export`, `sync`
- F24: Dry-run mode for extraction (shows count without writing)
- F25: Progress logging to console
- F26: Configuration via `.env` file for credentials and paths
- F27: Cookie export helper: instructions or script to export session cookies from browser

---

## Non-Functional Requirements

- **Reliability:** Extraction must handle network errors, page load timeouts, and scroll failures with retry logic. A failed run must not corrupt existing data.
- **Performance:** Processing pipeline must handle 10,000 bookmarks in under 60 minutes on a modern laptop.
- **Privacy:** No data leaves the local machine except for LLM API calls (configurable). Cookies are stored encrypted or in a local secrets file, never committed to git.
- **Maintainability:** The extraction layer must be isolatable — changing how X is scraped must not require changes to the processing or storage layers.
- **Portability:** The vault output must be valid Obsidian-compatible Markdown. It must not depend on any proprietary format or plugin.
- **Recoverability:** All processing must be replayable from SQLite raw data. Re-running the pipeline is always safe.

---

## Constraints

- User pays $11/month for X (basic subscriber) — no X API paid tier
- System runs on a personal laptop (macOS or Windows) — no cloud required
- Cookie-based authentication is the primary extraction mechanism — cookies expire and must occasionally be refreshed
- X's DOM and GraphQL schema can change without notice — the extraction layer is inherently brittle
- X Terms of Service prohibit unauthorized scraping/crawling — user accepts this risk for personal archival use of their own data

---

## Risks and Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| X changes DOM/GraphQL, breaking extractor | High | Medium | Extractor is isolated; fix without touching pipeline |
| X detects automation, flags account | Medium | High | Run slowly (human-like delays), limit frequency, use personal account only |
| Cookies expire mid-run | Medium | Low | Extractor detects auth failure, pauses and prompts for cookie refresh |
| X deprecates bookmark access entirely | Low | Critical | Export to JSON immediately; maintain raw SQLite as archive |
| LLM enrichment quality is poor | Medium | Low | Enrichment is optional; quality doesn't affect extraction or storage correctness |
| Thread reconstruction fetches deleted tweets | High | Low | Handle 404s gracefully; store partial threads |

**Key Assumptions:**
- The user's X account has an existing bookmark collection worth archiving
- The user has Python 3.11+ and can run Playwright locally
- Obsidian is acceptable as the primary knowledge base viewer
- Personal archival of one's own bookmarks is acceptable use under current legal interpretation

---

## Definition of Done — MVP

The MVP is complete when:

1. A user can run `python cli.py extract` and have their full bookmark history captured to SQLite
2. A user can run `python cli.py process` and have every bookmark converted to a Markdown note in the vault
3. The vault opens in Obsidian and bookmarks are browsable by tag, date, and author
4. Incremental sync adds only new bookmarks without duplicating or overwriting existing notes
5. The extractor fails gracefully: network errors, timeouts, and auth failures produce clear log output and do not corrupt existing data
6. A README documents: cookie export, first run, incremental sync, and enrichment setup

---

## Future Expansion Opportunities

- **Semantic search layer:** Embed notes with a local embedding model (e.g., nomic-embed via Ollama) and add a vector search CLI command
- **At-time-of-bookmark capture:** Browser extension that captures at save time, eliminating the need to scroll historical bookmarks
- **Synthesis reports:** Weekly LLM job that synthesizes recent bookmarks by topic into a new note
- **Backlink generation:** Cross-link notes that share entities or topics
- **Export to Readwise/Notion:** Transform vault notes to other formats for users of those tools
- **X API integration (if cost drops):** Add official API as an alternative extraction path
