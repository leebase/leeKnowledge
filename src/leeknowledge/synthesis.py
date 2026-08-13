"""
Deterministic weekly leadership synthesis generation.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from leeknowledge.db import APP_DB_PATH, get_connection
from leeknowledge.exporter import (
    DEFAULT_VAULT_DIR,
    ExportError,
    build_bookmark_note_path,
    build_source_link,
    select_bookmark_note_date,
)
from leeknowledge.metadata import PROMPT_VERSION as METADATA_PROMPT_VERSION
from leeknowledge.metadata import SCHEMA_VERSION as METADATA_SCHEMA_VERSION
from leeknowledge.topics import (
    TAXONOMY_VERSION,
    TOPIC_DEFINITIONS,
    TOPIC_NOTES_DIRNAME,
    assign_topics,
)

SYNTHESIS_DIRNAME = "synthesis"
BRIEFS_DIRNAME = "briefs"
LATEST_WEEKLY_BRIEF_NAME = "latest-weekly-signals.md"
MAX_DIRECT_CITATIONS = 8
MIN_DIRECT_CITATIONS = 5


class SynthesisError(RuntimeError):
    """Raised when weekly synthesis generation cannot complete safely."""


@dataclass(frozen=True)
class SynthesisRunResult:
    period_key: str
    weekly_note_path: Path
    latest_alias_path: Path
    bookmark_count: int
    cited_bookmark_count: int
    topic_count: int


@dataclass(frozen=True)
class WeeklyBookmark:
    tweet_id: str
    sort_date: datetime
    bookmark_date: str
    author_handle: str
    context: str
    note_path: Path
    note_link: str
    source_label: str | None
    source_url: str | None
    topic_keys: tuple[str, ...]
    matched_signals: dict[str, tuple[str, ...]]
    structured_signal: bool
    strategic_relevance: str | None
    time_horizon: str | None
    organizational_impact: str | None
    leadership_question: str | None
    metadata_validation_status: str | None
    metadata_prompt_version: str | None
    metadata_schema_version: str | None
    row: Mapping[str, Any]


def generate_weekly_synthesis(
    *,
    period_key: str,
    db_path: Path | str = APP_DB_PATH,
    vault_dir: Path | str = DEFAULT_VAULT_DIR,
) -> SynthesisRunResult:
    """Render one weekly leadership synthesis note and refresh the latest alias."""

    week = _parse_week_period(period_key)
    resolved_db_path = Path(db_path)
    if not resolved_db_path.exists():
        raise SynthesisError(f"SQLite database does not exist: {resolved_db_path}")

    vault_root = Path(vault_dir)

    with get_connection(resolved_db_path) as connection:
        _validate_synthesis_database(connection, resolved_db_path)
        has_leadership_metadata = (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'leadership_metadata'"
            ).fetchone()
            is not None
        )
        metadata_select = (
            """
                m.strategic_relevance,
                m.time_horizon,
                m.organizational_impact,
                m.leadership_question,
                m.validation_status AS metadata_validation_status,
                m.prompt_version AS metadata_prompt_version,
                m.schema_version AS metadata_schema_version
            """
            if has_leadership_metadata
            else """
                NULL AS strategic_relevance,
                NULL AS time_horizon,
                NULL AS organizational_impact,
                NULL AS leadership_question,
                NULL AS metadata_validation_status,
                NULL AS metadata_prompt_version,
                NULL AS metadata_schema_version
            """
        )
        metadata_join = (
            "LEFT JOIN leadership_metadata AS m ON m.tweet_id = b.tweet_id"
            if has_leadership_metadata
            else ""
        )
        rows = connection.execute(
            f"""
            SELECT
                b.tweet_id,
                b.source_name,
                b.source_type,
                b.source_item_id,
                b.source_ref,
                b.text,
                b.author_username,
                b.author_display_name,
                b.created_at,
                b.conversation_id,
                b.in_reply_to_id,
                b.media_urls,
                b.raw_urls,
                b.first_seen_at,
                e.summary,
                e.tags,
                e.entities,
                e.topic,
                e.model,
                e.prompt_version,
                e.schema_version,
                e.validation_status,
                e.enriched_at,
                {metadata_select}
            FROM bookmarks AS b
            LEFT JOIN enrichments AS e ON e.tweet_id = b.tweet_id
            {metadata_join}
            ORDER BY b.first_seen_at DESC, b.tweet_id DESC
            """
        ).fetchall()

    weekly_bookmarks = _build_weekly_bookmarks(rows=rows, vault_root=vault_root, week=week)
    active_topic_keys = _rank_active_topics(weekly_bookmarks)
    _validate_source_paths(vault_root=vault_root, weekly_bookmarks=weekly_bookmarks, active_topic_keys=active_topic_keys)

    cited_bookmarks = _select_cited_bookmarks(weekly_bookmarks)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    weekly_note_path = _weekly_note_path(vault_root, week)
    alias_path = vault_root / BRIEFS_DIRNAME / LATEST_WEEKLY_BRIEF_NAME

    weekly_content = _render_weekly_note(
        week=week,
        weekly_bookmarks=weekly_bookmarks,
        cited_bookmarks=cited_bookmarks,
        active_topic_keys=active_topic_keys,
        generated_at=generated_at,
        weekly_note_path=weekly_note_path,
        vault_root=vault_root,
    )
    alias_content = _render_latest_alias(
        week=week,
        weekly_bookmarks=weekly_bookmarks,
        cited_bookmarks=cited_bookmarks,
        active_topic_keys=active_topic_keys,
        generated_at=generated_at,
        alias_path=alias_path,
        weekly_note_path=weekly_note_path,
    )

    _write_atomically(weekly_note_path, weekly_content)
    _write_atomically(alias_path, alias_content)

    return SynthesisRunResult(
        period_key=week["period_key"],
        weekly_note_path=weekly_note_path,
        latest_alias_path=alias_path,
        bookmark_count=len(weekly_bookmarks),
        cited_bookmark_count=len(cited_bookmarks),
        topic_count=len(active_topic_keys),
    )


def _parse_week_period(period_key: str) -> dict[str, Any]:
    try:
        year_text, week_text = period_key.split("-W", maxsplit=1)
        year = int(year_text)
        week_number = int(week_text)
        start_date = date.fromisocalendar(year, week_number, 1)
    except (TypeError, ValueError):
        raise SynthesisError(
            f"Invalid weekly period '{period_key}'. Expected ISO week like 2026-W15."
        ) from None

    end_date = start_date + timedelta(days=6)
    return {
        "period_key": f"{year:04d}-W{week_number:02d}",
        "year": year,
        "week": week_number,
        "start_date": start_date,
        "end_date": end_date,
    }


def _build_weekly_bookmarks(*, rows, vault_root: Path, week: Mapping[str, Any]) -> list[WeeklyBookmark]:
    weekly_bookmarks: list[WeeklyBookmark] = []
    for row in rows:
        bookmark_datetime = select_bookmark_note_date(row)
        bookmark_day = bookmark_datetime.date()
        if bookmark_day < week["start_date"] or bookmark_day > week["end_date"]:
            continue

        matched_topics = assign_topics(row)
        note_path = build_bookmark_note_path(vault_root, row)
        note_link = _relative_link(_weekly_note_path(vault_root, week), note_path)
        source_link = build_source_link(row)
        weekly_bookmarks.append(
            WeeklyBookmark(
                tweet_id=str(row["tweet_id"]),
                sort_date=bookmark_datetime,
                bookmark_date=bookmark_datetime.strftime("%Y-%m-%d"),
                author_handle=_author_handle(row),
                context=_build_context(row),
                note_path=note_path,
                note_link=note_link,
                source_label=source_link[0] if source_link else None,
                source_url=source_link[1] if source_link else None,
                topic_keys=tuple(matched_topics.keys()),
                matched_signals={key: tuple(value) for key, value in matched_topics.items()},
                structured_signal=_has_structured_signal(row),
                strategic_relevance=row["strategic_relevance"],
                time_horizon=row["time_horizon"],
                organizational_impact=row["organizational_impact"],
                leadership_question=row["leadership_question"],
                metadata_validation_status=row["metadata_validation_status"],
                metadata_prompt_version=row["metadata_prompt_version"],
                metadata_schema_version=row["metadata_schema_version"],
                row=row,
            )
        )

    weekly_bookmarks.sort(key=lambda bookmark: (bookmark.sort_date, bookmark.tweet_id), reverse=True)
    return weekly_bookmarks


def _validate_source_paths(*, vault_root: Path, weekly_bookmarks: list[WeeklyBookmark], active_topic_keys: tuple[str, ...]) -> None:
    for bookmark in weekly_bookmarks:
        if not bookmark.note_path.exists():
            raise SynthesisError(
                f"Bookmark note does not exist for tweet {bookmark.tweet_id}: {bookmark.note_path}. Run 'export' before 'synthesize'."
            )

    for topic_key in active_topic_keys:
        topic_note_path = vault_root / TOPIC_NOTES_DIRNAME / f"{topic_key}.md"
        if not topic_note_path.exists():
            raise SynthesisError(
                f"Topic note does not exist for active weekly topic '{topic_key}': {topic_note_path}. Run 'export' and 'topics' before synthesis."
            )
        topic_note_mtime = topic_note_path.stat().st_mtime
        latest_bookmark_mtime = max(
            bookmark.note_path.stat().st_mtime
            for bookmark in weekly_bookmarks
            if topic_key in bookmark.topic_keys
        )
        if topic_note_mtime < latest_bookmark_mtime:
            raise SynthesisError(
                f"Topic note is stale for active weekly topic '{topic_key}': {topic_note_path}. Re-run 'topics' before 'synthesize'."
            )


def _select_cited_bookmarks(weekly_bookmarks: list[WeeklyBookmark]) -> list[WeeklyBookmark]:
    if len(weekly_bookmarks) <= MIN_DIRECT_CITATIONS:
        return list(weekly_bookmarks)

    selected: list[WeeklyBookmark] = []
    selected_ids: set[str] = set()

    active_topic_keys = list(_rank_active_topics(weekly_bookmarks))
    for topic_key in active_topic_keys:
        for bookmark in weekly_bookmarks:
            if bookmark.tweet_id in selected_ids:
                continue
            if topic_key not in bookmark.topic_keys:
                continue
            selected.append(bookmark)
            selected_ids.add(bookmark.tweet_id)
            break

    for bookmark in weekly_bookmarks:
        if len(selected) >= MAX_DIRECT_CITATIONS:
            break
        if bookmark.tweet_id in selected_ids:
            continue
        if bookmark.topic_keys:
            selected.append(bookmark)
            selected_ids.add(bookmark.tweet_id)

    for bookmark in weekly_bookmarks:
        if len(selected) >= MAX_DIRECT_CITATIONS:
            break
        if bookmark.tweet_id in selected_ids:
            continue
        selected.append(bookmark)
        selected_ids.add(bookmark.tweet_id)

    return selected


def _render_weekly_note(
    *,
    week: Mapping[str, Any],
    weekly_bookmarks: list[WeeklyBookmark],
    cited_bookmarks: list[WeeklyBookmark],
    active_topic_keys: tuple[str, ...],
    generated_at: str,
    weekly_note_path: Path,
    vault_root: Path,
) -> str:
    lines = [
        "---",
        'note_type: "leadership_synthesis"',
        'cadence: "weekly"',
        f'period_key: "{week["period_key"]}"',
        f'period_start: "{week["start_date"].isoformat()}"',
        f'period_end: "{week["end_date"].isoformat()}"',
        f'generated_at: "{generated_at}"',
        f"bookmark_count: {len(weekly_bookmarks)}",
        f"topic_count: {len(active_topic_keys)}",
        f'taxonomy_version: "{TAXONOMY_VERSION}"',
        "---",
        "",
        f"# Weekly Leadership Synthesis — {week['period_key']}",
        "",
        (
            "Generated leadership brief from local bookmark, enrichment, and topic-note state. "
            "Regenerate instead of editing by hand."
        ),
        "",
        (
            f"Coverage window: {week['start_date'].isoformat()} to {week['end_date'].isoformat()} "
            f"(ISO week {week['period_key']})."
        ),
        "",
        "## This week's signals",
        "",
    ]
    lines.extend(_signal_bullets(weekly_bookmarks, active_topic_keys, cited_bookmarks))
    lines.extend(["", "## Topic movement", ""])
    lines.extend(_topic_movement_lines(weekly_note_path, vault_root, active_topic_keys, weekly_bookmarks, cited_bookmarks))
    lines.extend(["", "## Worth discussing", ""])
    lines.extend(_worth_discussing_lines(weekly_bookmarks, active_topic_keys))
    lines.extend(["", "## Source trail", ""])
    lines.extend(_source_trail_lines(weekly_note_path, vault_root, active_topic_keys, cited_bookmarks))
    lines.extend(
        [
            "",
            "## Generation notes",
            "",
            "- This note is regenerated from SQLite state plus the shipped topic-note taxonomy.",
            "- Candidate selection and weekly windowing are deterministic for a fixed local corpus.",
            "- Observed signals come from cited bookmarks; implications are generated interpretation over those sources.",
        ]
    )
    return "\n".join(lines)


def _signal_bullets(
    weekly_bookmarks: list[WeeklyBookmark],
    active_topic_keys: tuple[str, ...],
    cited_bookmarks: list[WeeklyBookmark],
) -> list[str]:
    if not weekly_bookmarks:
        return [
            "- No bookmarks fell inside this weekly window, so this note records an explicit empty week.",
            "- Signal volume was light; no topic movement or cited sources were available.",
            "- Re-running the same week will update this same archived path and latest alias in place.",
        ]

    topic_counts = {
        topic_key: sum(topic_key in bookmark.topic_keys for bookmark in weekly_bookmarks)
        for topic_key in active_topic_keys
    }
    strongest_topics = [
        TOPIC_DEFINITIONS[topic_key].title
        for topic_key, count in topic_counts.items()
        if count == max(topic_counts.values(), default=0)
    ]
    structured_count = sum(bookmark.structured_signal for bookmark in weekly_bookmarks)
    uncategorized_count = sum(1 for bookmark in weekly_bookmarks if not bookmark.topic_keys)
    bullets = [
        f"- {len(weekly_bookmarks)} bookmarks landed in scope for this week, spanning {len(active_topic_keys)} active topics.",
    ]
    if cited_bookmarks:
        lead_examples = "; ".join(
            f"{bookmark.author_handle} on {bookmark.context}" for bookmark in cited_bookmarks[:2]
        )
        bullets.append(f"- Direct evidence this week: {lead_examples}")
    if strongest_topics:
        bullets.append(
            f"- Strongest visible movement: {', '.join(strongest_topics)} ({max(topic_counts.values())} observed items in the weekly slice)."
        )
    if structured_count:
        bullets.append(
            f"- {structured_count} bookmarks carried structured enrichment signals, which improved topic framing and citation selection."
        )
    if uncategorized_count:
        bullets.append(
            f"- {uncategorized_count} bookmarks remained uncategorized; review whether they are genuinely out of scope or expose taxonomy gaps."
        )
    elif len(cited_bookmarks) < len(weekly_bookmarks):
        bullets.append(
            f"- The brief cites {len(cited_bookmarks)} bookmarks directly and rolls the rest into topic counts to keep the weekly note readable."
        )
    return bullets[:5]


def _topic_movement_lines(
    weekly_note_path: Path,
    vault_root: Path,
    active_topic_keys: tuple[str, ...],
    weekly_bookmarks: list[WeeklyBookmark],
    cited_bookmarks: list[WeeklyBookmark],
) -> list[str]:
    if not active_topic_keys:
        return ["- No Sprint 6 topics were active in this week."]

    lines: list[str] = []
    cited_ids = {bookmark.tweet_id for bookmark in cited_bookmarks}
    for topic_key in active_topic_keys:
        definition = TOPIC_DEFINITIONS[topic_key]
        topic_note_path = vault_root / TOPIC_NOTES_DIRNAME / f"{topic_key}.md"
        topic_link = _relative_link(weekly_note_path, topic_note_path)
        topic_bookmarks = [bookmark for bookmark in weekly_bookmarks if topic_key in bookmark.topic_keys]
        cited_for_topic = [bookmark for bookmark in topic_bookmarks if bookmark.tweet_id in cited_ids][:3]
        lines.append(
            f"- [{definition.title}]({topic_link}) — {len(topic_bookmarks)} bookmarks in the weekly window."
        )
        if cited_for_topic:
            for bookmark in cited_for_topic:
                lines.append(
                    f"  - {bookmark.bookmark_date} — {bookmark.author_handle} — {bookmark.context}"
                )
                metadata_line = _render_metadata_labels(bookmark)
                if metadata_line:
                    lines.append(f"    - Triage: {metadata_line}")
                if _should_render_leadership_question(bookmark):
                    lines.append(
                        f"    - Leadership question: {bookmark.leadership_question}"
                    )
                lines.append(f"    - Bookmark note: [Open note]({bookmark.note_link})")
                if bookmark.source_url and bookmark.source_label:
                    lines.append(f"    - Source: [{bookmark.source_label}]({bookmark.source_url})")
        else:
            lines.append("  - No direct citations selected for this topic; it is still counted in the weekly totals.")
    return lines


def _worth_discussing_lines(
    weekly_bookmarks: list[WeeklyBookmark],
    active_topic_keys: tuple[str, ...],
) -> list[str]:
    if not weekly_bookmarks:
        return [
            "- No new bookmark evidence landed this week, so use the time to review whether the current topic taxonomy still matches what you want to track.",
        ]

    prompts_by_topic = {
        "ai-governance": "- Governance signal: decide whether any cited controls, auditability, or policy concerns should influence near-term operating guardrails.",
        "enterprise-agents": "- Agent operating model: ask which workflows are ready for broader rollout versus where evaluation and human review still need to mature.",
        "data-platform": "- Data-platform implication: check whether the week suggests changes to platform investments, observability, or semantic-layer priorities.",
        "vendor-landscape": "- Vendor evaluation: note whether launches, pricing, or comparison signals warrant a closer look at provider choices or negotiation posture.",
    }
    ranked_topics = list(_rank_active_topics(weekly_bookmarks))
    lines = [prompts_by_topic[topic_key] for topic_key in ranked_topics[:4]]
    if len(weekly_bookmarks) < MIN_DIRECT_CITATIONS:
        lines.append("- Signal volume was light this week; treat this brief as coverage confirmation rather than a strong directional read.")
    elif not active_topic_keys:
        lines.append("- Most bookmarks were uncategorized this week; review whether the taxonomy needs refinement before drawing leadership conclusions.")
    return lines


def _source_trail_lines(
    weekly_note_path: Path,
    vault_root: Path,
    active_topic_keys: tuple[str, ...],
    cited_bookmarks: list[WeeklyBookmark],
) -> list[str]:
    lines: list[str] = []
    if active_topic_keys:
        lines.append("- Topic notes")
        for topic_key in active_topic_keys:
            definition = TOPIC_DEFINITIONS[topic_key]
            topic_note_path = vault_root / TOPIC_NOTES_DIRNAME / f"{topic_key}.md"
            lines.append(
                f"  - [{definition.title}]({_relative_link(weekly_note_path, topic_note_path)})"
            )
    else:
        lines.append("- Topic notes: none active this week.")

    if cited_bookmarks:
        lines.append("- Directly cited bookmarks")
        for bookmark in cited_bookmarks:
            source_line = f"  - {bookmark.bookmark_date} — {bookmark.author_handle} — [Open note]({bookmark.note_link})"
            if bookmark.source_url and bookmark.source_label:
                source_line += f" — [{bookmark.source_label}]({bookmark.source_url})"
            metadata_line = _render_metadata_labels(bookmark)
            if metadata_line:
                source_line += f" — {metadata_line}"
            lines.append(source_line)
    else:
        lines.append("- Directly cited bookmarks: none for this week.")
    return lines


def _rank_active_topics(weekly_bookmarks: list[WeeklyBookmark]) -> tuple[str, ...]:
    topic_metrics: list[tuple[int, datetime, str]] = []
    for topic_key in TOPIC_DEFINITIONS:
        topic_bookmarks = [bookmark for bookmark in weekly_bookmarks if topic_key in bookmark.topic_keys]
        if not topic_bookmarks:
            continue
        topic_metrics.append(
            (
                len(topic_bookmarks),
                max(bookmark.sort_date for bookmark in topic_bookmarks),
                topic_key,
            )
        )
    topic_metrics.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return tuple(topic_key for _, _, topic_key in topic_metrics)


def _metadata_is_current(bookmark: WeeklyBookmark) -> bool:
    return (
        bookmark.metadata_validation_status == "valid"
        and bookmark.metadata_prompt_version == METADATA_PROMPT_VERSION
        and bookmark.metadata_schema_version == METADATA_SCHEMA_VERSION
    )


def _render_metadata_labels(bookmark: WeeklyBookmark) -> str | None:
    if not _metadata_is_current(bookmark):
        return None
    if not all(
        (
            bookmark.strategic_relevance,
            bookmark.time_horizon,
            bookmark.organizational_impact,
        )
    ):
        return None
    return " · ".join(
        [
            str(bookmark.strategic_relevance).replace("-", " ").title(),
            str(bookmark.time_horizon).replace("-", " ").title(),
            str(bookmark.organizational_impact).replace("-", " ").title(),
        ]
    )


def _should_render_leadership_question(bookmark: WeeklyBookmark) -> bool:
    if not _metadata_is_current(bookmark):
        return False
    if not isinstance(bookmark.leadership_question, str) or not bookmark.leadership_question.strip():
        return False
    return bookmark.strategic_relevance == "strategic" or (
        bookmark.strategic_relevance == "important" and bookmark.time_horizon == "now"
    )


def _render_latest_alias(
    *,
    week: Mapping[str, Any],
    weekly_bookmarks: list[WeeklyBookmark],
    cited_bookmarks: list[WeeklyBookmark],
    active_topic_keys: tuple[str, ...],
    generated_at: str,
    alias_path: Path,
    weekly_note_path: Path,
) -> str:
    lines = [
        "---",
        'note_type: "leadership_brief_alias"',
        'cadence: "weekly"',
        f'period_key: "{week["period_key"]}"',
        f'generated_at: "{generated_at}"',
        f'bookmark_count: {len(weekly_bookmarks)}',
        f'topic_count: {len(active_topic_keys)}',
        "---",
        "",
        "# Latest Weekly Signals",
        "",
        (
            f"Latest generated weekly leadership brief: [{week['period_key']}]({_relative_link(alias_path, weekly_note_path)})."
        ),
        "",
        f"Coverage window: {week['start_date'].isoformat()} to {week['end_date'].isoformat()}.",
        "",
        "## Snapshot",
        "",
    ]
    lines.extend(_signal_bullets(weekly_bookmarks, active_topic_keys, cited_bookmarks)[:3])
    lines.extend(
        [
            "",
            "## Source trail",
            "",
            f"- Canonical weekly brief: [{week['period_key']}]({_relative_link(alias_path, weekly_note_path)})",
        ]
    )
    for topic_key in active_topic_keys:
        lines.append(
            f"- Topic note: [{TOPIC_DEFINITIONS[topic_key].title}]({_relative_link(alias_path, Path(weekly_note_path).parents[3] / TOPIC_NOTES_DIRNAME / (topic_key + '.md'))})"
        )
    return "\n".join(lines)


def _weekly_note_path(vault_root: Path, week: Mapping[str, Any]) -> Path:
    return (
        vault_root
        / SYNTHESIS_DIRNAME
        / "weekly"
        / f"{week['year']:04d}"
        / f"{week['period_key']}.md"
    )


def _relative_link(from_path: Path, to_path: Path) -> str:
    return os.path.relpath(to_path, start=from_path.parent).replace(os.sep, "/")


def _author_handle(row: Mapping[str, Any]) -> str:
    username = row["author_username"]
    if isinstance(username, str) and username.strip():
        return f"@{username.lstrip('@')}"
    display_name = row["author_display_name"]
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()
    return f"tweet {row['tweet_id']}"


def _build_context(row: Mapping[str, Any]) -> str:
    for field in ("summary", "topic", "text"):
        value = row[field]
        if not isinstance(value, str):
            continue
        stripped = " ".join(value.split())
        if stripped:
            return _truncate(stripped, 160)
    return "No summary or text available."


def _truncate(text: str, length: int) -> str:
    if len(text) <= length:
        return text
    return text[: length - 1].rstrip() + "…"


def _has_structured_signal(row: Mapping[str, Any]) -> bool:
    return any(
        isinstance(row[key], str) and row[key].strip()
        for key in ("topic", "summary", "tags")
    )


def _validate_synthesis_database(connection, db_path: Path) -> None:
    try:
        rows = connection.execute(
            "SELECT tweet_id, text, created_at, raw_urls, first_seen_at FROM bookmarks LIMIT 1"
        ).fetchall()
        del rows
        rows = connection.execute(
            "SELECT tweet_id, summary, tags, topic FROM enrichments LIMIT 1"
        ).fetchall()
        del rows
    except Exception as exc:  # pragma: no cover - defensive wrapper.
        raise SynthesisError(
            f"SQLite database is not ready for weekly synthesis generation: {db_path}"
        ) from exc


def _write_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", delete=False, dir=path.parent, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
