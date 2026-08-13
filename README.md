# leeKnowledge

Local-first pipeline for turning X/Twitter bookmarks into a durable Markdown
knowledge base.

## What It Is

The project extracts bookmarks from `x.com/i/bookmarks` by default, with optional
folder-scoped X URL support, saves immutable raw JSON, normalizes into SQLite,
enriches bookmarks with LLM-generated metadata,
and exports Markdown notes that work well in Obsidian or any text editor.

## Current State

The repository now includes the end-to-end MVP pipeline, the Level 2 leadership layers, and the first Sprint 10 source-intake commands:
- `extract` launches Chrome against a logged-in profile, captures X bookmark GraphQL payloads, writes an immutable raw archive, normalizes the payloads, and inserts canonical rows into SQLite with tweet-id deduplication.
- `import-url` imports one or more explicit URLs through the shared source-intake contract.
- `import-safari-folder` imports Safari bookmarks from a local `Bookmarks.plist` path while preserving folder-lineage provenance.
- `import-research` imports research artifacts from JSON, JSONL, CSV, Markdown, or text.
- `enrich` expands URLs, validates structured LLM output, and stores versioned enrichment rows with null-placeholder handling on failure.
- `export` renders per-bookmark Markdown notes from SQLite into the vault path contract under `vault/YYYY/MM/<slug>-<tweet_id>.md`.
- `topics` generates four deterministic topic index notes at `vault/topics/<topic-key>.md` from existing local state only.
- `metadata` writes validated leadership-triage rows into `leadership_metadata` without changing bookmark-note export.
- `synthesize` generates a weekly leadership synthesis brief archived at `vault/synthesis/weekly/YYYY/YYYY-Www.md` with a leadership-prep shortcut at `vault/briefs/latest-weekly-signals.md`.
- `collections` generates initiative-centered notes under `vault/collections/<initiative-slug>.md` from the checked-in initiative definitions in `playbooks/curated-collections.yaml`.
- `sync` orchestrates `extract → enrich → export` in order; the topic, metadata, synthesis, collections, and non-X import layers remain separate explicit steps.
- Raw archives live under `data/raw/` and the local SQLite database lives under `state/app.db`.

Sprint 10 is the active slice: bounded universal source ingestion through explicit URL, Safari, and research-artifact imports while keeping downstream stages source-agnostic.

Sprint 5 hardening closed the first export review findings:
- `export` now fails read-only when the SQLite database is missing or missing required schema
- Markdown-sensitive source text and link metadata render without changing note structure
- verification has been rerun in a Python 3.12 dev environment with `.[dev]` installed

## Guides

- [using-leeKnowledge.md](/Users/lee/projects/leeKnowledge/using-leeKnowledge.md) — operator guide for setup, first run, and day-to-day usage
- [whats-next.md](/Users/lee/projects/leeKnowledge/whats-next.md) — vision document for how leeKnowledge could evolve to support Data and AI leadership

If you are starting fresh, read [using-leeKnowledge.md](/Users/lee/projects/leeKnowledge/using-leeKnowledge.md) first. It is the practical guide for initiating the project on a new machine and running your first successful `sync`, `import-url`, `import-safari-folder`, or `import-research` flow.

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
- `--bookmarks-url` / `LEEKNOWLEDGE_BOOKMARKS_URL`
- `--cdp-endpoint` / `LEEKNOWLEDGE_CHROME_CDP_ENDPOINT`

Example:

```bash
PYTHONPATH=src python3 -m leeknowledge extract \
  --chrome-profile-dir "$HOME/Library/Application Support/Google/Chrome" \
  --raw-output-dir data/raw \
  --db-path state/app.db
```

If Chrome is already running, pass an authenticated CDP endpoint from that window instead of fighting the profile lock:

```bash
# Start Chrome with remote debugging using a dedicated user data dir first (Chrome 136+ requirement)
open -a "Google Chrome" --args \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome-automation"

# Then run extract against that running session (endpoint can also be inferred automatically)
PYTHONPATH=src python3 -m leeknowledge extract \
  --cdp-endpoint "http://127.0.0.1:9222" \
  --bookmarks-url "https://x.com/i/bookmarks/your-folder"
```

