# Skill: LLM Enrichment Contract Review

> Load this skill when adding or changing prompts, models, or enrichment fields.

---

## Purpose

Keep AI enrichment structured, bounded, versioned, and optional so the pipeline
stays replayable and source-grounded.

---

## Use This Skill When

- Writing `src/leeknowledge/enricher.py`
- Defining or changing the enrichment JSON schema
- Tuning prompts or changing models
- Deciding how reruns should behave for old enrichments

---

## Required Inputs

- Prompt text
- Expected JSON schema
- Sample bookmark records
- Storage rules for enrichments

---

## Output Format

- Prompt review
- Schema validation plan
- Risk notes
- Replay/versioning guidance

---

## Guardrails

- Enrichment must remain optional
- Outputs must be structured and versioned
- Summaries must not replace original source text
- Flag hallucination and overclaiming risks explicitly

---

## Completion Criteria

- Prompt and response schema are explicit
- Validation plan exists for malformed output
- Model/version storage strategy is documented
- Rerun semantics are clear

