# Using leeKnowledge

This guide is for actually getting leeKnowledge running on your machine and using it with confidence.

It assumes:
- you are on macOS
- you have Chrome installed
- you are already logged into X in Chrome
- you want a local Obsidian-friendly knowledge vault

## What leeKnowledge Does

leeKnowledge turns saved signal into durable local knowledge artifacts:

1. `extract`
   Captures bookmark payloads from X and stores raw JSON plus normalized SQLite rows.
2. `import-url`
   Imports one or more explicit URLs through the shared source-intake contract.
3. `import-safari-folder`
   Imports Safari bookmarks from a local `Bookmarks.plist` export.
4. `import-research`
   Imports a research artifact from JSON, JSONL, CSV, Markdown, or text.
5. `enrich`
   Expands URLs and adds summaries, tags, entities, and topic metadata.
6. `export`
   Renders per-bookmark Markdown notes into your vault.
7. `topics`
   Generates four deterministic topic index notes from existing local state.
8. `metadata`
   Generates one small leadership-triage judgment row per eligible bookmark from existing local state.
9. `synthesize`
   Generates a weekly leadership brief for one explicit ISO week after bookmark notes and topic notes already exist.
10. `collections`
   Generates initiative-centered collection notes from existing local state plus checked-in initiative definitions.
11. `sync`
   Runs the core X pipeline in order: extract → enrich → export.

Core local state:
- SQLite DB: `state/app.db`
- Raw captures: `data/raw/`
- Markdown vault: `vault/`

## First-Time Setup

### 1. Create and activate the Python environment

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium
```

### 2. Confirm the CLI is available

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge --help
```

You should see:
- `extract`
- `import-url`
- `import-safari-folder`
- `import-research`
- `enrich`
- `export`
- `topics`
- `metadata`
- `synthesize`
- `collections`
- `sync`
- `db`

### 3. Set up the local LLM config

Copy the example config into place:

```bash
cp config/llm.example.yaml config/llm.yaml
```

Then edit `config/llm.yaml` to match the model/provider setup you want to use locally.

Important:
- `config/llm.yaml` is local-only and should stay uncommitted.
- enrichment depends on this file
- extraction and DB initialization do not

### 4. Make sure Chrome is ready

Before your first extract or sync:
- open Chrome normally
- confirm you are logged into X
- confirm `https://x.com/i/bookmarks` loads in that browser profile

To target one folder, open that folder in X first and copy its URL.
You can then pass it with `--bookmarks-url` to `extract` or `sync`.

If you use a non-default Chrome profile, be ready to pass:
- `--chrome-profile-dir`

Typical macOS value:

```bash
$HOME/Library/Application Support/Google/Chrome
```

## Recommended First Run

### Option A: Full pipeline

If your LLM config is ready and you want the full experience:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge sync \
  --chrome-profile-dir "$HOME/Library/Application Support/Google/Chrome"
```

What should happen:
- raw bookmark payloads are captured into `data/raw/`
- normalized bookmarks are written into `state/app.db`
- un-enriched bookmarks are processed
- bookmark notes are written into `vault/YYYY/MM/`

Then generate the topic layer explicitly:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
```

That command should write exactly four derived notes into `vault/topics/`:
- `ai-governance.md`
- `enterprise-agents.md`
- `data-platform.md`
- `vendor-landscape.md`

Generate the leadership metadata layer explicitly when you want triage judgments refreshed:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge metadata
```

Then generate the weekly brief:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period 2026-W15
```

That flow writes:
- metadata rows in `state/app.db` table `leadership_metadata`
- canonical weekly archive: `vault/synthesis/weekly/2026/2026-W15.md`
- latest prep shortcut: `vault/briefs/latest-weekly-signals.md`

Then generate collections when you want initiative-centered working notes:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge collections
```

That step reads `playbooks/curated-collections.yaml` and writes one initiative note per active definition under `vault/collections/`.

### Option B: Stage by stage

If you want to go slower and inspect each stage:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge extract \
  --chrome-profile-dir "$HOME/Library/Application Support/Google/Chrome" \
  --bookmarks-url "https://x.com/i/bookmarks/your-folder"

PYTHONPATH=src .venv/bin/python -m leeknowledge enrich

PYTHONPATH=src .venv/bin/python -m leeknowledge export
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
PYTHONPATH=src .venv/bin/python -m leeknowledge metadata
PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period 2026-W15
PYTHONPATH=src .venv/bin/python -m leeknowledge collections
```

This is the better path if you are diagnosing a failure or validating output quality.
Recommended order stays: `export` first, then `topics`, then `metadata`, then `synthesize`, so each derived layer reads from already-materialized local state.
Add `collections` last when you want initiative-centered execution support.

