# Code Review — Sprint 6 Topic Index Notes

## Architecture Summary
leeKnowledge is a local-first pipeline that extracts X bookmarks into SQLite, enriches them, exports bookmark notes to a Markdown vault, and now adds a separate `topics` derived-view step. The Sprint 6 slice is centered in `src/leeknowledge/topics.py`, which deterministically groups bookmark/enrichment rows into four fixed topic notes under `vault/topics/` and relies on exporter path logic for backlinks. The main risk areas in this slice are grouping correctness at the taxonomy boundaries, derived-note fidelity when backlink targets do not exist, and keeping the new command isolated so it does not regress the stable bookmark-export contract.

## Checks Run
| Command | Result |
|---------|--------|
| `PYTHONPATH=src .venv/bin/python -m compileall src` | ✅ Pass |
| `PYTHONPATH=src .venv/bin/python -m pytest` | ✅ Pass |

## Findings

| ID | Severity | Category | Location | Problem | Proposed Fix |
|----|----------|----------|----------|---------|--------------|
| R001 | High | Grouping Correctness | `src/leeknowledge/topics.py:491-564` | `vendor-landscape` currently requires both a movement keyword and an explicit vendor name. That is stricter than the Sprint 6 contract, which forbids vendor-name-only matches but still allows market/comparison/pricing posts without a named provider. Example probe: a row with `topic="vendor landscape"`, tags `comparison/pricing`, and summary `Vendor comparison of leading model providers after a pricing update` returns `{}`. This creates false negatives for generic market-scan posts and under-populates the derived note. | Change vendor matching so explicit structured vendor framing (`topic`, `tags`, or summary) plus movement/comparison keywords can qualify without a named provider. Keep the current safeguard only for weak text/URL-only matches. Add a regression test for a generic vendor-landscape row with no provider names. |
| R002 | High | Derived-Note Fidelity | `src/leeknowledge/topics.py:391-394`, `src/leeknowledge/topics.py:678-683`, `src/leeknowledge/cli.py:262-280` | Topic-note backlinks are synthesized from `build_bookmark_note_path()` without checking whether the bookmark note was ever exported. Running `topics` before `export` succeeds and writes links to files that do not exist, so the note claims source traceability but delivers broken local backlinks. | Fail fast when a matched bookmark's exported note file is missing, or add an explicit preflight that requires bookmark-note export to have been run before topic generation. If a softer behavior is preferred, mark the missing local note explicitly instead of emitting a broken link. Add a test that `topics` on a populated DB without exported bookmark notes errors clearly. |
| R003 | Medium | Regression / Failure Handling | `src/leeknowledge/topics.py:348-351`, `src/leeknowledge/topics.py:357-358`, `tests/test_topics.py` | `generate_topic_notes()` creates `vault/` and `vault/topics/` before validating that the DB schema is usable. On schema failure, the command leaves an empty derived-output directory behind even though generation failed. That is a small but real side effect from what is supposed to be a pure derived-view step, and it can make a failed run look partially successful. | Move vault-directory creation until after `_validate_topic_database()` passes, or clean up the newly created directories on failure. Add a regression test that a schema-invalid DB raises `TopicGenerationError` without creating `vault/topics/`. |

## Remediation Roadmap

### Fix Now (Blockers)
- R001 — grouping under-fills `vendor-landscape` for a documented class of Sprint 6 inputs.
- R002 — topic notes can be generated with broken bookmark-note backlinks, which undermines the slice's traceability contract.

### Fix Soon (High ROI)
- R003 — small failure-path cleanup that will keep the derived step side-effect free and easier to trust.

### Fix Later (Refactors)
- None beyond the targeted fixes above.

## Patch Suggestions

```python
# src/leeknowledge/topics.py:491-564 — BEFORE
if topic_key == "vendor-landscape":
    vendor_supported = _vendor_landscape_matches(
        structured_topic=structured_topic,
        joined_tags=joined_tags,
        summary_text=summary_text,
        bookmark_text=bookmark_text,
        url_text=url_text,
    )
    if not vendor_supported:
        continue

# AFTER
if topic_key == "vendor-landscape":
    vendor_supported = _vendor_landscape_matches(
        structured_topic=structured_topic,
        joined_tags=joined_tags,
        summary_text=summary_text,
        bookmark_text=bookmark_text,
        url_text=url_text,
        has_structured_match=structured_hits[topic_key] or medium_hits[topic_key],
    )
    if not vendor_supported:
        continue
```

```python
# src/leeknowledge/topics.py:391-394 — BEFORE
note_path = build_bookmark_note_path(vault_root, row)
relative_note_path = note_path.relative_to(vault_root)
note_link = Path("..") / relative_note_path

# AFTER
note_path = build_bookmark_note_path(vault_root, row)
if not note_path.exists():
    raise TopicGenerationError(
        f"Bookmark note is missing for tweet {row['tweet_id']}: {note_path}. Run export before topics."
    )
relative_note_path = note_path.relative_to(vault_root)
note_link = Path("..") / relative_note_path
```

```python
# src/leeknowledge/topics.py:348-351 — BEFORE
vault_root = Path(vault_dir)
vault_root.mkdir(parents=True, exist_ok=True)
topics_root = vault_root / TOPIC_NOTES_DIRNAME
topics_root.mkdir(parents=True, exist_ok=True)

# AFTER
vault_root = Path(vault_dir)
...
with get_connection(resolved_db_path) as connection:
    _validate_topic_database(connection, resolved_db_path)

vault_root.mkdir(parents=True, exist_ok=True)
topics_root = vault_root / TOPIC_NOTES_DIRNAME
topics_root.mkdir(parents=True, exist_ok=True)
```

## Test Additions Recommended
- [ ] Test: `assign_topics()` should classify a generic vendor-market row (`topic="vendor landscape"` + `comparison/pricing` language) even when no provider name appears.
- [ ] Test: `generate_topic_notes()` should fail clearly when bookmark-note files are absent and should not emit broken `Bookmark note` links.
- [ ] Test: schema-validation failure should not create `vault/` or `vault/topics/`.