To run extraction against a specific X bookmark folder, pass the folder URL from
X into `--bookmarks-url` (or set `LEEKNOWLEDGE_BOOKMARKS_URL`):

```bash
PYTHONPATH=src python3 -m leeknowledge extract \
  --bookmarks-url "https://x.com/i/bookmarks/your-folder"
```

### One-command folder sync + markdown export

Run a single script to extract from a folder URL, enrich, and export markdown:

```bash
./scripts/sync-bookmarks-folder.sh "https://x.com/i/bookmarks/your-folder"
```

The script uses your existing Chrome CDP session, defaults to
`http://127.0.0.1:9222`, and writes output to:
- `data/raw` (immutable raw capture)
- `state/app.db` (SQLite)
- `vault/` (exported markdown)

You can set environment overrides once and run with no args:

```bash
export LEEKNOWLEDGE_BOOKMARKS_URL="https://x.com/i/bookmarks/your-folder"
export CDP_ENDPOINT="http://127.0.0.1:9222"
export RAW_OUTPUT_DIR="data/raw"
export DB_PATH="state/app.db"
export VAULT_DIR="vault"

./scripts/sync-bookmarks-folder.sh
```

If Chrome is not authenticated, extraction stops with a readable error before any bookmark rows are inserted. When no bookmark payloads are captured, the raw archive is still written and the run stops before SQLite inserts.

## CLI Commands

- `python -m leeknowledge extract` — X bookmark extraction slice
- `python -m leeknowledge import-url <url> [<url> ...]` — explicit URL intake without using X or Safari
- `python -m leeknowledge import-safari-folder --input "$HOME/Library/Safari/Bookmarks.plist"` — Safari bookmark intake from a local plist export
- `python -m leeknowledge import-research ./research/deep-research-notes.md` — research-artifact intake from JSON, JSONL, CSV, Markdown, or text
- `python -m leeknowledge enrich` — un-enriched bookmark processing only
- `python -m leeknowledge export` — renders bookmark notes from SQLite under `vault/YYYY/MM/`
- `python -m leeknowledge topics` — generates deterministic topic index notes under `vault/topics/`
- `python -m leeknowledge sync` — runs extract → enrich → export in order for the X intake path; run later leadership layers explicitly after source artifacts are current
- `python -m leeknowledge metadata` — generates leadership-triage metadata from existing local state only
- `python -m leeknowledge synthesize --cadence weekly --period 2026-W15` — generates one weekly leadership brief after bookmark notes and topic notes exist
- `python -m leeknowledge collections` — generates initiative-centered collection notes from existing local state plus `playbooks/curated-collections.yaml`

### Source Intake Caveats

Use the explicit import commands when the source is not an X bookmark.

| Intake path | Best when | Watch for |
|-------------|-----------|-----------|
| `import-url` | You have a few specific links from chat, email, or notes and want them in the corpus now | URL identity is canonicalized, so formatting-only differences collapse to one record |
| `import-safari-folder` | Safari folder context is meaningful provenance and you exported a `Bookmarks.plist` on purpose | Folder lineage is part of identity, so reorganizing folders can create a different source record |
| `import-research` | One durable research file already contains the material you want to preserve | Artifact path is part of identity, so moving or renaming the file changes the identity base |

#### `import-url`

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge import-url \
  "https://example.com/insight" \
  "https://EXAMPLE.com/path?b=2&a=1#fragment" \
  --raw-output-dir data/raw \
  --db-path state/app.db

sqlite3 state/app.db "select source_name, source_type, source_ref from bookmarks order by rowid desc limit 5;"
```

Use it for a small number of links you want in the corpus immediately.
Caveats:
- accepts absolute `http`/`https` URLs only
- deduplicates by canonical URL, so fragments, host casing, and query-order changes do not create separate rows
- initial imported text is just the canonical URL until later stages add more context
- if the same link shows up in multiple places, import the final destination URL you actually want to keep, not a redirect or tracker URL

#### `import-safari-folder`

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge import-safari-folder \
  --input "$HOME/Library/Safari/Bookmarks.plist" \
  --raw-output-dir data/raw \
  --db-path state/app.db

sqlite3 state/app.db "select source_name, source_type, source_ref from bookmarks where source_name='safari' order by rowid desc limit 5;"
```

