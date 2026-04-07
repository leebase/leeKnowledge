
Project plan · MD
Copy

project-plan.md
Project Strategy
Approach: Phased, validation-gated delivery. Each phase must produce a working, testable artifact before the next begins. No phase is "plumbing for the real work later." Every phase delivers real value.

Builder: Codex as primary implementer, Lee as architect-director. Codex executes within bounded tasks defined by phase specs. Lee validates at each gate.

Risk Management: The extraction layer is treated as Phase 0's entire purpose. Nothing else begins until extraction is proven reliable against the real X account.

Total Estimated Duration: 4–6 weeks to a fully functional personal knowledge base. Each phase is approximately 1 week of Codex-driven work with validation gates between phases.

Phase 0: Proof of Extraction Feasibility
Goal: Prove that cookies-based Playwright can reliably extract bookmarks from Lee's real X account and produce parseable raw data.

Duration: 2–3 days

Deliverables:

Working Playwright script that:
Loads cookies from cookies.json
Navigates to x.com/i/bookmarks
Scrolls and intercepts GraphQL responses
Outputs raw JSON to stdout or a file
Cookie export helper script or documented manual process
A sample of 50+ real bookmarks in raw JSON
Validation Gate:

 Script successfully authenticates without error
 Script captures at least 50 bookmarks in a single run
 Raw JSON contains: tweet_id, text, author, timestamp, URLs
 Script handles auth failure gracefully (expired cookies → clear error message)
 Scroll loop terminates cleanly when no more bookmarks load
Success = Proceed to Phase 1 Failure = Fix extraction before anything else

Phase Risks:

X has updated GraphQL schema since last tested OSS tool → fall back to DOM extraction
Playwright detection triggers rate limit → add delays, reduce scroll speed
Cookies don't contain all required tokens → document additional token capture
Phase 1: Ingestion MVP
Goal: Store all bookmarks in SQLite reliably. Full historical backlog + deduplication + incremental mode working.

Duration: 3–4 days

Deliverables:

