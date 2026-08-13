---
id: BI-001
title: Universal Source Ingestion for URL, Safari, and Research Imports
source: research/primitive
source_insight: >
  Leadership prep fails when high-value sources live outside the main extraction path; a bounded generic import layer lets one pipeline serve all sources.
opportunity: >
  Move from X-only ingestion to source-agnostic intake so bookmarks, URL shares, Safari folder exports, and research artifacts can all become one reusable leadership knowledge corpus.
why_now: >
  The current pipeline is mature through sprint-led leadership views; expanding source intake now turns the system from an X utility into a general personal intelligence layer for the director role.
minimal_impl: >
  Add a `source adapters` layer and three CLI entrypoints: `import-url`, `import-safari-folder`, and `import-research`. All adapters normalize into canonical rows with `source_name`, `source_type`, `source_item_id`, `source_ref`, and existing field compatibility. Preserve source-specific raw payloads as immutable files before normalization and keep downstream `enrich`/`export` untouched.
definition_of_done:
  - Ingest commands persist one immutable raw record per source input before any SQLite mutation.
  - The source-identity contract is explicit per adapter: `import-url` uses canonical URL identity, `import-safari-folder` uses folder-lineage-plus-URL identity, and `import-research` uses artifact-plus-item-locator identity.
  - Every normalized row exposes the shared identity fields `source_name`, `source_type`, `source_item_id`, `source_ref`, plus compatibility semantics `canonical_item_id = tweet_id` for X rows and `<source_name>:<source_type>:<source_item_id>` otherwise.
  - Whole-input failures stop before SQLite mutation; readable artifacts with some bad rows still import valid siblings and quarantine only the rejected records.
  - Malformed records are quarantined after raw capture with explicit rejection reasons and raw-provenance links instead of being guessed into canonical rows.
  - Each intake path can be replayed idempotently into SQLite without duplicate notes.
  - Existing X exports and derived artifacts keep current `tweet_id`-based note paths and backlinks, while mixed-source rows flow through downstream stages without source-specific conditionals.
  - `sync`, `export`, `topics`, `metadata`, `synthesize`, and `collections` operate on imported source rows without source-specific conditionals.
  - A review command can list one canonical provenance map for each imported item (source_name, source_type, source_item_id, source_ref).
effort: M
build_recipe: builder_safe
priority: now
dependencies:
  - BI-001 is the prerequisite for source-layer expansion
risks: >
  1. Ingestion of noisy or malformed research exports can pollute signal quality.
  2. Safari and third-party formats can be inconsistent.
  3. URL import may introduce non-idempotent duplicates if source_id normalization is weak.
mitigations: >
  1. Add strict source schema normalization and validation plus quarantine paths.
  2. Use format-specific parsers with explicit fallback fields and preserve unknown fields in raw payload JSON.
  3. Define deterministic source identifiers per adapter and include source_item_id in dedupe checks: canonical URL for `import-url`, folder lineage plus canonical URL for `import-safari-folder`, and artifact identity plus item locator for `import-research`.
tags:
  - sources
  - ingestion
  - backlog
  - architecture

# RUNTIME FIELDS
status: candidate
created_at: 2026-04-08T14:00:00Z
created_by: AI-Iteration
token_cost: 0

# CURATOR FIELDS
approved_at: ~
approved_by: ~
notes: ~

# BUILDER FIELDS
implemented_at: ~
implemented_by: ~
pr_url: ~
---

## Why this is valuable
The existing workflow is already optimized for one source. Extending intake, without changing enrichment/export/synthesis contracts, unlocks broad reuse of the same leadership layer for web intelligence and curated research.

## Initial implementation sketch
- Add source adapter dispatch in extraction path with explicit `x_bookmarks`, `single_url`, `safari_export`, `research_artifact`.
- Introduce canonical source contract in normalizer and schema compatibility keys.
- Add import validators and raw archive naming by source adapter and run date.
- Add docs + examples for each import command in `using-leeKnowledge.md`.
