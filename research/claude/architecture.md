architecture.md
Architectural Overview
BookmarkBrain is a local-first, single-user data pipeline that converts X/Twitter bookmarks into a durable Markdown knowledge base. It is composed of four isolated stages: Extract → Normalize → Enrich → Export. The stages are decoupled by a canonical intermediate data model stored in SQLite. Each stage can be run independently and is fully replayable.
The design principle that governs every decision: the extraction layer is treated as permanently unstable. Everything downstream must be able to function without modification when extraction changes.
***Design Principles
Extraction Isolation: The scraping layer outputs one schema. Nothing else cares how that schema was produced.
Raw Capture First: Nothing is processed until raw data is stored. The raw store is append-only and treated as sacred.
Replayability: Every processing stage reads from SQLite and can be re-run safely. Re-runs are idempotent.
File-First Outputs: The canonical knowledge base output is Markdown files. Human-readable, portable, durable.
LLM as Enrichment, Not Infrastructure: The system is correct without LLM enrichment. LLMs add value, not correctness.
Local First: No cloud dependencies for MVP. Data stays on the user's machine.
Minimal Surface Area: The system does fewer things well rather than many things poorly.
***System Context
┌─────────────────────────────────────────────────────────────┐
│                    USER'S LAPTOP                            │
│                                                             │
│  ┌─────────────┐    ┌──────────────────────────────────┐   │
│  │   Browser   │    │         BookmarkBrain CLI         │   │
│  │  (cookies)  │───▶│  extract / process / enrich /    │   │
│  └─────────────┘    │         export / sync             │   │
│                     └─────────────┬────────────────────-┘   │
│                                   │                         │
│              ┌────────────────────▼───────────────────┐     │
│              │           SQLite Database               │     │
│              │  raw_bookmarks | processed_bookmarks |  │     │
│              │  threads | sync_state | enrichments     │     │
│              └────────────────────┬───────────────────┘     │
│                                   │                         │
│              ┌────────────────────▼───────────────────┐     │
│              │         Obsidian Vault (Markdown)       │     │
│              │   /vault/2024/01/tweet_12345.md  ...    │     │
│              └────────────────────────────────────────-┘     │
└─────────────────────────────────────────────────────────────┘
          │                               │
          ▼                               ▼
    x.com/i/bookmarks            Claude API or Ollama
    (Playwright session)         (optional enrichment)
***Major Components
1. Extractor (extractor/)
Responsible for: authenticated access to X, scrolling the bookmarks page, capturing raw tweet data.
Replaceability: High. This component is expected to break and be replaced. Its only contract is output schema.
Technology: Playwright (Python), cookie-based session auth.
2. Raw Store (db/raw.py)
Responsible for: append-only storage of raw extractor output, deduplication by tweet ID.
Technology: SQLite, raw_bookmarks table.
3. Processor (pipeline/processor.py)
Responsible for: URL expansion, thread reconstruction, text normalization, metadata extraction.
Technology: Python, httpx for URL expansion, recursive tweet fetch for threads.
4. Enricher (pipeline/enricher.py)
Responsible for: LLM-powered summarization, tagging, entity extraction.
Technology: Anthropic SDK or Ollama client. Provider is configured via env var.
Dependency: Optional. System functions without it.
5. Exporter (pipeline/exporter.py)
Responsible for: generating Markdown files with YAML frontmatter, organized by configured directory structure.
Technology: Python, pathlib, PyYAML.
6. CLI (cli.py)
Responsible for: user-facing commands, orchestrating pipeline stages, progress reporting.
Technology: Click or Typer.
7. Config (config.py)
Responsible for: loading .env configuration, validating required secrets, providing defaults.
***Data Flow / Pipeline Stages
Stage 0: Cookie Export (manual, one-time setup)
  User exports cookies from browser DevTools → saves to cookies.json (gitignored)
Stage 1: Extract
  Input:  cookies.json + x.com/i/bookmarks
  Output: raw_bookmarks rows in SQLite
  Schema: {tweet_id, raw_json, extracted_at, source}
Stage 2: Process
  Input:  raw_bookmarks (SQLite)
  Output: processed_bookmarks (SQLite)
  Schema: {tweet_id, text, author_username, author_name, created_at,
           expanded_urls[], thread_id, thread_order, thread_text,
           media_urls[], is_thread_root, processed_at}
