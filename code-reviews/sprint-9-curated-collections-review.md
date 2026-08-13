# Code Review — Sprint 9 Curated Collections

## Architecture Summary
leeKnowledge is a local-first CLI pipeline that stores X bookmarks in SQLite, exports per-bookmark Markdown notes, and then generates higher-level derived artifacts as explicit post-export steps. Sprint 9 adds `src/leeknowledge/collections.py` plus the `collections` CLI command and checked-in initiative definitions in `playbooks/curated-collections.yaml`, using bookmark notes, deterministic topic membership, weekly synthesis files, and validated leadership metadata to render initiative-centered notes under `vault/collections/`. The main risk areas in this slice are collection usefulness versus simply re-labeling topic notes, rerun safety when definitions change over time, Markdown fidelity because collection entries embed LLM-derived text inline, and definition validation because the YAML file is the only required manual curation layer.

## Checks Run
| Command | Result |
|---------|--------|
| `PYTHONPATH=src .venv/bin/python -m compileall src` | ✅ Pass |
| `PYTHONPATH=src .venv/bin/python -m pytest` | ✅ Pass (`38 passed`) |
| `PYTHONPATH=src .venv/bin/python - <<'PY' ... generate_collection_notes() twice with different slugs in a temp vault ... PY` | ✅ Reproduced stale removed-note artifact: old collection file remained after the definition slug changed |
| `PYTHONPATH=src .venv/bin/python - <<'PY' ... generate a collection with markdown-heavy summary/question text ... PY` | ✅ Reproduced Markdown structure injection in the rendered collection note |
| `PYTHONPATH=src .venv/bin/python - <<'PY' ... load_collection_definitions() with topic_keys: [1] ... PY` | ✅ Reproduced raw `TypeError` instead of `CollectionGenerationError` |

## Findings

| ID | Severity | Category | Location | Problem | Proposed Fix |
|----|----------|----------|----------|---------|--------------|
| R001 | High | Rerun Safety / Regression | `src/leeknowledge/collections.py:149-185` | Collection regeneration only rewrites the currently defined files; it never removes notes for initiatives that were deleted or renamed in `playbooks/curated-collections.yaml`. I reproduced this with two runs against the same temp vault: after switching the only definition from `first` to `second`, `vault/collections/first.md` remained beside `second.md`. That violates the Sprint 9 contract that the checked-in definition list is the source of truth and leaves misleading stale initiative artifacts in Obsidian. | Before writing new notes, enumerate existing `vault/collections/*.md` generated artifacts and remove any stale initiative files that are no longer present in the current definition set, while preserving the regenerated `index.md`. Add a regression test that runs `generate_collection_notes()` twice with different definition slugs and asserts the removed initiative note no longer exists. |
| R002 | Medium | Collection Usefulness | `src/leeknowledge/collections.py:318-330`, `src/leeknowledge/collections.py:390-402`, `tests/test_collections.py:358-419` | Weekly synthesis is advertised as an initiative signal and tie-breaker, but the actual membership gate discards `has_weekly_mention` entirely (`del has_weekly_mention`). In practice, a bookmark cannot enter a collection unless it has a direct topic match or a metadata-plus-tag combination. The shipped test suite codifies this by asserting that weekly-only candidates are excluded. That makes Sprint 9 less useful than the documented contract: a bookmark that was important enough to cite in the weekly brief but falls just outside the narrow topic/tag hints can never surface in a collection. | Allow a bounded weekly-backed admission path, e.g. `topic + weekly`, `metadata + weekly`, or `weekly + strong tag match`, and keep weekly-only membership rare but possible when the evidence is otherwise strong. Update the ranking logic so weekly mention remains a boost instead of a hard dependency, and replace the current exclusion test with cases that prove the intended bounded weekly-backed behavior. |
| R003 | Medium | Note Fidelity | `src/leeknowledge/collections.py:479-485`, `src/leeknowledge/collections.py:519-525` | The renderer inserts definition text, summary-derived context, and metadata `leadership_question` strings directly into Markdown bullets without escaping or fencing. In a tempfile repro, a metadata question containing `\n## injected heading` broke the bullet structure and rendered a new heading inside `## Current evidence`; a summary beginning with `# Heading` was also rendered as raw Markdown inside the evidence list. This repeats the same note-fidelity class of bug that Sprint 5 had to harden in bookmark export. | Escape Markdown-sensitive inline content or render volatile text fields in fenced/literal blocks. At minimum, normalize multiline `leadership_question` and context strings into safe single-line text before interpolation. Add regression tests with headings, list markers, links, and embedded newlines in summaries and leadership questions. |
| R004 | Medium | Missing Validation | `src/leeknowledge/collections.py:241-247`, `src/leeknowledge/collections.py:259-270` | Definition parsing does not validate element types before formatting error messages or coercing numeric fields. A malformed YAML file with `topic_keys: [1]` raises a raw `TypeError` from `', '.join(...)` instead of the command's expected `CollectionGenerationError`. Because the definitions file is the only manual curation layer in Sprint 9, this should fail cleanly and readably, not crash through an implementation detail. | Validate that `topic_keys` and `include_tags_any` contain only strings before using them, and wrap `source_window_days` / `max_items` coercion in explicit error handling that raises `CollectionGenerationError` with the initiative slug and bad value. Add tests for non-string topic keys and non-integer numeric fields. |

