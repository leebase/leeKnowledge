# Code Review — Sprint 8 Leadership Metadata

## Architecture Summary
leeKnowledge is a local-first pipeline that captures X bookmarks into SQLite, enriches them, exports per-bookmark Markdown notes, and then layers deterministic leadership views on top. Sprint 8 adds a separate `leadership_metadata` table plus a dedicated `metadata` CLI stage, and Sprint 7 weekly synthesis is the first consumer of that metadata. The main risk areas in this slice are metadata drift against upstream enrichment/topic logic, silent degradation in synthesis when metadata is missing or stale, and note-rendering trust when leadership prompts are derived from weak or arbitrarily ordered signals.

## Checks Run
| Command | Result |
|---------|--------|
| `PYTHONPATH=src .venv/bin/python -m compileall src` | ✅ Pass |
| `PYTHONPATH=src .venv/bin/python -m pytest` | ✅ Pass |

## Findings

| ID | Severity | Category | Location | Problem | Proposed Fix |
|----|----------|----------|----------|---------|--------------|
| R001 | High | Metadata drift / Correctness | `src/leeknowledge/metadata.py:221-267`, `src/leeknowledge/synthesis.py:540-575` | Metadata is considered current only when its own `prompt_version` and `schema_version` match. But the judgment also depends on upstream enrichment content and topic assignment. If enrichment rows are refreshed or topic rules change without bumping the metadata versions, `generate_leadership_metadata()` skips regeneration and synthesis still renders the old labels/question as current. That creates quiet triage drift in weekly briefs. | Persist dependency freshness on metadata rows and check it before skipping/rendering. At minimum include the upstream enrichment versions/timestamp plus topic-taxonomy version, and regenerate when any of those differ. Add regression tests for: (1) enrichment content/version changes while metadata versions stay the same, and (2) taxonomy-version changes invalidating old metadata rows. |
| R002 | Medium | Operator confusion / UX | `src/leeknowledge/synthesis.py:92-123`, `src/leeknowledge/synthesis.py:548-575`, `src/leeknowledge/cli.py:229-250` | `synthesize` silently degrades when metadata is absent, failed, or stale. The weekly brief still renders as if complete, but with no Sprint 8 triage overlay and no explicit warning or coverage signal. An operator following the older `sync -> topics -> synthesize` flow gets a valid-looking note and may assume metadata ran when it did not. | Make metadata coverage explicit. Options: fail unless `--allow-missing-metadata` is set, add frontmatter/body fields like `metadata_coverage` and a warning when current metadata is missing for active-week items, and surface that state in CLI output. Add a synthesis test that verifies the note or CLI clearly reports missing metadata coverage. |
| R003 | Medium | Correctness / Operator trust | `src/leeknowledge/metadata.py:230-253`, `src/leeknowledge/metadata.py:326-345`, `src/leeknowledge/topics.py:436-520` | Multi-topic bookmarks become more strategic, but the rendered `leadership_question` is chosen from `topic_keys[0]`. That ordering comes from the static taxonomy iteration order in `assign_topics()`, not from strongest evidence or the signal that actually made the bookmark important. The result can frame the wrong leadership discussion for mixed-signal posts. | Rank topic matches before selecting the question. Prefer strongest structured match first, then summary/text support, or derive the question from the signal family that drove the final relevance. Add a multi-topic metadata test that proves the chosen question follows ranked evidence rather than taxonomy order. |

## Remediation Roadmap

### Fix Now
- R001 — quiet metadata drift will undercut trust in the weekly brief even when tests stay green.

### Fix Soon
- R002 — high operator-confusion risk because the slice can appear to work while its new value is missing.
- R003 — improves the usefulness of the new `leadership_question` field and reduces arbitrary framing.

### Fix Later
- Expand synthesis/metadata tests to cover rendering and coverage edge cases, not just the happy path.

## Test Additions Recommended
- [ ] Re-enrichment invalidates previously valid metadata when upstream enrichment freshness changes.
- [ ] Topic-taxonomy version change forces metadata regeneration.
- [ ] Weekly synthesis reports partial or missing metadata coverage explicitly.
- [ ] Multi-topic bookmark chooses the leadership question from ranked evidence, not taxonomy order.
