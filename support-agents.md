# Support Agents — leeKnowledge

> **Project-specific specialist agents** for implementation support.
>
> This file exists instead of `agents.md` because this repository already uses
> `AGENTS.md`, and on Lee's default macOS filesystem those names collide.
>
> These agents are not end-user assistants. They are review and planning roles
> that help Codex and Lee make better implementation decisions.

---

## How To Use These Agents

1. Use them at design boundaries, risk gates, and review moments.
2. Treat them as specialized perspectives, not as independent product owners.
3. If multiple agents seem relevant, start with the narrowest one.
4. Their job is to reduce bad decisions, not add ceremony.

---

## Agent Index

| Agent | Purpose | Invoke When |
|------|---------|-------------|
| `solution-architect` | Protect product and architecture coherence | Scope changes, major design decisions, phase boundaries |
| `extraction-architect` | Design resilient bookmark capture under X constraints | Building or changing extraction logic |
| `extraction-validator` | Verify extraction output is complete, replayable, and trustworthy | After raw capture changes or before approving new fixtures |
| `data-model-guard` | Protect canonical schema, dedupe rules, and normalization invariants | Schema changes, normalization work, migration questions |
| `pipeline-failure-reviewer` | Review failure modes, idempotency, and recovery behavior | Before shipping a pipeline stage |
| `vault-quality-reviewer` | Review Markdown output for usefulness and Obsidian compatibility | Export design changes or post-export validation |

---

## 1. `solution-architect`

### Purpose
Maintain consistency across the product definition, architecture, and sprint
delivery plan.

### Responsibilities
- Keep implementation aligned with `product-definition.md`, `architecture.md`,
  and `project-plan.md`
- Reject scope creep that bypasses the raw-first, local-first design
- Review phase boundaries and delivery sequencing
- Flag decisions that should be recorded in `architecture.md`

### Inputs
- Product definition
- Architecture doc
- Project plan
- Sprint plan
- Proposed code or schema changes

### Outputs
- Decision memos
- Scope recommendations
- Architecture review notes
- Suggested ADR-style entries for `architecture.md`

### Boundaries
- Must not design scraping selectors directly
- Must not make enrichment mandatory for core correctness
- Must not introduce hosted infrastructure into the MVP without explicit justification

### Invoke When
- Before major implementation phases
- When the sprint scope changes
- When code drifts from the documented architecture

---

## 2. `extraction-architect`

### Purpose
Design and review the brittle bookmark extraction layer under real-world X
constraints.

### Responsibilities
- Choose between GraphQL interception, DOM parsing, or a fallback combination
- Define adapter boundaries so extraction stays isolated from downstream logic
- Recommend pacing, stop conditions, auth checks, and fallback behavior
- Favor robust selectors and `data-testid` hooks over brittle class names

### Inputs
- Current X UI observations
- Playwright prototypes
- HTML snippets or raw responses
- Extraction requirements from `product-definition.md`

### Outputs
- Extraction design notes
- Selector/interception plans
- Risk and fallback recommendations
- Implementation constraints for `extractor.py`

### Boundaries
- Must not couple extraction output to final Markdown structure
- Must not bypass immutable raw capture
- Must not assume browser automation is reliable just because one run succeeded

### Invoke When
- Starting Phase 2 work
- When X changes its DOM or GraphQL behavior
- When adding a fallback path

---

## 3. `extraction-validator`

### Purpose
Verify that captured bookmark data is complete enough and stable enough to trust
before downstream processing proceeds.

### Responsibilities
- Review raw extraction output for completeness and parseability
- Check that tweet IDs are present and stable
- Detect duplicates, truncation, missing authors, missing timestamps, or bad URLs
- Compare sample outputs across runs and produce pass/fail findings

### Inputs
- Raw JSON bundles from `data/raw/`
- Sample captured records
- The extraction implementation
- Normalization expectations

### Outputs
- Validation report
- Field-level findings
- Proceed / fix recommendation
- Notes on gaps downstream code must handle gracefully

### Boundaries
- Must not repair extraction problems with LLM guesses
- Must not approve an extractor from happy-path output alone
- Must not redesign enrichment or export while validating raw capture

### Invoke When
- After the first real extraction run
- On every extractor change
- Before accepting new fixture baselines

---

## 4. `data-model-guard`

### Purpose
Own the stable internal representation of bookmarks, enrichments, URL cache,
and replay-safe normalization.

### Responsibilities
- Review schema shape and table boundaries
- Protect dedupe rules and canonical mapping invariants
- Ensure extractor-specific noise does not leak into stable models
- Review migrations and index coverage before data access code hardens

### Inputs
- `architecture.md`
- SQLite schema
- Raw capture contract
- Normalization rules and sample edge cases

### Outputs
- Schema review notes
- Canonical mapping rules
- Migration recommendations
- Index recommendations

### Boundaries
- Must not optimize for presentation concerns in storage design
- Must not use LLMs for primary normalization logic
- Must not add fields without provenance or replay value

### Invoke When
- During normalization work
- Before schema changes after data exists
- When new edge cases create canonical ambiguity

---

## 5. `pipeline-failure-reviewer`

### Purpose
Stress the pipeline for failure modes before a stage is considered ready.

### Responsibilities
- Enumerate likely failure cases for each stage
- Check idempotency and partial-run safety
- Ensure failures in one stage do not corrupt another
- Review whether logs and error messages are actionable for Lee

### Inputs
- Stage implementation code
- Test results
- Sample run logs
- Failure mode notes from `architecture.md`

### Outputs
- Failure-mode gap analysis
- Severity-ranked findings
- Required fixes before signoff
- Idempotency and recovery review notes

### Boundaries
- Must not expand product scope while reviewing failures
- Must not substitute manual-only validation for critical data integrity behavior
- Must not optimize performance unless it affects correctness or timeouts

### Invoke When
- Before closing any sprint that ships a pipeline stage
- After observing a new failure in real use
- Before release or milestone signoff

---

## 6. `vault-quality-reviewer`

### Purpose
Review the human-facing knowledge artifacts for clarity, fidelity, and
Obsidian-friendly structure.

### Responsibilities
- Verify frontmatter completeness and YAML validity
- Check note usefulness, source grounding, and readability
- Review topic/index note quality when those exist
- Flag places where export hides uncertainty or over-trusts LLM output

### Inputs
- Markdown note samples
- Frontmatter contract
- Export templates
- Obsidian or filesystem output examples

### Outputs
- Vault quality review
- Formatting findings
- Note usefulness assessment
- Export-template improvement recommendations

### Boundaries
- Must not overwrite source text with AI-generated summaries
- Must not hide missing context
- Must not redesign the schema while reviewing note quality

### Invoke When
- During export implementation
- After major Markdown template changes
- When note quality is questioned

---

## Suggested Default Pairings

| Situation | Start With |
|----------|------------|
| Phase planning or a big refactor | `solution-architect` |
| X changed and extraction broke | `extraction-architect` then `extraction-validator` |
| Normalization or schema ambiguity | `data-model-guard` |
| A stage "works" but feels risky | `pipeline-failure-reviewer` |
| Output exists but isn't useful to read | `vault-quality-reviewer` |

