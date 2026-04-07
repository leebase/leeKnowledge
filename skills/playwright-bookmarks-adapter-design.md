# Skill: Playwright Bookmarks Adapter Design

> Load this skill when building or revising the Playwright-based bookmark extractor.

---

## Purpose

Design a conservative local browser adapter for extracting X bookmarks while
keeping the brittle scraping logic isolated from the rest of the pipeline.

---

## Use This Skill When

- Implementing `src/leeknowledge/extractor.py`
- Evaluating GraphQL interception versus DOM parsing
- Responding to an X UI change
- Adding or revising a fallback path

---

## Required Inputs

- Extraction goals from `product-definition.md`
- Extraction boundaries from `architecture.md`
- Current browser/session constraints
- Any available HTML snippets or intercepted responses

---

## Output Format

- Adapter plan
- Selector/interception strategy
- Pacing and stop-condition rules
- Auth and failure checks
- Fallback strategy

---

## Guardrails

- Local browser only by default
- Write raw bundles before parsing
- Prefer `data-testid` and response interception over fragile class selectors
- Avoid aggressive anti-bot tactics, proxies, or hidden infrastructure
- Keep extractor output independent of Markdown/export concerns

---

## Completion Criteria

- Adapter boundaries are explicit
- Stop conditions are defined
- Failure modes are documented
- Raw capture happens before normalization

