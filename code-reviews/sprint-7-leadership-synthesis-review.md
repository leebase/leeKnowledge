# Code Review — Sprint 7 Leadership Synthesis

## Architecture Summary
leeKnowledge is a local-first CLI pipeline that extracts X bookmarks into SQLite, enriches them, exports per-bookmark Markdown notes, generates deterministic topic notes, and now adds a separate `synthesize` command for weekly leadership briefs. Sprint 7 is centered in `src/leeknowledge/synthesis.py`, which reads bookmark/enrichment rows from SQLite, recomputes topic membership with the Sprint 6 taxonomy, validates that bookmark/topic notes exist in the vault, and writes one archived weekly note plus a latest-alias note under `vault/synthesis/` and `vault/briefs/`. The main risks in this slice are synthesis usefulness versus mere counting, source-trail accuracy when linked topic notes are stale, regressions that hide active topic movement from the weekly brief, and tests that validate file shape without fully locking the leadership-brief contract.

## Checks Run
| Command | Result |
|---------|--------|
| `pwd && python3 --version && .venv/bin/python --version` | ✅ Pass |
| `PYTHONPATH=src .venv/bin/python -m compileall src` | ✅ Pass |
| `PYTHONPATH=src .venv/bin/python -m pytest tests/test_synthesis.py` | ✅ Pass (`4 passed`) |
| `PYTHONPATH=src .venv/bin/python .agent-orch-scratch/44e5da53a693/review_sprint_7_leadership_synthesis/attempt-3/repro_four_topic.py` | ✅ Pass; reproduced count-heavy signal bullets and confirmed `vendor-landscape` is omitted from `Worth discussing` in a 4-topic week |
| `PYTHONPATH=src .venv/bin/python .agent-orch-scratch/44e5da53a693/review_sprint_7_leadership_synthesis/attempt-3/repro_stale_topic.py` | ✅ Pass; reproduced synthesis succeeding while the linked topic note remained stale (`8202` absent from the topic note but present in the weekly brief) |

## Findings

| ID | Severity | Category | Location | Problem | Proposed Fix |
|----|----------|----------|----------|---------|--------------|
| R001 | High | Artifact Usefulness | `src/leeknowledge/synthesis.py:324-366` | `## This week's signals` is mostly operational metadata (`bookmark_count`, `topic_count`, structured-signal count) rather than evidence-grounded synthesis. In the 4-topic repro, the section surfaced only counts and the strongest-topic tie, even though the cited bookmarks clearly described launches, governance controls, agent rollout, and data-platform movement. That underdelivers on the Sprint 7 contract that this should be the first leadership-prep surface instead of a stats header. | Build the signal bullets from the selected evidence pack instead of only aggregate counts. At minimum, emit 2-4 bullets that name the dominant theme/topic and include bookmark context or topic-note citations, with at most one count/volume bullet. Add a regression test that asserts at least one signal bullet contains source-grounded context text, not only numeric counts. |
| R002 | High | Synthesis Accuracy / Traceability | `src/leeknowledge/synthesis.py:209-215`, `src/leeknowledge/synthesis.py:369-399`, `src/leeknowledge/synthesis.py:425-451` | Synthesis checks only that active topic-note files exist; it does not verify that they are fresh for the current corpus. In the stale-topic repro, `synthesize` accepted `vault/topics/vendor-landscape.md` after a new vendor bookmark had been exported but before `topics` was rerun. The weekly brief then linked that stale topic note as current framing even though the topic note still contained only tweet `8201` while the weekly brief cited both `8201` and `8202`. This weakens the promised source trail because the linked topic note can contradict the synthesis it supposedly supports. | Fail fast when an active topic note is stale relative to the synthesized corpus. The lightest fix is to validate that each active topic note contains the current cited bookmark links for that topic, or at least that its frontmatter `generated_at`/`bookmark_count` matches the current active-topic slice. If the note is stale, raise `SynthesisError` with guidance to rerun `topics` before `synthesize`. Add a regression test for “topic note exists but is stale for the current week.” |
| R003 | Medium | Regression / Synthesis Accuracy | `src/leeknowledge/synthesis.py:411-417` | `## Worth discussing` silently truncates active topics to `active_topic_keys[:3]`. Because `active_topic_keys` follows taxonomy order, a week with all four topics always drops `vendor-landscape` from the discussion prompts even when vendor movement is active. The 4-topic repro showed exactly that: `Vendor Landscape` appeared in `Topic movement` and `Source trail` but disappeared from the section most likely to drive leadership conversation. | Rank discussion prompts by weekly activity (and then recency as a tiebreaker) instead of fixed taxonomy order, or include all active topics when the set is small. Add a regression test where all four topics are active and assert that a tied or dominant fourth topic is not omitted by default. |
| R004 | Medium | Testing Gaps | `tests/test_synthesis.py:60-150`, `tests/test_synthesis.py:153-246` | The synthesis tests currently prove pathing, section presence, alias refresh, and missing-file failures, but they do not lock the most failure-prone Sprint 7 behaviors: evidence-grounded signal bullets, stale topic-note detection, or 4-topic discussion coverage. That explains why R001-R003 all pass the suite today. | Extend `tests/test_synthesis.py` with content assertions for the top signal section, a stale-topic-note failure case, and a four-topic week that verifies `Worth discussing` covers the active/dominant topics. Keep these focused on rendered content, not just file existence. |

