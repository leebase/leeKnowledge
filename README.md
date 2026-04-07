# leeKnowledge

Local-first pipeline for turning X/Twitter bookmarks into a durable Markdown
knowledge base.

## What It Is

The project extracts bookmarks from `x.com/i/bookmarks`, saves immutable raw
JSON, normalizes into SQLite, enriches bookmarks with LLM-generated metadata,
and exports Markdown notes that work well in Obsidian or any text editor.

## Current State

The product, architecture, and project plan are now defined. The repository is
currently at the Phase 1 scaffold stage:
- Lowercase Python package: `leeknowledge`
- CLI skeleton with `extract`, `enrich`, `export`, and `sync`
- SQLite schema bootstrap and deduplicating bookmark insert helper
- Tests for DB initialization and dedup behavior

The extraction, enrichment, and export implementations are still stubs.

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

## Planned Commands

- `python -m leeknowledge extract`
- `python -m leeknowledge enrich`
- `python -m leeknowledge export`
- `python -m leeknowledge sync`

## Local-Only Files

- `data/raw/` keeps immutable extraction archives
- `state/app.db` stores normalized bookmarks and enrichments
- `vault/` holds generated Markdown notes
- `config/llm.yaml` stays untracked for local LLM routing config

## Updating Templates

To pull the latest AgentFlow templates into this project without overwriting your custom data, run:

```bash
init-agent --update
```

This will automatically detect the Python profile and refresh only the contract files: `AGENTS.md` and `skills/*`. Living project-memory files such as `context.md` and `WHERE_AM_I.md` are preserved.

---

Created on 2026-04-07 by Lee Harrington.
