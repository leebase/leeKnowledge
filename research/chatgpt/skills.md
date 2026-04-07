# skills.md

These skills are reusable Codex work modules. Each one exists to improve delivery quality, not to add ceremony.

## 1. extraction-feasibility-spike

### Purpose
Decide whether a candidate extraction path is good enough for MVP.

### Trigger / use case
Use when evaluating a new exporter, Playwright prototype, or API adapter.

### Inputs required
- sample account export or test account
- candidate adapter/tool
- expected bookmark count or range

### Output format
- short decision memo
- risk table
- recommended next step
- sample raw bundle

### Guardrails
- Must evaluate completeness, not just “it runs.”
- Must call out policy and maintenance risk explicitly.
- Must not assume the best-path result represents normal reliability.

### Completion criteria
- evidence gathered on real outputs,
- raw bundle produced,
- go / no-go recommendation made.

## 2. exporter-import-adapter-design

### Purpose
Design an importer from a third-party exporter format into the raw bundle contract.

### Trigger / use case
Use when supporting a new JSON/CSV/HTML export format.

### Inputs required
- example export file
- raw bundle schema
- fixture expectations

### Output format
- field mapping table
- parser plan
- edge-case list
- acceptance tests

### Guardrails
- Preserve unknown fields in namespaced raw payload.
- Never discard source IDs or ordering information.

### Completion criteria
- mapping approved,
- parser cases defined,
- fixture tests specified.

## 3. playwright-bookmarks-adapter-design

### Purpose
Design a conservative local browser adapter for bookmark extraction.

### Trigger / use case
Use when moving beyond import-first MVP.

### Inputs required
- extraction goals
- session constraints
- adapter contract
- current X UI observations

### Output format
- adapter plan
- selector/interception strategy
- pacing rules
- fallback strategy

### Guardrails
- Local only by default.
- No proxy or aggressive anti-bot tactics.
- Must write raw bundles before parsing.

### Completion criteria
- adapter boundaries clear,
- failure modes documented,
- incremental stop conditions defined.

## 4. raw-capture-contract-design

### Purpose
Define or revise the stable handoff between extraction and the rest of the system.

### Trigger / use case
Use whenever extractor outputs or source formats change.

### Inputs required
- exporter samples
- current contract
- downstream needs

### Output format
- schema proposal
- compatibility notes
- migration impact summary

### Guardrails
- Optimize for replayability and provenance.
- Prefer additive changes over breaking changes.

### Completion criteria
- contract version updated,
- backward-compatibility stance documented,
- fixtures updated.

## 5. canonical-normalizer-design

### Purpose
Define the raw-to-canonical mapping and dedupe rules.

### Trigger / use case
Use when normalization logic is added or changed.

### Inputs required
- raw contract
- schema definitions
- sample edge cases

### Output format
- normalization rules
- dedupe logic
- quarantine conditions
- test cases

### Guardrails
- Separate source truth from derived fields.
- Never use LLMs for primary normalization.

### Completion criteria
- mapping deterministic,
- edge cases handled,
- tests defined.

## 6. incremental-sync-review

### Purpose
Review whether the sync strategy is likely to work over time without duplicate churn or missed items.

### Trigger / use case
Use before shipping incremental sync logic or changing stop conditions.

### Inputs required
- observation model
- sample sequential runs
- source ordering assumptions

### Output format
- sync logic review
- identified failure modes
- recommended thresholds and sweeps

### Guardrails
- Must challenge implicit assumptions about bookmark timestamps.
- Must include a recovery path for missed observations.

### Completion criteria
- threshold strategy chosen,
- integrity sweep policy defined,
- regression tests specified.

## 7. markdown-knowledge-artifact-generator

### Purpose
Design or revise user-visible Markdown artifacts.

### Trigger / use case
Use when creating per-bookmark notes, topic pages, or synthesis notes.

### Inputs required
- canonical record schema
- enrichment schema
- vault structure

### Output format
- Markdown template
- frontmatter contract
- example rendered note

### Guardrails
- Original source text must remain visible.
- Provenance fields must be included.
- Missing context must be shown, not hidden.

### Completion criteria
- template reviewed,
- example note accepted,
- golden tests updated.

## 8. llm-enrichment-contract-review

### Purpose
Keep AI outputs structured, bounded, and replayable.

### Trigger / use case
Use when adding or changing prompts, models, or enrichment fields.

### Inputs required
- prompt text
- expected JSON schema
- sample records

### Output format
- prompt review
- schema validation plan
- risk notes
- rerun guidance

### Guardrails
- Enrichment must be optional.
- Outputs must be structured and versioned.
- The skill must flag hallucination risk and overclaiming.

### Completion criteria
- prompt and schema approved,
- validation added,
- replay semantics defined.

## 9. retrieval-usefulness-evaluator

### Purpose
Assess whether search and retrieval actually help the user refind knowledge.

### Trigger / use case
Use before adding vectors and after each major retrieval change.

### Inputs required
- sample queries
- expected relevant notes
- search outputs

### Output format
- benchmark report
- failure analysis
- ranked improvement recommendations

### Guardrails
- Evaluate real user tasks, not abstract IR metrics only.
- Prefer simpler retrieval when it performs similarly.

### Completion criteria
- benchmark executed,
- lexical baseline measured,
- vector recommendation justified or rejected.

## 10. secrets-and-local-security-review

### Purpose
Review handling of cookies, browser profiles, `.env` files, raw exports, and vault outputs.

### Trigger / use case
Use before introducing Playwright, API credentials, or scheduled syncs.

### Inputs required
- repo layout
- config files
- session handling approach
- backup plan

### Output format
- security review checklist
- identified exposures
- remediation steps

### Guardrails
- No secrets in source control.
- No remote storage of session artifacts by default.
- Must classify raw exports as sensitive personal data.

### Completion criteria
- gitignore and storage rules verified,
- credential handling approved,
- remediation issues filed where needed.