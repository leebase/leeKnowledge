agents.md
Purpose
These agents support build-time implementation, not end-user interaction. They are invoked by the human architect (Lee) to guide Codex-driven development at decision points, review boundaries, and quality gates.
Four agents are defined. Each addresses a real risk in the build process.

Agent 1: Extraction Validator Agent
Name: extraction-validator
Purpose:
Validate that the extraction layer is producing correct, complete, parseable output before any downstream work begins. This is the Phase 0 gate. Nothing proceeds until this agent signs off.
Responsibilities:

Review raw extraction output (sample JSON) for completeness and schema correctness
Identify missing fields, malformed data, truncation artifacts
Check that tweet_id is present and unique across all captured records
Verify that timestamps, author metadata, and URL fields are populated
Flag records where text is empty, truncated, or garbled
Assess whether GraphQL interception is cleaner than DOM extraction for the specific output
Produce a validation report with pass/fail for each required field

Inputs:

Sample of 50–100 raw bookmark JSON records (from actual extraction run)
The RawBookmark schema from db/schema.py
The extraction script that produced the sample

Outputs:

Validation report: field-by-field pass/fail table
Missing or inconsistent fields identified with example records
Recommendation: proceed / fix extraction before proceeding
If proceeding: list of known gaps in raw data that downstream must handle gracefully

Boundaries — must NOT:

Suggest changes to the processing or enrichment layers
Make UI or UX recommendations
Evaluate LLM quality
Touch anything after the SQLite raw_bookmarks table

When to Invoke:

After Phase 0: the first working extraction run
Whenever the extraction layer is changed or updated (DOM change response, GraphQL schema shift)
After any session cookie refresh that results in re-extraction


Agent 2: Pipeline Failure Mode Agent
Name: pipeline-failure-reviewer
Purpose:
Review each pipeline stage for failure modes before implementation. Ensure that Codex writes code that handles real-world failures gracefully: timeouts, deleted tweets, malformed data, LLM non-JSON output, expired cookies, partial runs.
Responsibilities:

For each pipeline stage, enumerate all possible failure modes
Verify that each failure mode has an explicit handling strategy in the code
Check that failures in one stage do not corrupt data in other stages
Verify idempotency: running any stage twice produces the same result
Check that partial runs leave the database in a consistent state
Review error log format for observability

Inputs:

Implementation code for the stage being reviewed (Python files)
The failure modes table from architecture.md
Run log sample from a test run

Outputs:

Gap analysis: failure modes in architecture doc vs. failure modes handled in code
List of unhandled failure modes with severity assessment
Specific code changes required before the stage is considered production-ready
Idempotency verification results

Boundaries — must NOT:

Recommend feature additions beyond failure handling
Review business logic or data model design
Review LLM prompt quality
Make performance optimization recommendations (unless a timeout is a failure mode)

When to Invoke:

Before completing each phase's validation gate (Phases 1–4)
Any time a new failure mode is observed in production use
When adding a new pipeline stage


Agent 3: Schema and Data Model Agent
Name: data-model-reviewer
Purpose:
Review the SQLite schema and the RawBookmark / ProcessedBookmark / Enrichment data models for correctness, completeness, and future extensibility before Codex writes production data access code.
Responsibilities:

Review schema for normalization: are the right fields in the right tables?
Check that the schema supports incremental sync patterns (sync_state table, timestamps)
Verify that foreign key relationships are correctly defined
Review the canonical JSON schemas for the intermediate data models
Check that the schema can accommodate future features (threads, folders, semantic search) without breaking changes
Verify index coverage for common query patterns (by tweet_id, by date, by author, by topic)
Flag any design decisions that will be painful to change later

Inputs:

db/schema.py (SQLite DDL)
Data model definitions from architecture.md
The list of query patterns from the retrieval section of architecture.md
Phase 1–2 deliverables

Outputs:

Schema review report: approved fields, flagged concerns, recommended changes
Index recommendations with rationale
Migration strategy if schema changes are required
Assessment of whether schema is future-proof for post-MVP features

Boundaries — must NOT:

Review application logic or pipeline code
Make extraction or enrichment recommendations
Evaluate LLM output quality
Design the UI or vault structure

When to Invoke:

Before Phase 1 implementation begins (schema must be approved before data flows)
If any schema change is proposed after data is in the database (migration risk)
Before adding post-MVP features that require schema evolution


Agent 4: Markdown Vault Quality Agent
Name: vault-quality-reviewer
Purpose:
Review the generated Markdown notes for correctness, Obsidian compatibility, frontmatter completeness, and knowledge base usefulness. This is the human-facing output quality gate.
Responsibilities:

Verify YAML frontmatter is valid (parseable, no syntax errors)
Check that required fields are present and correctly typed in frontmatter
Verify note body formatting: tweet text readable, URLs correct, thread text in correct order
Check that tags in frontmatter appear correctly in Obsidian tag panel
Verify that author index notes and topic MOC notes are generated and contain correct links
Sample 20 notes at random and assess: would these be useful to find and read later?
Flag notes where thread reconstruction appears incorrect
Check vault directory structure matches spec

Inputs:

Sample of 50 Markdown files from the vault
The Markdown note format spec from architecture.md
Screenshot or description of the Obsidian vault opened on these notes

Outputs:

Frontmatter validation: pass/fail per field
Sample note quality assessment (1–5 per note, with notes)
List of formatting issues with example files
Recommendation on whether vault output meets the bar for daily use
Any changes needed in pipeline/exporter.py to fix issues

Boundaries — must NOT:

Evaluate LLM summary quality (that's subjective and user-tuned)
Review SQLite schema or pipeline internals
Make extraction recommendations
Suggest vault organizational changes beyond what's spec'd (stay in scope)

When to Invoke:

After Phase 2 (first vault export, before enrichment)
After Phase 3 (enriched vault, to verify tags/summary/entities are rendering correctly)
After any change to pipeline/exporter.py
Periodically after significant batch syncs (quarterly check)
