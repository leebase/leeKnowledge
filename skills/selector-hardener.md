# Skill: Selector Hardener

> Load this skill when X DOM changes break extraction or when selectors feel fragile.

---

## Purpose

Create resilient scraping selectors and DOM lookup rules that survive routine X
UI churn better than naive class-based scraping.

---

## Use This Skill When

- Existing selectors stop working
- You need a DOM fallback path
- You are reviewing whether selector choices are too brittle

---

## Required Inputs

- HTML snippet or page snapshot from X
- Current selector set
- The extraction target you need to identify

---

## Output Format

- Revised selector set
- Selector rationale
- Fallback selector chain
- Known brittleness warnings

---

## Guardrails

- Prefer `data-testid`, semantic attributes, and stable structure
- Avoid obfuscated class names unless there is no better path
- Document why each selector is trustworthy enough
- Keep selectors scoped to the extraction need, not the whole page

---

## Completion Criteria

- Primary selector is defined
- Backup selector path exists
- Failure cases are known
- The selector choice is justified against likely DOM churn