### Option C: Start from non-X source intake

If the source is not an X bookmark, use one of the explicit import commands first, then continue with the same downstream stages.

Quick chooser:
- `import-url` — best when you can name the exact links up front and want canonical URL dedupe
- `import-safari-folder` — best when the Safari folder path is part of the provenance you want to keep
- `import-research` — best when one durable artifact file already contains the material you want to preserve

Operator preflight:
- decide whether URL canonicalization, folder lineage, or artifact path is the identity base you care about before importing anything
- keep the input URL/file path stable if you want reruns to dedupe cleanly
- inspect `data/raw/` first when the normalized result looks surprising; the raw snapshot is the source of truth for that run
- expect quarantine files for bad inputs instead of silent repairs

#### Import one or more explicit URLs

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge import-url \
  "https://example.com/insight" \
  "https://EXAMPLE.com/path?b=2&a=1#fragment" \
  --raw-output-dir data/raw \
  --db-path state/app.db
```

Use this when:
- you have copied links from email, chat, or a ticket and want them in the corpus immediately
- the source is a URL, not a bookmark export or research file
- you want the imported rows to flow through `enrich`, `export`, `topics`, `metadata`, `synthesize`, and `collections` like any other source note
- you do not need folder provenance or artifact-local row lineage

A practical post-import check:

```bash
find data/raw -type f | sort | tail -n 3
sqlite3 state/app.db "select source_name, source_type, source_ref from bookmarks order by rowid desc limit 5;"
```

Practical caveats:
- only absolute `http` and `https` URLs are accepted
- URL identity is canonicalized, so host casing, query-string order, and fragments do not create separate records
- re-importing `https://EXAMPLE.com/path?b=2&a=1#fragment` and `https://example.com/path?a=1&b=2` maps to the same canonical record
- the initial imported note text is just the canonical URL until later stages add more context
- invalid URLs are quarantined rather than guessed or repaired silently; if the CLI says quarantine was written, inspect the companion file in `data/raw/`
- if you want a specific URL to stay distinct from a tracker or redirect, import the final canonical destination you actually want to keep

#### Import Safari bookmarks from a folder export

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge import-safari-folder \
  --input "$HOME/Library/Safari/Bookmarks.plist" \
  --raw-output-dir data/raw \
  --db-path state/app.db
```

Use this when:
- you want a bounded Safari import instead of using X extraction
- your source bookmarks already exist in Safari and you want to preserve folder context
- you want each accepted bookmark item to become a normal source note downstream
- the folder path itself is part of why the bookmark matters
- you exported or pointed at a plist that already contains the exact folder tree you want to preserve

A practical post-import check:

```bash
find data/raw -type f | sort | tail -n 3
sqlite3 state/app.db "select source_name, source_type, source_ref from bookmarks where source_name='safari' order by rowid desc limit 5;"
```

Practical caveats:
- the current CLI expects a local Safari `Bookmarks.plist` file, not an HTML export
- bookmark identity includes folder lineage plus canonical URL, so moving the same URL to a different Safari folder can produce a different imported source record
- bookmarks without usable folder lineage are quarantined instead of being attached to an invented root folder
- raw provenance still lands in `data/raw/` before normalization, so inspect that first if the import result surprises you
- if you want one folder-focused import, prune or export the Safari bookmark set first; the current command reads the plist you point it at rather than interactively choosing folders
- if you only care about one subfolder, export a smaller plist for that folder instead of importing a giant library and hoping the lineage sorts itself out

#### Import a research artifact

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge import-research \
  ./research/deep-research-notes.md \
  --raw-output-dir data/raw \
  --db-path state/app.db
```

