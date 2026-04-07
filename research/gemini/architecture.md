## 2. architecture.md

**Design Principles**
1.  **Extraction Isolation:** The scraper is a "disposable" module.
2.  **Raw Data Sovereignty:** Never transform data without keeping the original JSON.
3.  **Offline-First:** The system must be fully queryable without an internet connection (using local LLMs/Embeddings).

**Major Components**
* **The Extractor (Playwright/Python):** Handles auth-session injection, infinite scroll, and GraphQL interception.
* **The Refiner:** A Python service that handles `t.co` expansion and thread "stitching" via `conversation_id`.
* **The Librarian (Enrichment):** Orchestrates Ollama for summarization and metadata generation.
* **The Vault:** A local directory of Markdown files + a ChromaDB vector index.



**Data Flow**
1.  **Scrape:** Playwright → `raw_{timestamp}.json`.
2.  **Normalize:** Python → `cleaned_{id}.json` (URLs expanded, threads merged).
3.  **Enrich:** Ollama (Llama 3) → Appends Summary/Tags to JSON.
4.  **Generate:** Template Engine → `{Title}.md` in Vault.
5.  **Index:** Sentence-Transformers → ChromaDB.

**Failure Handling**
* **DOM Change:** If selectors fail, the Extractor triggers an alert to the "Scraping Strategy Agent" to update selectors.
* **Rate Limit:** Exponential backoff (jittered) is baked into the Playwright loop.

---
