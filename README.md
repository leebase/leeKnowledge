# leeKnowledge

Local-first pipeline for turning X/Twitter bookmarks into a durable Markdown
knowledge base.

## What It Is

The project extracts bookmarks from `x.com/i/bookmarks`, saves immutable raw
JSON, normalizes into SQLite, enriches bookmarks with LLM-generated metadata,
and exports Markdown notes that work well in Obsidian or any text editor.

## Current State

The repository now includes the first end-to-end MVP pipeline in code:
- `extract` launches Chrome against a logged-in profile, captures X bookmark GraphQL payloads, writes an immutable raw archive, normalizes the payloads, and inserts canonical rows into SQLite with tweet-id deduplication.
- `enrich` expands URLs, validates structured LLM output, and stores versioned enrichment rows with null-placeholder handling on failure.
- `export` renders Markdown notes from SQLite into the vault path contract under `vault/YYYY/MM/<slug>-<tweet_id>.md`.
- `sync` orchestrates `extract → enrich → export` in order.
- Raw archives live under `data/raw/` and the local SQLite database lives under `state/app.db`.

The current follow-up work is Sprint 5 hardening:
- make export fail read-only when the SQLite database is missing instead of bootstrapping state
- escape Markdown-sensitive source text and link metadata so notes preserve source fidelity
- rerun verification in the documented Python 3.12+ dev environment

## Development Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
```

## Verify The Scaffold

```bash
PYTHONPATH=src python3 -m leeknowledge --help
PYTHONPATH=src pytest
```

## Extraction Configuration

`extract` expects a real Chrome profile that is already logged in to X.

You can configure a run with flags or environment variables:
- `--chrome-profile-dir` / `LEEKNOWLEDGE_CHROME_PROFILE_DIR`
- `--raw-output-dir` / `LEEKNOWLEDGE_RAW_DIR`
- `--db-path` / `LEEKNOWLEDGE_DB_PATH`
- `--headless` / `LEEKNOWLEDGE_HEADLESS`

Example:

```bash
PYTHONPATH=src python3 -m leeknowledge extract \
  --chrome-profile-dir "$HOME/Library/Application Support/Google/Chrome" \
  --raw-output-dir data/raw \
  --db-path state/app.db
```

If Chrome is not authenticated, extraction stops with a readable error before any bookmark rows are inserted. When no bookmark payloads are captured, the raw archive is still written and the run stops before SQLite inserts.

## CLI Commands

- `python -m leeknowledge extract` — live Sprint 2 extraction slice
- `python -m leeknowledge enrich` — live Sprint 3 command for un-enriched bookmarks only
- `python -m leeknowledge export` — live Sprint 4 command that renders the Markdown vault from SQLite
- `python -m leeknowledge sync` — live Sprint 4 orchestration command that runs extract → enrich → export in order

### Enrichment Configuration

`enrich` reads `config/llm.yaml` through `lee-llm-router` and routes the `enricher` role through the pi harness.

Operator guidance:
- Keep provider, model, temperature, and timeout settings in `config/llm.yaml`.
- Optional page metadata fetch is best effort; missing metadata should not block persistence.
- Existing enrichment rows stay unchanged on rerun.
- Malformed JSON or validation failures should write the null enrichment placeholder instead of inventing values.
- If you run the full workflow through Agent-Orch and need a specific Pi model, pin the run with `AGENT_ORCH_PI_MODEL=<model>` because per-step model selection is not available yet.

## Local-Only Files

- `data/raw/` keeps immutable extraction archives; same-day reruns create a timestamp-suffixed sibling instead of overwriting
- `state/app.db` stores normalized bookmarks and enrichments
- `vault/YYYY/MM/<slug>-<tweet_id>.md` holds generated Markdown notes for Obsidian; export reruns replace the same file atomically
- `config/llm.yaml` stays untracked for local LLM routing config

## Manual Obsidian Check

After an export run, open the vault root in Obsidian and spot-check one sample note:

- confirm the note path matches `YYYY/MM/<slug>-<tweet_id>.md`
- verify the frontmatter includes the expected source and enrichment fields
- check that tweet text, resolved links, and the back-link to X are visible
- make sure the note remains readable in both preview and source modes

## Updating Templates

To pull the latest AgentFlow templates into this project without overwriting your custom data, run:

```bash
init-agent --update
```

This will automatically detect the Python profile and refresh only the contract files: `AGENTS.md` and `skills/*`. Living project-memory files such as `context.md` and `WHERE_AM_I.md` are preserved.

---

Created on 2026-04-07 by Lee Harrington.