Other accepted examples:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge import-research ./research/vendor-scan.json
PYTHONPATH=src .venv/bin/python -m leeknowledge import-research ./research/signals.csv
PYTHONPATH=src .venv/bin/python -m leeknowledge import-research ./research/signals.jsonl
```

Use this when:
- you already have notes or exported research outside leeKnowledge
- the source is a structured file rather than a single URL
- you want one import pass to capture many research rows before enrichment and export
- you want accepted rows to preserve artifact-local provenance instead of being flattened into ad hoc manual links
- the file itself is the thing you want to keep stable over time, not just the text inside it

A practical post-import check:

```bash
find data/raw -type f | sort | tail -n 3
sqlite3 state/app.db "select source_name, source_type, source_ref from bookmarks where source_name='research' order by rowid desc limit 5;"
```

Practical caveats:
- supported formats are JSON, JSONL, CSV, Markdown, and plain text
- a Markdown or text file is imported as one record, not split into many sections automatically
- JSON/JSONL/CSV rows still need readable text or URL content; unreadable rows are quarantined
- research record identity includes the artifact path plus a row locator, so rerunning the same file at the same path is stable, but moving or renaming the file changes the identity base
- if a research file contains many weak rows, expect partial success: accepted rows are imported and rejected rows land in quarantine with explicit reasons instead of aborting the whole artifact
- if you want stable dedupe over time, avoid importing the same artifact from changing temp paths like `~/Downloads/...`
- a plain-text export is a good fit for one memo or briefing, but not for a folder of mixed notes unless you are okay with one record per file

#### Continue the downstream pipeline after import

After any non-X import path, continue with the same local stages:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge enrich
PYTHONPATH=src .venv/bin/python -m leeknowledge export
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
PYTHONPATH=src .venv/bin/python -m leeknowledge metadata
PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period 2026-W15
PYTHONPATH=src .venv/bin/python -m leeknowledge collections
```

## How To Initiate leeKnowledge On a New Machine

Use this checklist in order:

1. Clone the repo.
2. Create `.venv` with Python 3.12.
3. Install `.[dev]`.
4. Install Playwright Chromium.
5. Copy `config/llm.example.yaml` to `config/llm.yaml`.
6. Confirm Chrome is logged into X.
7. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge --help`.
8. Choose your intake path:
   - X bookmarks: `PYTHONPATH=src .venv/bin/python -m leeknowledge sync --chrome-profile-dir "...Chrome"`
   - X bookmark folder: `PYTHONPATH=src .venv/bin/python -m leeknowledge sync --chrome-profile-dir "...Chrome" --bookmarks-url "https://x.com/i/bookmarks/your-folder"`
   - explicit URLs: `PYTHONPATH=src .venv/bin/python -m leeknowledge import-url "https://example.com/insight"`
   - Safari bookmarks: `PYTHONPATH=src .venv/bin/python -m leeknowledge import-safari-folder --input "$HOME/Library/Safari/Bookmarks.plist"`
   - research artifact: `PYTHONPATH=src .venv/bin/python -m leeknowledge import-research ./research/deep-research-notes.md`
9. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge enrich` if you want LLM summaries and metadata for imported sources.
10. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge export`.
11. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge topics`.
12. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge metadata`.
13. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period YYYY-Www`.
14. Run `PYTHONPATH=src .venv/bin/python -m leeknowledge collections`.
15. Open `vault/` in Obsidian and inspect a few source notes, the generated topic notes, the latest weekly brief, and any collection notes you generated.

## Day-to-Day Usage

### Refresh your knowledge vault

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge sync \
  --chrome-profile-dir "$HOME/Library/Application Support/Google/Chrome" \
  --bookmarks-url "https://x.com/i/bookmarks/your-folder"
```

Use this when you want the X source pipeline current.
Then run `PYTHONPATH=src .venv/bin/python -m leeknowledge topics` to refresh the derived topic layer.
Then run `PYTHONPATH=src .venv/bin/python -m leeknowledge metadata` to refresh leadership-triage judgments.
Then run `PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period YYYY-Www` for the specific week you want to review.
Then run `PYTHONPATH=src .venv/bin/python -m leeknowledge collections` to turn the refreshed signal stack into initiative notes for live strategic work.

### Import explicit URLs without touching X

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge import-url \
  "https://example.com/insight" \
  "https://example.com/vendor-update" \
  --raw-output-dir data/raw \
  --db-path state/app.db
```

Use this when:
- you saved links somewhere other than X
- you want a fast manual intake path
- you want imported URLs to dedupe by canonical URL rather than exact string formatting

Watch for:
- non-absolute URLs are rejected into quarantine
- repeated imports of the same canonical URL insert zero new rows even if the command input uses different formatting
- these imports do not open a browser or require an X session

### Import Safari bookmarks without touching X

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge import-safari-folder \
  --input "$HOME/Library/Safari/Bookmarks.plist" \
  --raw-output-dir data/raw \
  --db-path state/app.db
```

Use this when:
- Safari already has the bookmark set you care about
- folder context matters and should stay part of provenance
- you want the imported bookmarks to feed the same downstream vault flow

Watch for:
- the CLI currently reads `Bookmarks.plist`
- root-level Safari bookmarks without folder lineage are quarantined
- reorganizing Safari folders can change source identity for the same URL because lineage is part of the identity key

### Import an external research artifact

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge import-research \
  ./research/deep-research-notes.md \
  --raw-output-dir data/raw \
  --db-path state/app.db
```

