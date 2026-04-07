## 1. product-definition.md

**Product Overview**
A personal, automated pipeline that transforms X/Twitter bookmarks into a structured, searchable, and AI-enriched Markdown knowledge base.

**Problem Statement**
X bookmarks are a "data graveyard." They are difficult to search, threads are often fragmented, linked content is not archived, and the data is locked behind a platform that limits historical access.

**Goals**
* **Automated Recovery:** Extract 100% of historical and new bookmarks.
* **Thread Coherence:** Automatically reconstruct multi-post threads into single documents.
* **Contextual Enrichment:** Use AI to summarize, tag, and link related bookmarks.
* **Durability:** Store everything in local, human-readable Markdown.

**Non-Goals**
* Mass-scraping of non-bookmarked accounts.
* Social features or resharing to X.
* Real-time "firehose" monitoring.

**Core User Journey**
1.  **Sync:** System triggers a Playwright scroll-session using Lee's session cookies.
2.  **Ingest:** Raw JSON is saved to `/archive/raw`.
3.  **Process:** System detects threads, expands URLs, and fetches linked webpage summaries.
4.  **Enrich:** Local LLM generates a "Context Card" (summary + tags).
5.  **Commit:** A new `.md` file appears in the Obsidian Vault.

**Definition of Done (MVP)**
* Successful extraction of >500 historical bookmarks.
* Automatic conversion to Markdown with YAML frontmatter.
* Working semantic search over the local vault.

---