Use it when Safari folder context is part of why the bookmark matters.
Caveats:
- currently expects a Safari `Bookmarks.plist` file, not an HTML export
- folder lineage is part of identity, so reorganizing Safari folders can create a different imported record for the same URL
- entries without usable folder lineage are quarantined instead of being attached to an invented root folder
- if you only care about one subfolder, export a smaller plist for that folder instead of importing your entire library

#### `import-research`

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge import-research \
  ./research/deep-research-notes.md \
  --raw-output-dir data/raw \
  --db-path state/app.db

sqlite3 state/app.db "select source_name, source_type, source_ref from bookmarks where source_name='research' order by rowid desc limit 5;"
```

Use it for one durable research artifact at a time.
Caveats:
- accepts `.json`, `.jsonl`, `.csv`, `.md`, `.markdown`, and `.txt`
- Markdown/text import as one record, while structured rows without readable content are quarantined
- rerunning the same file at the same path is stable, but moving or renaming the file changes the identity base
- partial success is normal for mixed-quality artifacts: accepted rows import, rejected rows go to quarantine with explicit reasons
- if the artifact is just a memo or briefing, keep it as one file; if it is a mixed export from a folder, expect record-by-record quarantine rather than a silent repair

All three import paths write immutable raw archives before normalization and may also write a quarantine file when some records are rejected.

After any import path, the practical next commands are:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge enrich
PYTHONPATH=src .venv/bin/python -m leeknowledge export
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
PYTHONPATH=src .venv/bin/python -m leeknowledge metadata
PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period 2026-W15
PYTHONPATH=src .venv/bin/python -m leeknowledge collections
```

Downstream stages stay source-agnostic.

For more step-by-step flows and post-import checks, see [using-leeKnowledge.md](/Users/lee/projects/leeKnowledge/using-leeKnowledge.md).

### Topic Index Notes

`topics` is the first leadership-oriented derived view.

Current taxonomy:
- `ai-governance`
- `enterprise-agents`
- `data-platform`
- `vendor-landscape`

Operator expectations:
- topic notes are generated from existing SQLite bookmark/enrichment state only
- no new LLM call is made during topic generation
- bookmark notes remain the source artifacts; topic notes are generated indexes
- each topic entry links to both the source bookmark note and the original X post
- re-running `topics` updates the same four files in place

### Weekly Leadership Briefs

Sprint 7's synthesis layer is intentionally narrow:
- weekly only for the first slice
- operator supplies an explicit ISO week like `2026-W15`
- canonical archive path is `vault/synthesis/weekly/YYYY/YYYY-Www.md`
- leadership-prep shortcut is `vault/briefs/latest-weekly-signals.md`
- the brief is derived from both Sprint 6 topic membership and the underlying SQLite bookmark/enrichment rows
- source traceability must link back to topic notes, bookmark notes, and original X posts

Current operator cadence:
1. `sync` to refresh raw bookmarks, SQLite rows, and bookmark notes
2. `topics` to refresh the topic layer
3. `metadata` to refresh leadership-triage judgments from current local state
4. `synthesize --cadence weekly --period YYYY-Www` for the week you want to review
5. open `vault/briefs/latest-weekly-signals.md` first when preparing for a leadership conversation
6. run `collections` to turn the current signal stack into initiative-centered notes under `vault/collections/`

The weekly brief contract is meant to answer "what mattered this week?" without forcing you to scan every bookmark or every topic note manually.

### Leadership Metadata