Use this when:
- you have exported research from another tool
- one file contains many rows or a durable memo you want preserved locally
- you want that artifact to feed the same enrich/export/topic/synthesis flow

Watch for:
- supported formats are `.json`, `.jsonl`, `.csv`, `.md`, `.markdown`, and `.txt`
- Markdown and text imports are one-record captures
- moving the source file to a different path changes the research artifact identity base on rerun

### Re-run only enrichment

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge enrich
```

Use this when:
- you changed prompts
- you changed model settings
- extraction already happened

### Re-render bookmark notes only

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge export
```

Use this when:
- you changed the bookmark-note template
- you want to rebuild the bookmark vault from SQLite only
- you want to avoid re-extracting from X

### Rebuild topic index notes only

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
```

Use this when:
- you changed topic taxonomy or grouping rules in code
- you changed the topic-note template or layout expectations
- you already have bookmark notes exported and want to refresh the derived leadership view

### Generate leadership metadata

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge metadata
```

Use this when:
- bookmark notes and topic notes are already current
- you want triage labels refreshed before generating a weekly brief
- you changed the metadata prompt, schema version, or rendering rules in code

Field meaning for operators:
- `strategic_relevance`: how strongly this item should compete for your attention right now versus later scan work
- `time_horizon`: whether the implication is immediate, next-quarter, or longer-term
- `organizational_impact`: whether the likely effect is local to your team, cross-functional, or company-wide
- `leadership_question`: one short follow-up prompt worth bringing into a meeting or planning discussion

Important constraints:
- these are derived judgments, not source facts
- missing or failed metadata should be treated as “not usable yet,” not as low importance
- Sprint 8 does not change exported bookmark-note frontmatter or topic-note layout
- weekly synthesis is the first place this metadata should become visible

### Generate a weekly leadership brief

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period 2026-W15
```

Use this when:
- you want one time-bounded leadership brief instead of scanning all topic notes manually
- bookmark notes and topic notes are already current for the week you care about
- if Sprint 8 metadata is available, you have refreshed it first
- you are preparing for a staff meeting, planning review, or vendor/risk discussion

Expected artifact locations:
- archived brief: `vault/synthesis/weekly/YYYY/YYYY-Www.md`
- latest shortcut: `vault/briefs/latest-weekly-signals.md`

Leadership-prep habit:
- open `vault/briefs/latest-weekly-signals.md` first
- use the linked archived week for the durable record
- treat metadata labels as triage aids, not replacements for evidence
- follow topic-note, bookmark-note, and X links when you need evidence

### Curated collections workflow

The checked-in initiative-definition file lives at `playbooks/curated-collections.yaml`.
The `collections` command uses it as the operator curation layer for initiative-centered notes.

How to curate initiatives well:
- keep the file to a small set of active workstreams, usually three to five
- make every `leadership_question` concrete enough that a generated note could help with a real meeting, decision, or prep thread
- use `topic_keys` to anchor the initiative to the existing four-topic taxonomy instead of inventing new categories
- use `metadata_preferences` to express what should rise within a candidate set, not to force evidence-free membership
- keep `max_items` bounded so the resulting note stays scan-friendly
- prefer initiative names like `ai-operating-model` or `data-platform-strategy` over vague buckets like `important-stuff`

How to connect external signal to live work:
1. refresh the source pipeline with `sync`
2. refresh `topics`, `metadata`, and the relevant weekly brief
3. review `playbooks/curated-collections.yaml` and tighten initiative questions or hints if the current work has shifted
4. generate collections
5. open the collection note first during prep for that initiative, then follow links outward to topic notes, bookmark notes, and original X posts

The intended outcome is not a second project tracker. It is a bounded initiative brief that helps you move from "I saw useful signal" to "I can use this signal in current strategic work."

### Initialize the database explicitly

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge db
```

Use this when you want the schema created before running other stages.

## What To Inspect After a Run

### Raw capture

Check that a raw archive exists:

```bash
find data/raw -type f | sort | tail
```

### SQLite state

Check bookmark and enrichment counts:

```bash
sqlite3 state/app.db "select count(*) from bookmarks;"
sqlite3 state/app.db "select count(*) from enrichments;"
```

### Exported notes

Check generated note paths:

```bash
find vault -type f | sort | head -n 20
```

You should see several layers today:
- source notes under `vault/YYYY/MM/`
- topic notes under `vault/topics/`
- archived weekly briefs under `vault/synthesis/weekly/YYYY/`
- latest brief shortcut under `vault/briefs/`
- collection notes under `vault/collections/`

The collections layer also depends on one checked-in initiative-definition source:
- definitions at `playbooks/curated-collections.yaml`

### Topic taxonomy expectations

