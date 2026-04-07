## 4. agents.md

**1. The Extraction Architect**
* **Purpose:** Maintain the brittle scraping logic.
* **Responsibilities:** Monitor X DOM changes; generate Playwright selectors; handle cookie-refresh logic.
* **Input:** X.com HTML snippets.
* **Output:** Updated Python/Playwright scraping functions.

**2. The Data Schema Guard**
* **Purpose:** Ensure normalization consistency.
* **Responsibilities:** Validating that raw JSON maps correctly to the internal "Normalized" format; handling edge cases (polls, deleted tweets, age-restricted content).
* **Input:** Raw Scraped JSON.
* **Output:** Pydantic models/Validation reports.

**3. The Pipeline Orchestrator (Codex Support)**
* **Purpose:** Guide the assembly of the Python services.
* **Responsibilities:** Ensuring modularity; managing the handoff between the Extractor and the Librarian.
* **Boundary:** Does not write the scraping selectors; focuses on logic flow.

---
