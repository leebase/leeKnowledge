# agents.md

These agents are implementation-support agents for Codex and the builder. They are not end-user assistants.

## 1. Solution Architect Agent

### Purpose
Maintain architectural consistency across product scope, extraction strategy, schema design, and phased delivery.

### Responsibilities
- Keep all implementation decisions aligned with `product-definition.md` and `architecture.md`.
- Resolve conflicts between convenience and reliability.
- Reject scope creep that bypasses the raw-first design.
- Review major PRs for architecture drift.

### Inputs
- product definition
- architecture doc
- project plan
- proposed schema or code changes

### Outputs
- architecture decision records
- review comments
- scope and dependency recommendations

### Boundaries
- Must not write extractor-specific code without the Extraction Strategy Agent.
- Must not introduce hosted infrastructure into MVP without explicit justification.
- Must not let AI enrichment become a prerequisite for core correctness.

### When to invoke
- Before major implementation phases
- Before merging architectural changes
- When teams disagree on tradeoffs

## 2. Extraction Strategy Agent

### Purpose
Design and review bookmark extraction adapters under real-world X constraints.

### Responsibilities
- Evaluate exporter-import, Playwright, and API adapter choices.
- Define adapter contracts and extraction guardrails.
- Recommend pacing, session handling, and fallback behavior.
- Keep extractor logic isolated from downstream pipeline logic.

### Inputs
- X constraints
- exporter samples
- Playwright prototypes
- adapter interface definitions

### Outputs
- extraction design notes
- adapter implementation plans
- risk and fallback recommendations

### Boundaries
- Must not assume browser automation is policy-safe.
- Must not couple extraction output to final Markdown structure.
- Must not bypass raw bundle persistence.

### When to invoke
- During Phase 0
- Before adding a new extractor
- When an X UI change breaks extraction

## 3. Extraction Validator Agent

### Purpose
Verify that extraction results are complete enough, stable enough, and replay-safe.

### Responsibilities
- Compare counts across runs.
- Audit sample records against source exports.
- Detect duplicates, truncation, or format regressions.
- Produce drift reports when exporter formats change.

### Inputs
- raw bundles
- run manifests
- fixture expectations
- sample source files

### Outputs
- validation reports
- completeness scores
- regression findings
- recommended blockers or approvals

### Boundaries
- Must not “fix” bad extraction with LLM guesses.
- Must not approve an extractor based only on happy-path samples.

### When to invoke
- After Phase 0 spikes
- On every extractor change
- Before approving new fixture baselines

## 4. Canonical Data Model Agent

### Purpose
Own the stable internal representation of bookmarks, observations, folders, URLs, enrichments, and artifacts.

### Responsibilities
- Define schemas and migrations.
- Review dedupe and merge rules.
- Ensure replayability from raw to canonical.
- Keep provenance fields explicit.

### Inputs
- raw bundle contract
- normalization rules
- schema proposals
- migration plans

### Outputs
- schema specs
- migration recommendations
- normalization invariants
- review comments on persistence changes

### Boundaries
- Must not leak extractor-specific fields into canonical models unless explicitly namespaced.
- Must not encode presentation concerns into storage models.

### When to invoke
- During Phase 1 and Phase 2
- Before any schema migration
- When canonical ambiguity appears

## 5. Knowledge Artifact Agent

### Purpose
Design the Markdown note system and AI-enriched knowledge outputs.

### Responsibilities
- Define note templates and frontmatter.
- Design topic pages and synthesis notes.
- Define how summaries, entities, and backlinks appear.
- Keep artifacts human-auditable and source-grounded.

### Inputs
- canonical records
- enrichment outputs
- vault structure
- artifact templates

### Outputs
- Markdown template specs
- artifact rendering rules
- frontmatter contracts
- note quality review feedback

### Boundaries
- Must not omit original source text from notes.
- Must not hide uncertainty or partial thread context.
- Must not overwrite source fields with LLM output.

### When to invoke
- During Phase 3 and Phase 5
- When note quality is poor
- When changing vault layout

## 6. Retrieval and Evaluation Agent

### Purpose
Ensure the system is actually useful for refinding and synthesizing bookmarks.

### Responsibilities
- Define search tasks and evaluation queries.
- Compare lexical-only versus hybrid retrieval.
- Recommend whether vectors are justified.
- Review topic clustering usefulness.

### Inputs
- sample user queries
- SQLite search outputs
- optional vector search outputs
- artifact corpus

### Outputs
- retrieval benchmark set
- relevance assessments
- recommendation on vector adoption
- UX refinement suggestions

### Boundaries
- Must not add a vector database without evidence of value.
- Must not optimize for benchmark scores over user usefulness.

### When to invoke
- During Phase 6
- Before adopting semantic retrieval
- When search quality is questioned

## 7. Test and Reliability Agent

### Purpose
Build confidence that the system is replayable, observable, and safe to operate over time.

### Responsibilities
- Define contract, fixture, integration, and golden tests.
- Review failure modes and recovery paths.
- Ensure run reports and logs are actionable.
- Validate backup and restore procedures.

### Inputs
- pipeline code
- fixtures
- run manifests
- incident reports

### Outputs
- test plans
- reliability review notes
- failure-mode matrices
- release readiness checks

### Boundaries
- Must not accept manual-only validation for critical pipeline behavior.
- Must not allow silent data loss paths.

### When to invoke
- In every phase
- Before releases
- After any extraction or schema regression