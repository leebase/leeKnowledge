## 3. project-plan.md

**Strategy:** Build inside-out. Secure the data first, then make it smart.

**Phase 0: Proof of Extraction (The "Gating" Phase)**
* Build Playwright script to successfully login via `cookies.json`.
* Verify infinite scroll can reach 100+ items without a 429 error.

**Phase 1: Ingestion MVP**
* Schema definition for "Normalized Tweet."
* Basic JSON-to-Markdown converter.
* Local folder structure: `/inbox`, `/archive`, `/vault`.

**Phase 2: Enrichment & URL Expansion**
* Integrate `Aiohttp` for parallel URL unshortening.
* Connect Ollama (local) for basic 1-sentence summaries.

**Phase 3: The "Second Brain" (Vector/Search)**
* Implement ChromaDB indexing.
* Build a simple "Ask my Bookmarks" CLI or local UI.

**Phase 4: Optimization**
* Incremental sync logic (only scrape until the last known `tweet_id` is found).
* Automatic "Daily Synthesis" note generation.

---