## Remediation Roadmap

### Fix Now (Blockers)
- R001 — stale collection notes will quietly survive initiative-list edits and misrepresent the current active-work view.

### Fix Soon (High ROI)
- R002 — bounded weekly-backed admission would make the collection layer feel more like initiative support and less like a second topic filter.
- R003 — Markdown injection is likely to show up with real LLM summaries/questions and will erode trust in the notes quickly.
- R004 — the definitions file is operator-facing config; malformed values should fail cleanly.

### Fix Later (Refactors)
- Pull candidate admission and ranking into a small policy helper so the initiative-selection contract is easier to test as Sprint 9 evolves.

## Patch Suggestions

```python
# src/leeknowledge/collections.py:149-185 — BEFORE
collections_root = vault_root / COLLECTIONS_DIRNAME
collections_root.mkdir(parents=True, exist_ok=True)
...
for definition in definitions:
    ...
    _write_atomically(note_path, content)
...
_write_atomically(index_path, index_content)

# AFTER
collections_root = vault_root / COLLECTIONS_DIRNAME
collections_root.mkdir(parents=True, exist_ok=True)
expected_note_names = {f"{definition.initiative_slug}.md" for definition in definitions}
for existing_path in collections_root.glob("*.md"):
    if existing_path.name == "index.md":
        continue
    if existing_path.name not in expected_note_names:
        existing_path.unlink()
...
for definition in definitions:
    ...
_write_atomically(index_path, index_content)
```

```python
# src/leeknowledge/collections.py:390-402 — BEFORE
def _candidate_is_allowed(...):
    del has_weekly_mention
    if has_topic_match:
        return True
    if metadata_fit and has_tag_match:
        return True
    return False

# AFTER
# Example bounded expansion that still avoids weak weekly-only dumps.
def _candidate_is_allowed(...):
    if has_topic_match:
        return True
    if metadata_fit and has_tag_match:
        return True
    if has_weekly_mention and (metadata_fit or has_tag_match):
        return True
    return False
```

```python
# src/leeknowledge/collections.py:519-525 — BEFORE
lines.append(f"- {candidate.bookmark_date} — {candidate.author_handle} — {candidate.context}")
...
lines.append(f"  - Leadership question: {candidate.leadership_question}")

# AFTER
safe_context = _markdown_safe_inline(candidate.context)
lines.append(f"- {candidate.bookmark_date} — {candidate.author_handle} — {safe_context}")
...
safe_question = _markdown_safe_inline(candidate.leadership_question)
lines.append(f"  - Leadership question: {safe_question}")
```

```python
# src/leeknowledge/collections.py:241-247 — BEFORE
topic_keys = tuple(raw.get("topic_keys") or ())
...
invalid_topic_keys = [topic_key for topic_key in topic_keys if topic_key not in TOPIC_DEFINITIONS]
if invalid_topic_keys:
    raise CollectionGenerationError(
        f"Unknown topic_keys for {initiative_slug}: {', '.join(invalid_topic_keys)}"
    )

# AFTER
topic_keys_raw = raw.get("topic_keys") or []
if not isinstance(topic_keys_raw, list) or any(not isinstance(item, str) for item in topic_keys_raw):
    raise CollectionGenerationError(f"topic_keys must be a list of strings for {initiative_slug}.")
topic_keys = tuple(topic_keys_raw)
invalid_topic_keys = [topic_key for topic_key in topic_keys if topic_key not in TOPIC_DEFINITIONS]
if invalid_topic_keys:
    raise CollectionGenerationError(
        f"Unknown topic_keys for {initiative_slug}: {', '.join(invalid_topic_keys)}"
    )
```

## Test Additions Recommended
- [ ] Test: rerunning collections after removing or renaming an initiative definition should delete the old generated note.
- [ ] Test: a weekly-cited bookmark with strong supporting metadata or tag evidence can be admitted even when topic hints are sparse.
- [ ] Test: Markdown-heavy summary and `leadership_question` values do not break collection-note structure.
- [ ] Test: non-string `topic_keys` and non-integer `source_window_days` / `max_items` fail with `CollectionGenerationError`, not raw Python exceptions.