SQLite schema implemented (raw_bookmarks, sync_state, url_cache)
CLI command: python cli.py extract [--incremental]
Deduplication logic (tweet_id as primary key)
Progress logging to console (count extracted, count skipped/duplicate)
Structured run log to logs/
Incremental mode: reads last_tweet_id_seen from sync_state, stops scrolling when that ID is encountered
Validation Gate:

 Full extraction run captures all bookmarks (compare count to X's displayed count)
 Re-running extract on same data adds zero duplicates
 Incremental run captures only bookmarks newer than last sync
 Extraction failure midway leaves existing data intact
 Run log file is written with accurate counts
Phase Risks:

X's displayed bookmark count is inaccurate → document discrepancy, proceed
Incremental mode misses bookmarks if X bookmark ordering is non-chronological → add fallback full-scan mode
Phase 2: Normalization and Storage
Goal: Transform raw SQLite data into clean, normalized processed records. URL expansion, thread reconstruction, text normalization.

Duration: 4–5 days

Deliverables:

CLI command: python cli.py process
processed_bookmarks table populated from raw_bookmarks
URL expansion with caching (url_cache table)
Thread reconstruction with SQLite threads table
Text normalization (HTML entities, Unicode)
CLI command: python cli.py export → writes Markdown files to vault directory
Vault organized by year/month, one note per standalone tweet or thread root
YAML frontmatter on every note with: tweet_id, author, date, url, tags (empty), entities (empty)
Validation Gate:

 Every raw_bookmark has a corresponding processed_bookmark
 URLs in notes are resolved (t.co links expanded)
 Thread notes concatenate the full thread text in correct order
 Vault opens in Obsidian without errors
 All notes are navigable by date (year/month folder structure correct)
 Re-exporting regenerates notes identically (idempotency check)
Phase Risks:

Thread parent tweets not in raw data → fetch on demand; implement timeout/retry; store partial threads with note in frontmatter
URL expansion hangs → enforce 5-second timeout per URL; cap parallel fetches at 10
t.co URLs redirect to paywalled content → store title only; don't attempt content extraction
Phase 3: LLM Enrichment
Goal: Add optional AI-powered summarization, tagging, and entity extraction. Wire to both Claude API and local Ollama.

Duration: 3–4 days

Deliverables:

CLI command: python cli.py enrich [--provider claude|ollama] [--limit N]
enrichments table populated
Provider abstraction: LLMProvider interface with ClaudeProvider and OllamaProvider implementations
Prompt template with JSON output schema
Enrichment re-export: python cli.py export reads enrichments and adds summary/tags/entities to frontmatter
Author index notes auto-generated at _index/authors/{username}.md
Topic MOC notes auto-generated at _index/topics/{topic}.md
Validation Gate:

 Enrich command runs on 50 bookmarks without error
 Output JSON is valid and matches expected schema
 Tags appear in Obsidian tag panel
 Entities appear in frontmatter and are searchable
 Summaries are readable and accurate for a sample of 10 manually reviewed notes
 Ollama provider works as a drop-in replacement for Claude provider
 Enrichment can be re-run on same bookmarks; updates enrichments table; re-exports updated notes
Phase Risks:

LLM returns invalid JSON → implement retry with explicit JSON instruction; fall back to empty enrichment rather than fail
LLM summary quality is poor for short/cryptic tweets → acceptable; leave summary empty for low-confidence results
Ollama model is too slow for large batch → document expected throughput; add --limit flag to cap batch size
Phase 4: Operational Hardening
Goal: Make the system reliable enough for long-term personal use. Error handling, monitoring, documentation.

Duration: 2–3 days

Deliverables:

Cookie refresh helper: python cli.py export-cookies (headed Playwright window, saves cookies)
python cli.py sync command: runs extract → process → enrich → export in sequence with checkpoints
Vault backup reminder in run log when more than 7 days since last backup timestamp
README.md: setup guide, cookie export, first run, incremental sync, enrichment config
.env.example with all required and optional variables documented
Unit tests for: deduplication logic, URL expansion cache, thread reconstruction, Markdown frontmatter generation
Integration test: end-to-end run against a small fixture of 10 raw bookmark JSON samples
Validation Gate:

 README is complete enough that Lee can rebuild the system from scratch following only the README
 python cli.py sync runs without error on both first run and incremental run
 All unit tests pass
 Integration test passes
 System recovers correctly from: network timeout, expired cookies, LLM API failure
MVP Scope Summary
In MVP:

Full historical extraction via Playwright + GraphQL interception
Raw storage in SQLite
Processing: URL expansion, thread reconstruction, text normalization
Markdown export to Obsidian-compatible vault
Optional LLM enrichment (Claude API or Ollama)
Incremental sync
CLI interface
Author index notes and topic MOC notes
Out of MVP:

Semantic search / vector embeddings
Web UI
Browser extension for at-time-of-bookmark capture
Weekly synthesis reports
Backlink generation between notes
Notion / Readwise export
Post-MVP Scope
Priority-ordered:

Semantic search layer — Local Chroma or LanceDB + embedding model via Ollama. CLI command: python cli.py query "what did I save about X?"
At-time-of-bookmark capture — Browser extension that fires on X's bookmark action and sends to a local API endpoint. Eliminates need to scroll historical bookmarks going forward.
Weekly synthesis — Cron job that runs Claude against the week's new bookmarks and writes a synthesis note to the vault.
Backlink generation — Post-process enriched notes to find shared entities and add [[backlink]] references in Obsidian format.
Readwise export — Transform processed notes into Readwise CSV import format for users of that tool.
Testing Strategy
Unit Tests (Phase 4):

test_dedup.py: Verify tweet_id uniqueness constraint is enforced
test_url_expansion.py: Verify cache hit/miss behavior and timeout handling
test_thread_reconstruction.py: Verify correct ordering and partial thread handling
test_frontmatter.py: Verify YAML frontmatter is valid and fields are correct
test_llm_provider.py: Verify provider abstraction with mock responses
Integration Tests (Phase 4):

test_e2e.py: Run full pipeline against 10 fixture bookmark JSONs → verify Markdown output
Fixture data: sanitized samples from real extraction output, committed to test fixtures dir
Manual Validation Checkpoints:

After Phase 0: Visual inspection of raw JSON output
After Phase 2: Open vault in Obsidian, browse 20 notes, verify accuracy
After Phase 3: Review 10 enriched notes; check summary quality, tag relevance
After Phase 4: Run full sync from scratch on a fresh directory
Ongoing:

Monthly: Run sync and verify no extraction failures
Quarterly: Check if GraphQL/DOM extraction still works; update selectors if broken
Risks by Phase
Phase	Top Risk	Mitigation
0	X breaks GraphQL interception	DOM fallback extractor
1	Scroll loop misses bookmarks	Count verification; full-scan fallback
2	Thread parent fetch is slow	Per-tweet timeout; store partial threads
3	LLM JSON output is unreliable	Retry + empty fallback
4	Cookie refresh flow is confusing	Clear error messages + documented steps
Repo Structure
bookmarkbrain/
  cli.py                    # Entry point; Click commands
  config.py                 # .env loading, validation
  extractor/
    __init__.py
    playwright_extractor.py # Primary: GraphQL interception
    dom_extractor.py        # Fallback: DOM scraping
    selectors.py            # CSS selectors (update here when X changes)
    cookie_helper.py        # Cookie export utility
  db/
    __init__.py
    schema.py               # SQLite schema creation and migrations
    raw.py                  # Raw bookmark read/write
    processed.py            # Processed bookmark read/write
    enrichments.py          # Enrichment read/write
    state.py                # Sync state management
    url_cache.py            # URL expansion cache
  pipeline/
    __init__.py
    processor.py            # Normalization, URL expansion, threads
    enricher.py             # LLM enrichment orchestration
    exporter.py             # Markdown file generation
    llm/
      __init__.py
      base.py               # LLMProvider interface
      claude_provider.py    # Anthropic SDK
      ollama_provider.py    # Ollama HTTP client
  tests/
    fixtures/               # Sample raw bookmark JSON
    test_dedup.py
    test_url_expansion.py
    test_thread_reconstruction.py
    test_frontmatter.py
    test_e2e.py
  vault/                    # Generated; gitignored
  logs/                     # Run logs; gitignored
  bookmarks.db              # SQLite; gitignored
  cookies.json              # Never committed; gitignored
  .env                      # Never committed; gitignored
  .env.example              # Committed; shows required vars
  .gitignore
  README.md
  requirements.txt
  pyproject.toml