Sprint 8's metadata layer stays small on purpose. It adds four fields per eligible bookmark:
- `strategic_relevance` — how strongly the item should compete for leadership attention: `monitor`, `important`, or `strategic`
- `time_horizon` — when the item is most likely to matter operationally: `now`, `next-quarter`, or `longer-term`
- `organizational_impact` — how broad the likely effect is: `team`, `cross-functional`, or `company-wide`
- `leadership_question` — one short decision-oriented prompt to use only when the bookmark is strong enough to justify discussion framing

Operator meaning:
- these are triage labels, not scores or facts about the source material
- metadata lives in SQLite as a separate derived table and can be regenerated independently
- bookmark-note export under `vault/YYYY/MM/` stays unchanged
- topic notes under `vault/topics/` also stay unchanged
- weekly synthesis is the first consumer, showing compact labels and optional questions only for validated, evidence-backed items

### Curated Collections

The curated collection layer is for live strategic work rather than broad theme review.

Current checked-in initiative definitions live in `playbooks/curated-collections.yaml`:
- `ai-operating-model`
- `data-platform-strategy`
- `vendor-watchlist`

Operator expectations for curated collections:
- the YAML file is the only required manual curation layer
- each initiative should name a real leadership question, a short scope note, and bounded hints such as topic keys, metadata preferences, recency window, and max note size
- collection notes should stay selective and evidence-backed instead of becoming project trackers or generic topic dumps
- the collection generator reads existing bookmark notes, topic membership, weekly brief context, and validated metadata without requiring a new LLM pass
- every surfaced item should explain why it is present through visible inclusion reasons such as topic fit, metadata fit, tag fit, or recent weekly mention

Operator flow for live initiative support:
1. run `sync` or one of the explicit import commands to refresh source notes
2. run `topics` to refresh the theme layer
3. run `metadata` to refresh triage labels
4. run `synthesize --cadence weekly --period YYYY-Www` for current leadership context
5. run `collections` to produce `vault/collections/<initiative-slug>.md`
6. use the generated collection note as the working bridge from external signal to an active initiative, then drill back into bookmark notes and source links as needed

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
- `state/app.db` stores normalized bookmarks, enrichments, and leadership metadata
- `vault/YYYY/MM/<slug>-<tweet_id>.md` holds generated bookmark notes for Obsidian; export reruns replace the same file atomically
- `vault/topics/<topic-key>.md` holds generated topic index notes; `topics` reruns replace the same four files atomically
- `state/app.db` also holds the `leadership_metadata` table; `metadata` reruns update at most one current row per `tweet_id`
- `vault/synthesis/weekly/YYYY/YYYY-Www.md` is the canonical archive for weekly leadership briefs
- `vault/briefs/latest-weekly-signals.md` is the operator shortcut for leadership prep and should point to the latest generated weekly brief
- `playbooks/curated-collections.yaml` is the checked-in initiative-definition source for curated collections
- `vault/collections/<initiative-slug>.md` is the stable output path for curated initiative notes
- `config/llm.yaml` stays untracked for local LLM routing config

## Manual Obsidian Check

After an `export` then `topics` run, open the vault root in Obsidian and spot-check:

- one bookmark note under `YYYY/MM/<slug>-<tweet_id>.md`
- one topic note under `topics/<topic-key>.md`
- verify the bookmark note still carries the expected source and enrichment fields
- verify the topic note declares itself as a generated view and includes Scope, Grouping hints, Recent bookmarks, and Generation notes sections
- check that every topic entry links to both the bookmark note and the original X post
- open `vault/briefs/latest-weekly-signals.md` and confirm it is the fastest starting point for leadership prep
- confirm weekly cited items show compact metadata labels only where the source evidence is present and current
- confirm each collection note has a clear leadership question, visible inclusion reasons, and easy jumps back to source notes
- make sure all generated note types remain readable in preview and source modes

## Updating Templates

To pull the latest AgentFlow templates into this project without overwriting your custom data, run:

```bash
init-agent --update
```

This will automatically detect the Python profile and refresh only the contract files: `AGENTS.md` and `skills/*`. Living project-memory files such as `context.md` and `WHERE_AM_I.md` are preserved.

---

Created on 2026-04-07 by Lee Harrington.
