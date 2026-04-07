# Sprint 2 Extraction Review

Scope: extraction slice only (`src/leeknowledge/extractor.py`, `src/leeknowledge/normalizer.py`, and related tests).

Overall: the slice is close, but I would not call it safe to close yet. The implementation has a few failure modes that can silently hide a broken capture shape.

## Findings

### 1. High — extraction can succeed with zero canonical rows and no hard failure

`extract_bookmarks()` only raises `EmptyCaptureError` when `captured_payloads` is empty. If Chrome captures payloads but the payload shape changes and the normalizer cannot recognize them, the run still returns successfully with `normalized_record_count == 0` and `inserted_record_count == 0`.

- Relevant code: `src/leeknowledge/extractor.py:235-255`
- Why this matters: a GraphQL schema drift or selector regression would look like a clean run even though nothing was actually imported.
- Recommendation: fail loudly, or at minimum treat `captured_payloads > 0 && normalized_record_count == 0` as a non-success condition and surface the skipped payloads as a warning/error.

### 2. Medium — Chrome profile handling is misleading for Playwright persistent contexts

`resolve_chrome_profile_dir()` advertises support for “a specific profile path”, but `capture_bookmarks_from_chrome()` passes that path directly as `user_data_dir` in `launch_persistent_context()`.

- Relevant code: `src/leeknowledge/extractor.py:91-121` and `src/leeknowledge/extractor.py:151-157`
- Why this matters: Playwright persistent contexts expect the Chrome user-data root, not a profile subdirectory. Passing `.../Chrome/Profile 1` or `.../Chrome/Default` will not reliably reuse the intended authenticated session and may create a fresh browser state instead.
- Recommendation: either constrain the input to the user-data root only, or add explicit profile-directory handling and document the accepted path precisely.

### 3. Medium — the normalizer is very permissive and can misclassify nested objects

`normalize_raw_archive()` recursively walks every nested mapping and accepts any mapping with an ID plus text fields. On complex GraphQL payloads, that can promote unrelated nested objects into bookmarks.

- Relevant code: `src/leeknowledge/normalizer.py:58-67` and `src/leeknowledge/normalizer.py:98-118`
- Why this matters: X responses contain many nested mappings; a loose `id`/`text` match is brittle and may yield false positives or duplicate-looking rows from non-bookmark sub-objects.
- Recommendation: narrow candidate selection to known tweet-shaped objects before extracting canonical fields.

## Testing gaps

- No regression test covers the “payloads captured, but zero canonical rows” path.
- No test covers the profile-directory contract or the auth-failure path for Chrome launch/navigation.
- The current extraction tests exercise the happy path and empty capture path, but not schema drift or false-positive normalization.

## Notes from verification

I ran one small local reproduction with a fake capture payload shaped as `[{"unexpected": "shape"}]`; the current code returned a completed result with `normalized_record_count == 0` and `inserted_record_count == 0` instead of failing.
