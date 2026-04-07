# Skill: Canonical Normalizer Design

> Load this skill when implementing or changing raw-to-canonical bookmark mapping.

---

## Purpose

Define deterministic normalization rules, dedupe behavior, and quarantine logic
for turning raw captures into stable bookmark records.

---

## Use This Skill When

- Writing `src/leeknowledge/normalizer.py`
- Changing the canonical bookmark shape
- Handling extraction edge cases like missing text, replies, polls, or deleted tweets
- Revising dedupe rules

---

## Required Inputs

- Raw capture contract
- SQLite schema
- Sample edge-case payloads
- Retrieval and export needs from the architecture

---

## Output Format

- Normalization rules
- Dedupe logic
- Quarantine or skip conditions
- Test case list

---

## Guardrails

- Keep source truth separate from derived fields
- Never use an LLM for primary normalization
- Preserve tweet IDs and provenance fields
- Make edge-case handling explicit instead of silently dropping records

---

## Completion Criteria

- Mapping is deterministic
- Dedupe semantics are explicit
- Edge cases have named handling paths
- Tests are defined for the risky cases

