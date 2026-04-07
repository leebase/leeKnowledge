# product-definition.md

## Product overview

**Working name:** `bookmark-vault`

`bookmark-vault` is a local-first system that turns a user’s saved X/Twitter bookmarks into an inspectable personal knowledge base.

The product accepts bookmark exports or direct extraction outputs, preserves the raw source material, normalizes it into a stable canonical model, and generates durable knowledge artifacts such as Markdown notes, metadata manifests, and searchable local indexes. It is designed for a single user operating at personal scale, with an architecture that can later evolve into a multi-user platform without reworking the core pipeline.

## Problem statement

X is good at letting a user save posts, but poor at helping them turn saved posts into reusable knowledge. The main failure is not summarization or search. The main failure is **reliable extraction of the user’s own bookmark data**.

Today, extraction has three realities that drive the product design:

- X publicly documents bookmark and bookmark-folder endpoints for authenticated users, but API access is a pay-per-use commercial dependency and public docs do not present a simple, guaranteed full-history export path.
- X publicly warns against non-API website scripting, which makes browser automation practically useful but policy-risky.
- Current open-source and browser-local exporter tools demonstrate that practical full-history export from the web UI is achievable today for personal use.

Because extraction is unstable, a bookmark knowledge base must be architected so that extraction can change without breaking storage, enrichment, or retrieval.

## Goals

1. Reliably ingest a user’s historical bookmark backlog.
2. Support repeatable incremental sync for new bookmarks.
3. Preserve raw extracted data so downstream improvements can be replayed without re-extracting.
4. Normalize bookmarks into a stable canonical schema independent of extractor quirks.
5. Generate human-auditable Markdown knowledge artifacts.
6. Preserve useful structure such as author, post URL, quoted-post references, thread hints, media references, and bookmark folder membership when available.
7. Provide useful local retrieval through keyword search in MVP and optional semantic retrieval later.
8. Keep the default deployment local-first, low-ops, and safe enough for personal use.
9. Make AI additive, versioned, and optional.

## Non-goals

1. Mass scraping or data collection across many X accounts.
2. Scraping bookmarks for users who have not explicitly provided their own authenticated session or exported data.
3. A cloud-first SaaS product in MVP.
4. Real-time social analytics, trend detection, or engagement monitoring.
5. A fully autonomous browser bot that the product depends on for correctness.
6. Automatic enrichment of every external link’s full contents in MVP.
7. Perfect reconstruction of every thread or deleted post.
8. Publishing or redistributing extracted content.

## Primary users

### Primary user
A single knowledge worker who bookmarks posts on X while reading and wants those bookmarks converted into a durable personal knowledge base.

### Secondary future user
A small team or researcher who wants the same pipeline shape later, but that is not part of MVP scope.

## Core user journeys

### 1. Initial backfill
The user exports or extracts all existing bookmarks, imports them into `bookmark-vault`, and gets:
- immutable raw capture files,
- normalized structured records,
- one Markdown note per bookmark or resolved thread,
- a searchable local catalog.

### 2. Ongoing sync
The user runs a weekly or on-demand sync. Only new or changed bookmarks are processed. Existing notes are left stable unless the user requests re-rendering.

### 3. Audit and inspect
The user can open any bookmark note and trace it back to:
- the normalized record,
- the raw extraction run,
- the enrichment outputs,
- the original X URL.

### 4. Explore and retrieve
The user can search by text, author, date, folder, tag, or linked domain. Later, they can use semantic search and AI-generated topic pages.

### 5. Reprocess without re-extracting
The user upgrades prompts, parsers, or artifact templates and re-runs normalization/enrichment against raw captures without touching X again.

## Functional requirements