## Remediation Roadmap

### Fix Now (Blockers)
- R001 — the top section is supposed to reduce leadership-prep scanning, but it currently reads like counters rather than a brief.
- R002 — stale topic-note links can make the brief’s evidence trail internally inconsistent even when generation succeeds.

### Fix Soon (High ROI)
- R003 — small logic change, high usefulness payoff; it prevents relevant topic movement from disappearing from the section leaders are most likely to read.
- R004 — once added, these tests should keep the brief contract from regressing during Sprint 7 hardening.

### Fix Later (Refactors)
- Pull section-ranking and signal-bullet construction into small helpers with explicit tests so monthly synthesis work does not duplicate brittle ordering logic.

## Patch Suggestions

```python
# src/leeknowledge/synthesis.py:347-366 — BEFORE
bullets = [
    f"- {len(weekly_bookmarks)} bookmarks landed in scope for this week, spanning {len(active_topic_keys)} active topics.",
]
...
return bullets[:5]

# AFTER
bullets = []
for bookmark in cited_bookmarks[:3]:
    topic_label = ", ".join(TOPIC_DEFINITIONS[key].title for key in bookmark.topic_keys[:2]) or "Uncategorized"
    bullets.append(
        f"- {topic_label}: {bookmark.context} ([note]({bookmark.note_link}); [x]({bookmark.source_url}))"
    )
if len(weekly_bookmarks) > len(cited_bookmarks):
    bullets.append(
        f"- {len(weekly_bookmarks)} total bookmarks were in scope; {len(cited_bookmarks)} are cited directly below."
    )
return bullets[:5]
```

```python
# src/leeknowledge/synthesis.py:209-215 — BEFORE
for topic_key in active_topic_keys:
    topic_note_path = vault_root / TOPIC_NOTES_DIRNAME / f"{topic_key}.md"
    if not topic_note_path.exists():
        raise SynthesisError(...)

# AFTER
for topic_key in active_topic_keys:
    topic_note_path = vault_root / TOPIC_NOTES_DIRNAME / f"{topic_key}.md"
    if not topic_note_path.exists():
        raise SynthesisError(...)
    note_text = topic_note_path.read_text(encoding="utf-8")
    expected_links = {
        bookmark.note_link
        for bookmark in weekly_bookmarks
        if topic_key in bookmark.topic_keys
    }
    missing_links = [link for link in expected_links if link not in note_text]
    if missing_links:
        raise SynthesisError(
            f"Topic note is stale for active topic '{topic_key}': {topic_note_path}. Run 'topics' before 'synthesize'."
        )
```

```python
# src/leeknowledge/synthesis.py:417 — BEFORE
lines = [prompts_by_topic[topic_key] for topic_key in active_topic_keys[:3]]

# AFTER
ranked_topic_keys = sorted(
    active_topic_keys,
    key=lambda topic_key: (
        sum(topic_key in bookmark.topic_keys for bookmark in weekly_bookmarks),
        max(
            (bookmark.sort_date for bookmark in weekly_bookmarks if topic_key in bookmark.topic_keys),
            default=datetime.min.replace(tzinfo=timezone.utc),
        ),
    ),
    reverse=True,
)
lines = [prompts_by_topic[topic_key] for topic_key in ranked_topic_keys[: min(3, len(ranked_topic_keys))]]
```

## Test Additions Recommended
- [ ] Test: a 4-topic week should render at least one evidence-grounded signal bullet that includes bookmark context, not only aggregate counts.
- [ ] Test: `generate_weekly_synthesis()` should fail when linked topic notes exist but are stale relative to the current weekly corpus.
- [ ] Test: when all four topics are active, `Worth discussing` should include the active/dominant topics rather than dropping the taxonomy’s fourth key by default.
- [ ] Test: alias-note snapshot bullets should stay aligned with the weekly note’s improved signal bullets so the shortcut artifact remains useful.
