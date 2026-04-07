## 5. skills.md

**Skill: `selector-hardener`**
* **Purpose:** Create resilient scraping selectors.
* **Input:** HTML block from X.
* **Output:** Robust CSS/Xpath selectors that avoid frequently changed obfuscated classes (e.g., preferring `data-testid`).

**Skill: `thread-stitcher`**
* **Purpose:** Logic to group tweets by `conversation_id`.
* **Logic:** Sort by timestamp, identify the "Root" tweet, and concatenate text for LLM processing.

**Skill: `markdown-vault-architect`**
* **Purpose:** Define Obsidian-ready templates.
* **Output:** Markdown files with YAML frontmatter containing: `source_url`, `author`, `created_at`, `tags`, `summary`.

**Skill: `semantic-query-builder`**
* **Purpose:** Convert natural language into ChromaDB vector searches.
* **Guardrail:** Must prioritize "Date" and "Author" filters before semantic similarity to ensure accuracy.