Stage 3: Enrich (optional)
  Input:  processed_bookmarks (SQLite)
  Output: enrichments (SQLite)
  Schema: {tweet_id, summary, tags[], entities[], topic, enriched_at, model}
Stage 4: Export
  Input:  processed_bookmarks + enrichments (SQLite)
  Output: Markdown files in vault directory
***Extraction Architecture
Why Cookie-Based Playwright (Not API)
The X API v2 Basic tier costs $200/month and caps bulk retrieval at ~800 recent bookmarks. For a personal system with an $11/month subscription and a historical backlog of thousands of bookmarks, the API is not a viable primary path.
Cookie-based Playwright automation uses the same authenticated session as a logged-in browser. It does not expose credentials beyond the user's local machine. It can retrieve the full historical backlog.
Extraction Strategy: GraphQL Interception (Preferred)
X uses internal GraphQL endpoints to load bookmarks. Intercepting these responses is more stable than DOM scraping because:
GraphQL responses are structured JSON (not subject to CSS class changes)
They contain richer data than what's visible in the DOM (media metadata, entity IDs, etc.)
A single GraphQL response can contain 20–40 tweets with full metadata
Implementation:
# Intercept GraphQL responses
page.on("response", handle_response)
async def handle_response(response):
    if "Bookmarks" in response.url and response.status == 200:
        data = await response.json()
        # Parse tweet objects from the GraphQL payload
        tweets = extract_tweets_from_graphql(data)
        store_raw(tweets)
Fallback: DOM Extraction
If GraphQL interception fails (schema changes), fall back to DOM extraction:
tweets = await page.query_selector_all('[data-testid="tweet"]')
for tweet in tweets:
    tweet_id = await extract_id_from_element(tweet)
    text = await tweet.query_selector('[data-testid="tweetText"]')
    ...
Scroll Loop
async def scroll_to_end(page):
    last_height = 0
    retries = 0
    MAX_RETRIES = 5
    while retries < MAX_RETRIES:
        await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
        await asyncio.sleep(random.uniform(1.5, 3.0))  # Human-like delay
        
        new_height = await page.evaluate("document.documentElement.scrollHeight")
        if new_height == last_height:
            retries += 1
        else:
            retries = 0
            last_height = new_height
Authentication
Cookies are loaded at session start. The extractor checks for auth state before scrolling. If the auth check fails (cookies expired), the run is aborted with a clear error message directing the user to refresh cookies.
async def check_auth(page):
    await page.goto("https://x.com/i/bookmarks")
    if "login" in page.url:
        raise AuthenticationError(
            "Session expired. Re-export cookies and update cookies.json."
        )
Anti-Detection Measures
Random delays between scrolls (1.5–3.0 seconds)
Human-like mouse movement patterns
Standard viewport dimensions (1280×800)
--disable-blink-features=AutomationControlled flag
No proxy rotation (personal-scale, single IP, low frequency)
Run rate: at most once per day; typically once per week
***Processing/Enrichment Architecture
URL Expansion
async def expand_url(short_url: str, cache: dict) -> ExpandedURL:
    if short_url in cache:
        return cache[short_url]
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.head(short_url, follow_redirects=True, timeout=5.0)
            real_url = str(response.url)
            title = await fetch_page_title(real_url, client)
            result = ExpandedURL(original=short_url, resolved=real_url, title=title)
            cache[short_url] = result
            return result
        except Exception:
            return ExpandedURL(original=short_url, resolved=short_url, title=None)
URL expansion results are cached in SQLite to avoid re-fetching on re-runs.
Thread Reconstruction
A tweet is part of a thread if in_reply_to_status_id references a tweet by the same author. Thread reconstruction walks the reply chain upward to the root, then orders tweets sequentially.
def reconstruct_thread(tweet_id: str, db: Database) -> list[Tweet]:
    chain = []
    current = db.get_tweet(tweet_id)
    
    while current:
        chain.append(current)
        if current.in_reply_to_status_id:
            parent = db.get_tweet(current.in_reply_to_status_id)
            if parent and parent.author_id == current.author_id:
                current = parent
            else:
                break
        else:
            break
    
    return list(reversed(chain))  # Root first
