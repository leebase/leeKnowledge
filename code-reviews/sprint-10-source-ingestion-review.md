# Code Review — Sprint 10 Source Ingestion

## Architecture Summary
leeKnowledge is a local-first staged pipeline where unstable source-intake commands (`extract`, `import-url`, `import-safari-folder`, `import-research`) are supposed to stop at raw capture plus deterministic normalization, and all downstream stages (`enrich`, `export`, `topics`, `metadata`, `synthesize`, `collections`) consume the same stable SQLite bookmark contract. The main risk areas in this slice are adapter-boundary drift, source-identity/dedupe stability across reruns, and accidental regressions in the existing X-oriented derived stages when non-X rows enter the corpus.

## Checks Run
| Command | Result |
|---------|--------|
| `PYTHONPATH=src .venv/bin/python -m compileall src` | ✅ Pass |
| `PYTHONPATH=src .venv/bin/python -m pytest` | ✅ Pass |

## Findings

| ID | Severity | Category | Location | Problem | Proposed Fix |
|----|----------|----------|----------|---------|--------------|
| R001 | High | Adapter boundary | `src/leeknowledge/intake.py:95-145`, `src/leeknowledge/intake.py:148-220`, `src/leeknowledge/intake.py:223-319`, `src/leeknowledge/intake.py:418-439` | The Sprint 10 adapters build canonical bookmark rows and source IDs inside `intake.py` and then write SQLite directly via `_persist_records()`. That bypasses `normalizer.py`, so the shared normalization contract now exists in two places: X uses `normalizer.py`, while non-X imports use adapter-local logic. This preserves current behavior, but it weakens the intended boundary and makes future identity or quarantine changes likely to drift between X and non-X paths. | Move `SourceRecord`/identity derivation into a shared normalization layer and have each adapter hand off archived raw items to that shared code before DB insertion. Keep `intake.py` limited to read/parse/archive/quarantine decisions. Add one regression test proving X and non-X both reach SQLite through the same normalization helper. |
| R002 | Medium | Dedupe / idempotence | `src/leeknowledge/intake.py:283-308` | Research-item identity is not as stable as it should be. `locator = _first_string(item, ("id", "slug", "title", "url", "source_url"))` prefers `title` before URL-based identifiers. If the same research row is re-imported with the same source URL but an edited title, the derived `source_item_key` changes, producing a new `source_item_id` and duplicate bookmark instead of an idempotent rerun. | Prefer stable identifiers in this order: explicit `id`/`slug`, then canonicalized `url`/`source_url`, and only fall back to `title` when no stronger identity exists. Add a regression test that imports the same research URL twice with different titles and asserts only one bookmark row remains. |
| R003 | Medium | Tests / contract preservation | `tests/test_source_intake.py:7-42`, `tests/test_topics.py:9-42`, `tests/test_metadata.py:14-54`, `tests/test_synthesis.py:13-58`, `tests/test_collections.py:19-64` | Non-X downstream compatibility is only explicitly tested at export time. The derived-stage suites still construct X-shaped fixtures (`tweet_id`-centric helpers with X-like source expectations), so the stated Sprint 10 contract that mixed-source rows continue to work through topics, metadata, synthesis, and collections is not locked in by tests. A future X-specific assumption in those stages could slip through the current suite. | Add at least one end-to-end non-X fixture path: import a manual/Safari/research row, enrich it or seed enrichment directly, export it, then verify `topics`, `metadata`, and any applicable derived stages render `View source` links and stable note paths without assuming X URLs. |

## Remediation Roadmap

### Fix Now (Blockers)
- None. Build and full test suite passed.

### Fix Soon (High ROI)
- R001 — restores the intended adapter/normalizer boundary before more intake paths or identity rules are added.
- R002 — closes a real rerun-safety gap for research imports with mutable titles.
- R003 — adds coverage for the source-agnostic downstream contract Sprint 10 claims to preserve.

### Fix Later (Refactors)
- Consolidate source-identity naming in docs and code so the implementation, tests, and architecture language stay aligned as intake expands.

## Patch Suggestions

### R001 — route non-X adapters through shared normalization
```python
# src/leeknowledge/intake.py — BEFORE
records.append(
    _build_source_record(
        source_name="manual",
        source_type="import_url",
        source_item_key=canonical_url,
        source_ref=canonical_url,
        text=canonical_url,
        raw_urls=[canonical_url],
        first_seen_at=imported_at,
    )
)
return _persist_records(..., records=records, ...)

# AFTER
normalized = normalize_import_archive(
    archive_path=archive_path,
    adapter="import-url",
    imported_at=imported_at,
    items=items,
)
return _persist_records(..., records=normalized.records, issues=normalized.issues, ...)
```

### R002 — prefer URL identity over mutable title for research rows
```python
# src/leeknowledge/intake.py:297 — BEFORE
locator = _first_string(item, ("id", "slug", "title", "url", "source_url")) or str(index)

# AFTER
locator = (
    _first_string(item, ("id", "slug"))
    or _research_source_ref(item)
    or _first_string(item, ("title",))
    or str(index)
)
```

### R003 — add downstream non-X regression coverage
```python
# tests/test_source_intake.py or a new mixed-source contract test
# 1. seed one non-X bookmark row with source_name/source_type/source_ref
# 2. seed enrichment
# 3. run export/topics/metadata
# 4. assert generated notes use "View source" and stable non-X note paths
```

## Test Additions Recommended
- [ ] Test: re-import the same research row with unchanged URL but changed title and confirm only one bookmark row exists.
- [ ] Test: one non-X row flows through `topics` and renders a `View source` backlink instead of an X backlink.
- [ ] Test: one non-X row can participate in `metadata` and any applicable higher derived stage without path or source-link assumptions.
