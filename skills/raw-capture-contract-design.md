# Skill: Raw Capture Contract Design

> Load this skill when defining or changing the handoff between extraction and normalization.

---

## Purpose

Define the stable raw data contract that the rest of the pipeline can replay
from, even when the upstream extraction details change.

---

## Use This Skill When

- The extractor output format changes
- New source fields appear in captured payloads
- A fallback extractor needs to share the same downstream contract
- You are deciding what to archive versus what to derive

---

## Required Inputs

- Current raw capture behavior
- Example raw payloads
- Downstream normalization needs
- Existing SQLite schema and replay requirements

---

## Output Format

- Raw contract proposal
- Compatibility notes
- Field preservation rules
- Migration impact summary

---

## Guardrails

- Optimize for replayability and provenance
- Preserve unknown source data in raw form rather than discarding it
- Prefer additive contract changes over breaking ones
- Do not let extractor-specific quirks leak into canonical models

---

## Completion Criteria

- Required raw fields are explicit
- Backward-compatibility stance is documented
- Raw archive naming and persistence rules are clear
- Downstream code can consume the contract deterministically