1. Import bookmark data from at least one browser-local export format in MVP.
2. Support a versioned extraction adapter interface so additional extractors can be added later.
3. Store each extraction run as an immutable raw bundle with manifest, source metadata, and item payloads.
4. Normalize raw items into a canonical bookmark model.
5. Deduplicate across runs using stable identifiers and observation history.
6. Track first-seen and last-seen observations separately from post creation time.
7. Preserve folder membership if the source exposes it. X documents bookmark-folder endpoints, and at least some current exporters expose folder-aware export behavior for Premium users.
8. Expand URLs and capture lightweight linked-content metadata such as final URL, title, and description when possible.
9. Support best-effort thread reconstruction.
10. Generate Markdown notes with frontmatter and stable filenames.
11. Build a local metadata/search index.
12. Support replay of normalization and enrichment from raw data.
13. Version enrichment outputs by model, prompt, and pipeline version.
14. Produce run-level reports for completeness, duplicates, failures, and changes.

## Non-functional requirements

### Reliability
- Every pipeline stage must be independently rerunnable.
- Partial failures must not corrupt previous successful outputs.
- Repeated runs against the same raw bundle must be idempotent.

### Transparency
- Every user-visible note must be traceable to source records.
- Generated outputs must be inspectable without a proprietary UI.

### Local-first operation
- MVP must run on a personal machine.
- No mandatory cloud database or hosted queue in MVP.

### Security
- Secrets, cookies, and session artifacts must never be committed to source control.
- Raw exports and generated notes must be treated as sensitive personal data.

### Maintainability
- Extraction logic must be isolated behind adapter contracts.
- Parser and artifact templates must be versioned.

### Performance
- The system should handle at least 10,000 bookmarks on a laptop without requiring distributed infrastructure.
- Incremental sync should complete substantially faster than full backfill.

## Constraints

1. The most complete extraction methods are the least stable and may violate X automation guidance.
2. The official API is the safest automation path, but pricing is pay-per-use and endpoint pricing is not fully public outside the Developer Console.
3. Browser exporters depend on X’s current web behavior and may break after UI or GraphQL changes.
4. The system may not know the exact time a bookmark was saved unless the extractor exposes it; local first-seen time must therefore be modeled separately.
5. Deleted, protected, or unavailable posts may disappear from future syncs.

## Risks and assumptions

### Assumptions
- The user can authenticate interactively in a normal browser.
- The user is comfortable running a local CLI workflow.
- The user prefers durable local artifacts over a polished hosted UI.

### Major risks
- Extraction breakage after X UI changes.
- Incomplete exports due to lazy loading or interrupted runs.
- Session expiry or credential leakage.
- Overly aggressive automation causing account issues.
- Low-quality AI enrichment obscuring rather than clarifying the source.

### Product stance on these risks
The product will not promise “always-on reliable scraping.” It will promise a **replayable, extractor-agnostic knowledge pipeline** with strong auditability.

## Definition of done for MVP

MVP is done when all of the following are true:

1. A user can import a real historical bookmark export from their own account.
2. The system writes immutable raw run bundles and records run metadata.
3. The system normalizes bookmarks into a canonical schema and deduplicates repeated imports.
4. The system generates one inspectable Markdown artifact per bookmark or resolved thread.
5. The system builds a local searchable catalog using SQLite FTS.
6. The system supports rerunning normalization and artifact generation from raw data only.
7. The system exposes clear run reports showing total imported, duplicates, failures, and unresolved items.
8. A manual sample audit of at least 50 bookmarks shows acceptable fidelity of text, author, URL, and note rendering.
9. No cloud service is required for core extraction, storage, or keyword retrieval.

## Future expansion opportunities

1. First-party Playwright extraction adapter for convenience syncs.
2. Optional official X API adapter for compliant delta syncs.
3. Capture-at-bookmark browser extension for future-proof collection of new bookmarks.
4. Local semantic retrieval with embeddings.
5. Topic pages, weekly synthesis notes, and backlink suggestions.
6. External link full-text capture with per-domain allowlists.
7. Team-capable deployment using the same raw contract and canonical schema.
8. Shared knowledge workspaces with role-based access later, without changing the core pipeline model.