Sprint 6 topic-note generation is intentionally narrow. It creates only:
- `ai-governance`
- `enterprise-agents`
- `data-platform`
- `vendor-landscape`

Important expectations:
- there is no `other` bucket
- uncategorized bookmarks remain source notes only
- a bookmark may appear in more than one topic note when deterministic rules match more than one topic
- topic assignment uses existing bookmark and enrichment fields only; `topics` does not call the LLM

### Obsidian check

Open the vault root in Obsidian and confirm:
- bookmark note paths look like `YYYY/MM/<slug>-<tweet_id>.md`
- topic note paths look like `topics/<topic-key>.md`
- bookmark-note frontmatter looks sane
- topic notes include Scope, Grouping hints, Recent bookmarks, and Generation notes
- each topic entry has both a bookmark-note backlink and a `View on X` link
- once weekly synthesis is generated, confirm the brief has a clear week label, topic movement, worth-discussing prompts, and source links
- confirm each collection note reads like initiative support rather than a generic topic dump
- notes read well in both source and preview mode

## Useful Environment Variables

- `LEEKNOWLEDGE_CHROME_PROFILE_DIR`
- `LEEKNOWLEDGE_RAW_DIR`
- `LEEKNOWLEDGE_DB_PATH`
- `LEEKNOWLEDGE_HEADLESS`
- `LEEKNOWLEDGE_LLM_CONFIG_PATH`
- `LEEKNOWLEDGE_VAULT_DIR`

Example:

```bash
export LEEKNOWLEDGE_CHROME_PROFILE_DIR="$HOME/Library/Application Support/Google/Chrome"
export LEEKNOWLEDGE_DB_PATH="state/app.db"
export LEEKNOWLEDGE_VAULT_DIR="vault"
```

Then:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge sync
```

## Failure Modes To Expect

### X login/auth failure

Symptoms:
- extraction fails early
- bookmarks page redirects

What to do:
- open Chrome manually
- log back into X
- retry `extract` or `sync`

### Missing `config/llm.yaml`

Symptoms:
- `enrich` fails before doing useful work

What to do:
- copy `config/llm.example.yaml` to `config/llm.yaml`
- verify the model/provider config

### Missing or stale SQLite DB on export

Symptoms:
- `export` fails with a readable DB/schema error

What to do:
- run `db` if you truly need a fresh empty schema
- run `extract` or `sync` if the DB is supposed to contain real data
- do not treat `export` as a DB initialization command

### Topic notes are empty or surprising

Symptoms:
- one or more topic notes have no bookmarks
- a bookmark you expected is uncategorized
- a topic note feels noisy

What to do:
- remember Sprint 6 only uses four fixed topics
- inspect the bookmark note and enrichment fields first
- re-run `export` before `topics` if bookmark-note backlinks are missing
- treat weak single-keyword matches as intentionally uncategorized rather than as a failure

### Notes look odd in Obsidian

What to do:
- inspect the raw Markdown file in `vault/`
- confirm whether the issue is source text, metadata, or template shape
- if needed, re-run only `export` after template changes

## Recommended Operating Rhythm

### Weekly

Current weekly operating rhythm for the X path:

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge sync \
  --chrome-profile-dir "$HOME/Library/Application Support/Google/Chrome"
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
PYTHONPATH=src .venv/bin/python -m leeknowledge metadata
PYTHONPATH=src .venv/bin/python -m leeknowledge synthesize --cadence weekly --period YYYY-Www
PYTHONPATH=src .venv/bin/python -m leeknowledge collections
```

If you started from `import-url`, `import-safari-folder`, or `import-research`, replace `sync` with the relevant intake command and keep the downstream order the same.
Use the generated `vault/briefs/latest-weekly-signals.md` note as the starting point for leadership prep that week.

### Monthly

- skim the vault for weak notes or tagging drift
- adjust the enrichment prompt/model if needed
- re-run `enrich` then `export`

### After bookmark-note template changes

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge export
```

### After topic-note template or taxonomy changes

```bash
PYTHONPATH=src .venv/bin/python -m leeknowledge topics
```

## Fastest Mental Model

If you only remember one thing, remember this:

- `sync` is your normal refresh command for source artifacts
- `export` rebuilds bookmark notes from SQLite
- `topics` rebuilds the derived topic layer from existing local state
- `metadata` adds a separate triage layer before weekly synthesis
- `synthesize` builds one weekly leadership brief from the current corpus for a requested ISO week
- `collections` turns the current signal stack into initiative-specific briefs
- `extract` is the brittle stage
- `data/raw/` is the provenance layer
- `state/app.db` is the system of record
- `vault/` is the human-facing output