If parent tweets are not in the local database (not bookmarked), they are fetched via Playwright single-tweet navigation as a best-effort operation. Maximum chain depth: 20 tweets.
LLM Enrichment
Enrichment calls are batched and rate-limited. Each tweet is enriched independently. The enrichment result is stored in SQLite and does not modify the processed_bookmarks table — separation of concerns.
Prompt design:
System: You are a knowledge extraction assistant. Return only valid JSON. No preamble.
User: Extract structured metadata from this tweet.
Tweet: {tweet_text}
Author: @{username}
{linked_article_title_if_available}
Return JSON:
{
  "summary": "1-2 sentence description of the key insight or claim",
  "tags": ["tag1", "tag2"],  // 2-5 lowercase tags
  "entities": {
    "people": [],
    "organizations": [],
    "tools": [],
    "concepts": []
  },
  "topic": "one of: ai, theology, health, physics, music, tech, finance, other"
}
Provider configuration:
# config.py
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")  # "claude" | "ollama"
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
***Storage Architecture
SQLite Schema
-- Raw extractor output. Append-only. Never modified.
CREATE TABLE raw_bookmarks (
    tweet_id TEXT PRIMARY KEY,
    raw_json TEXT NOT NULL,           -- Complete GraphQL/DOM payload
    extracted_at TIMESTAMP NOT NULL,
    source TEXT NOT NULL              -- "graphql" | "dom" | "import"
);
-- Processed and normalized data.
CREATE TABLE processed_bookmarks (
    tweet_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    author_username TEXT,
    author_display_name TEXT,
    created_at TIMESTAMP,
    expanded_urls TEXT,               -- JSON array of {original, resolved, title}
    thread_id TEXT,                   -- NULL if standalone tweet
    thread_order INTEGER,             -- Position in thread (1-based)
    thread_text TEXT,                 -- Full concatenated thread if is_thread_root
    media_urls TEXT,                  -- JSON array
    is_thread_root BOOLEAN DEFAULT 0,
    processed_at TIMESTAMP NOT NULL,
    FOREIGN KEY (tweet_id) REFERENCES raw_bookmarks(tweet_id)
);
-- LLM enrichment results. Separate table — never blocks processing.
CREATE TABLE enrichments (
    tweet_id TEXT PRIMARY KEY,
    summary TEXT,
    tags TEXT,                        -- JSON array
    entities TEXT,                    -- JSON object
    topic TEXT,
    enriched_at TIMESTAMP,
    model TEXT,                       -- Which model produced this
    FOREIGN KEY (tweet_id) REFERENCES processed_bookmarks(tweet_id)
);
-- Thread metadata.
CREATE TABLE threads (
    thread_id TEXT PRIMARY KEY,       -- root_tweet_id
    tweet_count INTEGER,
    author_username TEXT,
    created_at TIMESTAMP
);
-- Sync state for incremental runs.
CREATE TABLE sync_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP
);
-- Keys: "last_sync_at", "last_tweet_id_seen", "total_extracted"
-- URL expansion cache.
CREATE TABLE url_cache (
    original_url TEXT PRIMARY KEY,
    resolved_url TEXT,
    page_title TEXT,
    cached_at TIMESTAMP
);
Vault Directory Structure
vault/
  _index/
    authors/
      paulg.md              # Author index note (auto-generated)
      karpathy.md
    topics/
      ai.md                 # Topic MOC note (auto-generated)
      theology.md
  2023/
    01/
      tweet_1234567890.md
    ...
  2024/
    ...
  2025/
    ...
  threads/
    thread_root_id.md       # Full reconstructed threads as single notes
Markdown Note Format
---
tweet_id: "1234567890"
author: "@username"
author_name: "Display Name"
date: 2024-03-15
url: "https://x.com/username/status/1234567890"
topic: "ai"
tags:
  - llm
  - safety
  - alignment
entities:
  people:
    - Andrej Karpathy
  organizations:
    - OpenAI
  tools:
    - GPT-4
  concepts:
    - RLHF
