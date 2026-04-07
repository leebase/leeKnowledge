# Skill: Pipeline Failure Review

> Load this skill before closing a sprint that ships a pipeline stage.

---

## Purpose

Review a stage for failure handling, idempotency, and partial-run safety before
it is considered trustworthy.

---

## Use This Skill When

- A new stage has been implemented
- An existing stage was substantially changed
- A real-world failure exposed a blind spot

---

## Required Inputs

- Stage implementation code
- Sample logs or command output
- Existing tests
- Known failure risks from `architecture.md`

---

## Output Format

- Failure-mode table
- Unhandled-case list
- Severity notes
- Required follow-up fixes

---

## Guardrails

- Check idempotency, not just happy-path success
- Focus on data safety and operator clarity
- Do not accept "just rerun it" if reruns can corrupt state
- Prefer explicit readable errors over silent skips

---

## Completion Criteria

- Critical failure modes are enumerated
- Handling strategy exists for each critical case
- Partial-run behavior is understood
- Rerun safety has been reviewed