summary: "Karpathy argues that RLHF is fundamentally misaligned with true capability development, using an analogy to teaching by test-cramming."
is_thread: false
bookmarked_at: 2024-03-15
---
# Tweet by @username
Karpathy argues that RLHF is fundamentally misaligned...
[Full tweet text]
---
**Linked:** [Article Title](https://example.com/article)
[View on X](https://x.com/username/status/1234567890)
***Retrieval/Query Architecture
For MVP: Obsidian handles all retrieval. No additional layer needed.
Full-text search: Obsidian's native search across all vault files
Tag filtering: Obsidian tag panel (populated from frontmatter tags:)
Author browsing: Author index notes in _index/authors/
Topic browsing: Topic MOC notes in _index/topics/
Backlinks: Obsidian's native backlink panel (works from entity names in frontmatter)
Graph view: Obsidian's graph view shows note connections
Post-MVP semantic search (optional):
# cli.py: python cli.py embed
# Generates embeddings for all notes and stores in a local ChromaDB instance
# python cli.py query "what did I save about AI safety?"
***AI/LLM Integration Points
Stage	LLM Use	Required?	Provider
Enrichment	Summarization	No	Claude API or Ollama
Enrichment	Tag generation	No	Claude API or Ollama
Enrichment	Entity extraction	No	Claude API or Ollama
Post-MVP: Synthesis	Weekly topic synthesis note	No	Claude API
Post-MVP: Semantic Search	Embedding generation	No	Ollama (local)
Post-MVP: Author Index	Auto-write author profiles	No	Claude API
LLM never used for: extraction correctness, deduplication, URL resolution, thread reconstruction logic, storage operations.
***Failure Handling and Observability
Extraction Failures
Network timeout during scroll: retry up to 3 times, then checkpoint and stop. Next run resumes.
Auth failure (expired cookies): fail immediately, log clear instructions for cookie refresh.
Partial scroll (X rate-limits the session): store what was captured, log the count. Next run continues incrementally.
GraphQL schema change (parsing fails): fall back to DOM extractor. Log which fallback was used.
Processing Failures
URL expansion timeout: store original URL, log as warning. Continue.
Thread fetch 404 (deleted tweet): store partial thread, log as warning. Continue.
LLM enrichment API error: log and skip. The processed bookmark is stored without enrichment. Re-run enrichment stage later.
Observability
All runs write a structured log to logs/run_{timestamp}.jsonl with:
Stage name
Count of items processed / skipped / failed
Total duration
Any errors encountered
The sync_state table tracks:
Timestamp of last successful extraction
Total count of extracted tweets
Total count of processed notes
Total count of enriched notes
***Security and Secrets Handling
cookies.json: stored locally, added to .gitignore. Never committed. Contains full account session access.
ANTHROPIC_API_KEY: stored in .env, added to .gitignore.
.env: never committed. A .env.example with placeholder values is committed.
No credentials are passed to external services except the LLM API (optional) and X (implicit via browser session).
The SQLite database contains tweet content from the user's bookmarks. It should not be shared.
***Operational Concerns
Cookie Refresh:
Playwright cookies from x.com expire. Expect to refresh every 2–4 weeks. The CLI provides a helper command:
python cli.py export-cookies
This opens a headed browser, prompts the user to log in, and saves cookies to cookies.json.
Run Frequency:
Weekly incremental sync is sufficient for typical use. Running more than once per day is unnecessary and increases detection risk.
Database Backup:
SQLite database should be backed up before any major run. A single cp bookmarks.db bookmarks.db.bak is sufficient.
Vault Backup:
The vault directory should be committed to a private git repo or backed up to a local drive. Notes are idempotent — the vault can be regenerated from SQLite if lost.
***Extension Points / Replaceable Components
Component	Replacement Trigger	Replacement Path
GraphQL extractor	X changes GraphQL schema	Switch to DOM extractor; update `extract_tweets_from_graphql()`
DOM extractor	X changes data-testid attributes	Update selectors in `extractor/selectors.py`
Cookie auth	X requires stronger auth	Investigate username/password flow or token-based auth
Claude API enrichment	Cost or availability concern	Switch `LLM_PROVIDER=ollama` in .env
Obsidian vault	User switches to Logseq	Vault format is standard Markdown+YAML frontmatter — compatible
SQLite	Scale beyond 100K items + complex queries	Swap in DuckDB (same Python interface, better analytics)
Markdown export	User wants Notion/Roam	Write a new exporter module against processed_bookmarks table
