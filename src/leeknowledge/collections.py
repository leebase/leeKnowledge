"""
Deterministic curated collection-note generation for active initiatives.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from leeknowledge.db import APP_DB_PATH, get_connection
from leeknowledge.exporter import (
    DEFAULT_VAULT_DIR,
    build_bookmark_note_path,
    build_source_link,
    select_bookmark_note_date,
)
from leeknowledge.metadata import (
    ORGANIZATIONAL_IMPACT_VALUES,
    PROMPT_VERSION as METADATA_PROMPT_VERSION,
    SCHEMA_VERSION as METADATA_SCHEMA_VERSION,
    STRATEGIC_RELEVANCE_VALUES,
    TIME_HORIZON_VALUES,
)
from leeknowledge.topics import TOPIC_DEFINITIONS, assign_topics

COLLECTIONS_DIRNAME = "collections"
DEFAULT_DEFINITIONS_PATH = Path("playbooks/curated-collections.yaml")
DEFINITION_VERSION = "sprint-9-v1"
MAX_DEFINITIONS = 5
MAX_ALLOWED_ITEMS = 12
WEEKLY_NOTE_PATTERN = re.compile(r"\b(\d{4}-W\d{2})\b")
SOURCE_URL_PATTERN = re.compile(r"https://x\.com/i/web/status/([A-Za-z0-9_\-]+)")


class CollectionGenerationError(RuntimeError):
    """Raised when curated-collection generation cannot complete safely."""


@dataclass(frozen=True)
class CollectionRunResult:
    generated_note_count: int
    written_paths: tuple[Path, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CollectionDefinition:
    initiative_slug: str
    title: str
    status: str
    leadership_question: str
    scope_note: str
    topic_keys: tuple[str, ...]
    metadata_preferences: Mapping[str, tuple[str, ...]]
    source_window_days: int
    max_items: int
    weekly_priority: bool
    include_tags_any: tuple[str, ...]
    description: str | None = None


@dataclass(frozen=True)
class CollectionCandidate:
    tweet_id: str
    bookmark_date: str
    sort_date: datetime
    author_handle: str
    context: str
    note_path: Path
    note_link: str
    source_label: str | None
    source_url: str | None
    topic_keys: tuple[str, ...]
    topic_matches: tuple[str, ...]
    tags: tuple[str, ...]
    tag_matches: tuple[str, ...]
    strategic_relevance: str | None
    time_horizon: str | None
    organizational_impact: str | None
    leadership_question: str | None
    metadata_is_current: bool
    weekly_mentions: tuple[str, ...]
    inclusion_reasons: tuple[str, ...]
    precedence_bucket: int


@dataclass(frozen=True)
class WeeklyMention:
    period_key: str
    note_path: Path


def generate_collection_notes(
    *,
    db_path: Path | str = APP_DB_PATH,
    vault_dir: Path | str = DEFAULT_VAULT_DIR,
    definitions_path: Path | str = DEFAULT_DEFINITIONS_PATH,
) -> CollectionRunResult:
    """Render one curated collection note per checked-in initiative definition."""

    resolved_db_path = Path(db_path)
    if not resolved_db_path.exists():
        raise CollectionGenerationError(f"SQLite database does not exist: {resolved_db_path}")

    vault_root = Path(vault_dir)
    definitions = load_collection_definitions(definitions_path)
    weekly_mentions = _scan_weekly_mentions(vault_root)

    with get_connection(resolved_db_path) as connection:
        _validate_collection_database(connection, resolved_db_path)
        rows = connection.execute(
            """
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
                e.validation_status AS enrichment_validation_status,
                m.strategic_relevance,
                m.time_horizon,
                m.organizational_impact,
                m.leadership_question,
                m.validation_status AS metadata_validation_status,
                m.prompt_version AS metadata_prompt_version,
                m.schema_version AS metadata_schema_version
            FROM bookmarks AS b
            LEFT JOIN enrichments AS e ON e.tweet_id = b.tweet_id
            LEFT JOIN leadership_metadata AS m ON m.tweet_id = b.tweet_id
            ORDER BY b.first_seen_at DESC, b.tweet_id DESC
            """
        ).fetchall()

    collections_root = vault_root / COLLECTIONS_DIRNAME
    collections_root.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    written_paths: list[Path] = []

    note_summaries: list[tuple[CollectionDefinition, Path, int]] = []

    for definition in definitions:
        candidates = _select_candidates(
            definition=definition,
            rows=rows,
            vault_root=vault_root,
            weekly_mentions=weekly_mentions,
        )
        note_path = collections_root / f"{definition.initiative_slug}.md"
        content = _render_collection_note(
            definition=definition,
            candidates=candidates,
            generated_at=generated_at,
            note_path=note_path,
            vault_root=vault_root,
            weekly_mentions=weekly_mentions,
            definitions_path=Path(definitions_path),
        )
        _write_atomically(note_path, content)
        written_paths.append(note_path)
        note_summaries.append((definition, note_path, len(candidates)))

    index_path = collections_root / "index.md"
    index_content = _render_collection_index_note(
        note_summaries=note_summaries,
        generated_at=generated_at,
        index_path=index_path,
        definitions_path=Path(definitions_path),
    )
    _write_atomically(index_path, index_content)
    written_paths.append(index_path)

    return CollectionRunResult(
        generated_note_count=len(definitions),
        written_paths=tuple(written_paths),
    )


def load_collection_definitions(
    definitions_path: Path | str = DEFAULT_DEFINITIONS_PATH,
) -> tuple[CollectionDefinition, ...]:
    """Load and validate checked-in initiative definitions."""

    path = Path(definitions_path)
    if not path.exists():
        raise CollectionGenerationError(f"Collection definitions file does not exist: {path}")

    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CollectionGenerationError(f"Collection definitions file is not valid YAML: {path}") from exc

    if not isinstance(parsed, dict) or not isinstance(parsed.get("collections"), list):
        raise CollectionGenerationError(
            "Collection definitions file must contain a top-level 'collections' list."
        )

    raw_definitions = parsed["collections"]
    if not raw_definitions:
        raise CollectionGenerationError("Collection definitions file must define at least one initiative.")
    if len(raw_definitions) > MAX_DEFINITIONS:
        raise CollectionGenerationError(
            f"Collection definitions file may define at most {MAX_DEFINITIONS} initiatives."
        )

    definitions: list[CollectionDefinition] = []
    seen_slugs: set[str] = set()
    for raw in raw_definitions:
        if not isinstance(raw, dict):
            raise CollectionGenerationError("Each collection definition must be a mapping.")

        initiative_slug = _require_string(raw, "initiative_slug")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", initiative_slug):
            raise CollectionGenerationError(
                f"Invalid initiative_slug '{initiative_slug}'. Use lowercase kebab-case only."
            )
        if initiative_slug in seen_slugs:
            raise CollectionGenerationError(f"Duplicate initiative_slug '{initiative_slug}'.")
        seen_slugs.add(initiative_slug)

        status = _require_string(raw, "status")
        if status not in {"active", "watching"}:
            raise CollectionGenerationError(
                f"Invalid status '{status}' for {initiative_slug}. Use 'active' or 'watching'."
            )

        topic_keys = tuple(raw.get("topic_keys") or ())
        if not isinstance(raw.get("topic_keys", []), list):
            raise CollectionGenerationError(f"topic_keys must be a list for {initiative_slug}.")
        invalid_topic_keys = [topic_key for topic_key in topic_keys if topic_key not in TOPIC_DEFINITIONS]
        if invalid_topic_keys:
            raise CollectionGenerationError(
                f"Unknown topic_keys for {initiative_slug}: {', '.join(invalid_topic_keys)}"
            )

        include_tags_any = tuple(_normalize_text(tag) for tag in (raw.get("include_tags_any") or ()))
        if raw.get("include_tags_any") is not None and not isinstance(raw.get("include_tags_any"), list):
            raise CollectionGenerationError(f"include_tags_any must be a list for {initiative_slug}.")

        metadata_preferences = _validate_metadata_preferences(
            raw.get("metadata_preferences") or {},
            initiative_slug=initiative_slug,
        )

        source_window_days = int(raw.get("source_window_days", 45))
        if source_window_days <= 0:
            raise CollectionGenerationError(f"source_window_days must be positive for {initiative_slug}.")

        max_items = int(raw.get("max_items", 8))
        if max_items <= 0 or max_items > MAX_ALLOWED_ITEMS:
            raise CollectionGenerationError(
                f"max_items must be between 1 and {MAX_ALLOWED_ITEMS} for {initiative_slug}."
            )

        weekly_priority = bool(raw.get("weekly_priority", True))
        if raw.get("weekly_priority") not in (None, True, False):
            raise CollectionGenerationError(f"weekly_priority must be a boolean for {initiative_slug}.")

        definitions.append(
            CollectionDefinition(
                initiative_slug=initiative_slug,
                title=_require_string(raw, "title"),
                status=status,
                leadership_question=_require_string(raw, "leadership_question"),
                scope_note=_require_string(raw, "scope_note"),
                topic_keys=topic_keys,
                metadata_preferences=metadata_preferences,
                source_window_days=source_window_days,
                max_items=max_items,
                weekly_priority=weekly_priority,
                include_tags_any=tuple(tag for tag in include_tags_any if tag),
                description=_optional_string(raw, "description"),
            )
        )

    return tuple(definitions)


def _select_candidates(
    *,
    definition: CollectionDefinition,
    rows,
    vault_root: Path,
    weekly_mentions: Mapping[str, tuple[WeeklyMention, ...]],
) -> list[CollectionCandidate]:
    now = datetime.now(timezone.utc)
    earliest_allowed = now - timedelta(days=definition.source_window_days)
    selected: list[CollectionCandidate] = []

    for row in rows:
        bookmark_date = select_bookmark_note_date(row)
        if bookmark_date.tzinfo is None:
            bookmark_date = bookmark_date.replace(tzinfo=timezone.utc)
        if bookmark_date < earliest_allowed:
            continue

        note_path = build_bookmark_note_path(vault_root, row)
        matched_topics = assign_topics(row)
        topic_matches = tuple(topic_key for topic_key in definition.topic_keys if topic_key in matched_topics)
        tags = tuple(_load_json_list(row["tags"]))
        tag_matches = tuple(
            tag for tag in tags if _normalize_text(tag) in set(definition.include_tags_any)
        )
        bookmark_weekly_mentions = weekly_mentions.get(str(row["tweet_id"]), ())
        weekly_periods = tuple(mention.period_key for mention in bookmark_weekly_mentions)
        metadata_is_current = _metadata_is_current(row)
        metadata_fit = _metadata_matches_preferences(row, definition.metadata_preferences) if metadata_is_current else False
        has_topic_match = bool(topic_matches)
        has_tag_match = bool(tag_matches)
        has_weekly_mention = bool(weekly_periods) and definition.weekly_priority

        if not _candidate_is_allowed(
            has_topic_match=has_topic_match,
            metadata_fit=metadata_fit,
            has_weekly_mention=has_weekly_mention,
            has_tag_match=has_tag_match,
        ):
            continue

        if not note_path.exists():
            raise CollectionGenerationError(
                f"Bookmark note does not exist for tweet {row['tweet_id']}: {note_path}. Run 'export' before 'collections'."
            )

        note_link = _relative_link(vault_root / COLLECTIONS_DIRNAME / f"{definition.initiative_slug}.md", note_path)
        inclusion_reasons = _build_inclusion_reasons(
            definition=definition,
            topic_matches=topic_matches,
            tag_matches=tag_matches,
            row=row,
            weekly_periods=weekly_periods,
            metadata_is_current=metadata_is_current,
            metadata_fit=metadata_fit,
        )
        source_link = build_source_link(row)
        selected.append(
            CollectionCandidate(
                tweet_id=str(row["tweet_id"]),
                bookmark_date=bookmark_date.strftime("%Y-%m-%d"),
                sort_date=bookmark_date,
                author_handle=_author_handle(row),
                context=_build_context(row),
                note_path=note_path,
                note_link=note_link,
                source_label=source_link[0] if source_link else None,
                source_url=source_link[1] if source_link else None,
                topic_keys=tuple(matched_topics.keys()),
                topic_matches=topic_matches,
                tags=tags,
                tag_matches=tag_matches,
                strategic_relevance=row["strategic_relevance"],
                time_horizon=row["time_horizon"],
                organizational_impact=row["organizational_impact"],
                leadership_question=row["leadership_question"],
                metadata_is_current=metadata_is_current,
                weekly_mentions=weekly_periods,
                inclusion_reasons=inclusion_reasons,
                precedence_bucket=_precedence_bucket(
                    has_topic_match=has_topic_match,
                    metadata_fit=metadata_fit,
                    has_weekly_mention=has_weekly_mention,
                    has_tag_match=has_tag_match,
                ),
            )
        )

    selected.sort(
        key=lambda candidate: (
            candidate.precedence_bucket,
            -_strategic_rank(candidate.strategic_relevance),
            -candidate.sort_date.timestamp(),
            candidate.tweet_id,
        )
    )
    return selected[: definition.max_items]


def _candidate_is_allowed(
    *,
    has_topic_match: bool,
    metadata_fit: bool,
    has_weekly_mention: bool,
    has_tag_match: bool,
) -> bool:
    del has_weekly_mention
    if has_topic_match:
        return True
    if metadata_fit and has_tag_match:
        return True
    return False


def _precedence_bucket(
    *,
    has_topic_match: bool,
    metadata_fit: bool,
    has_weekly_mention: bool,
    has_tag_match: bool,
) -> int:
    if has_topic_match and metadata_fit:
        return 0
    if has_topic_match and has_weekly_mention:
        return 1
    if has_topic_match or (metadata_fit and has_tag_match):
        return 2
    return 4


def _build_inclusion_reasons(
    *,
    definition: CollectionDefinition,
    topic_matches: tuple[str, ...],
    tag_matches: tuple[str, ...],
    row: Mapping[str, Any],
    weekly_periods: tuple[str, ...],
    metadata_is_current: bool,
    metadata_fit: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if topic_matches:
        topic_titles = ", ".join(TOPIC_DEFINITIONS[topic_key].title for topic_key in topic_matches)
        reasons.append(f"topic match: {topic_titles}")
    if metadata_is_current and metadata_fit:
        reasons.append(f"metadata fit: {_render_metadata_from_row(row)}")
    if tag_matches:
        reasons.append(f"tag match: {', '.join(tag_matches[:3])}")
    if weekly_periods and definition.weekly_priority:
        reasons.append(f"recent weekly mention: {', '.join(weekly_periods[:2])}")
    return tuple(reasons)


def _render_collection_note(
    *,
    definition: CollectionDefinition,
    candidates: list[CollectionCandidate],
    generated_at: str,
    note_path: Path,
    vault_root: Path,
    weekly_mentions: Mapping[str, tuple[WeeklyMention, ...]],
    definitions_path: Path,
) -> str:
    related_weeklies = _related_weekly_links(candidates, note_path, weekly_mentions)
    related_topics = _related_topic_links(definition, note_path, vault_root)
    lines = [
        "---",
        'note_type: "curated_collection"',
        f'initiative_slug: "{definition.initiative_slug}"',
        f'initiative_title: "{_escape_quotes(definition.title)}"',
        f'status: "{definition.status}"',
        f'generated_at: "{generated_at}"',
        f"bookmark_count: {len(candidates)}",
        f"source_window: {definition.source_window_days}",
        f'definition_version: "{DEFINITION_VERSION}"',
        "---",
        "",
        f"# {definition.title}",
        "",
        "Generated initiative view from local bookmark, topic, synthesis, and metadata state. Regenerate instead of editing by hand.",
        "",
    ]
    if definition.description:
        lines.extend([definition.description, ""])
    lines.extend(
        [
            "## Leadership question",
            "",
            definition.leadership_question,
            "",
            "## Scope",
            "",
            f"- Status: {definition.status.replace('-', ' ').title()}",
            f"- Scope note: {definition.scope_note}",
            f"- Source window: last {definition.source_window_days} days",
            f"- Target size: up to {definition.max_items} items",
            "",
            "## Why these items are here",
            "",
        ]
    )
    if definition.topic_keys:
        lines.append(
            "- Preferred topics: "
            + ", ".join(TOPIC_DEFINITIONS[topic_key].title for topic_key in definition.topic_keys)
        )
    if definition.include_tags_any:
        lines.append("- Tag hints: " + ", ".join(definition.include_tags_any))
    if definition.metadata_preferences:
        lines.append("- Metadata preferences: " + _render_metadata_preferences(definition.metadata_preferences))
    if definition.weekly_priority:
        lines.append("- Weekly synthesis mentions act as a tie-breaker, not a hard requirement.")
    else:
        lines.append("- Weekly synthesis mentions are ignored for prioritization in this collection.")

    lines.extend(["", "## Related views", ""])
    if related_topics:
        lines.extend(f"- Topic note: {link}" for link in related_topics)
    if related_weeklies:
        lines.extend(f"- Weekly brief: {link}" for link in related_weeklies)
    if not related_topics and not related_weeklies:
        lines.append("- None yet.")

    lines.extend(["", "## Current evidence", ""])
    if not candidates:
        lines.append("- No current evidence met the initiative definition in the configured source window.")
    else:
        for candidate in candidates:
            lines.append(f"- {candidate.bookmark_date} — {candidate.author_handle} — {candidate.context}")
            lines.append(f"  - Inclusion reasons: {'; '.join(candidate.inclusion_reasons)}")
            metadata_line = _render_candidate_metadata(candidate)
            if metadata_line:
                lines.append(f"  - Triage: {metadata_line}")
            if _should_render_leadership_question(candidate):
                lines.append(f"  - Leadership question: {candidate.leadership_question}")
            if candidate.topic_matches:
                topic_links = ", ".join(
                    f"[{TOPIC_DEFINITIONS[topic_key].title}]({_relative_link(note_path, vault_root / 'topics' / f'{topic_key}.md')})"
                    for topic_key in candidate.topic_matches
                    if (vault_root / "topics" / f"{topic_key}.md").exists()
                )
                if topic_links:
                    lines.append(f"  - Related topics: {topic_links}")
            if candidate.weekly_mentions:
                weekly_links = ", ".join(
                    _link_for_weekly_period(note_path, vault_root, period_key)
                    for period_key in candidate.weekly_mentions[:2]
                    if (vault_root / "synthesis" / "weekly" / period_key[:4] / f"{period_key}.md").exists()
                )
                if weekly_links:
                    lines.append(f"  - Recent weekly briefs: {weekly_links}")
            lines.append(f"  - Bookmark note: [Open note]({candidate.note_link})")
            if candidate.source_url and candidate.source_label:
                lines.append(f"  - Source: [{candidate.source_label}]({candidate.source_url})")

    lines.extend(["", "## Gaps or watch items", ""])
    if not candidates:
        lines.append("- No bookmarks currently satisfy this initiative framing. Keep the question and scope, then re-run after new evidence lands.")
    elif len(candidates) < min(3, definition.max_items):
        lines.append("- Evidence is still thin. Re-run after future export/topic/metadata/synthesis updates to see whether the initiative gains stronger support.")
    else:
        lines.append("- The collection is intentionally selective. Open the linked topic notes and weekly briefs if you need broader context.")

    lines.extend(
        [
            "",
            "## Generation notes",
            "",
            f"- Definitions come from `{definitions_path.as_posix()}`.",
            "- This note is regenerated from existing local state only.",
            "- It does not call X, Playwright, or a new LLM pass.",
            "- Source bookmark notes remain separate from these initiative views.",
        ]
    )
    return "\n".join(lines)


def _render_collection_index_note(
    *,
    note_summaries: list[tuple[CollectionDefinition, Path, int]],
    generated_at: str,
    index_path: Path,
    definitions_path: Path,
) -> str:
    lines = [
        "---",
        'note_type: "collection_index"',
        f'generated_at: "{generated_at}"',
        f"collection_count: {len(note_summaries)}",
        f'definition_version: "{DEFINITION_VERSION}"',
        "---",
        "",
        "# Curated Collections",
        "",
        "Generated entrypoint for initiative-centered collection notes. Open one collection when you want a bounded, evidence-backed view for a live strategy thread.",
        "",
        "## Current collections",
        "",
    ]
    if not note_summaries:
        lines.append("- No curated collections are defined yet.")
    else:
        for definition, note_path, bookmark_count in note_summaries:
            lines.append(
                f"- [{definition.title}]({_relative_link(index_path, note_path)}) — {definition.status.title()} — {bookmark_count} evidence item{'s' if bookmark_count != 1 else ''}"
            )
            lines.append(f"  - Leadership question: {definition.leadership_question}")
            lines.append(f"  - Scope: {definition.scope_note}")

    lines.extend(
        [
            "",
            "## Generation notes",
            "",
            f"- Definitions come from `{definitions_path.as_posix()}`.",
            "- Re-run `leeknowledge collections` after export, topics, metadata, or synthesis updates.",
            "- Collection notes are generated views over existing local state, not manual project trackers.",
        ]
    )
    return "\n".join(lines)


def _related_topic_links(
    definition: CollectionDefinition,
    note_path: Path,
    vault_root: Path,
) -> list[str]:
    links: list[str] = []
    for topic_key in definition.topic_keys:
        topic_note_path = vault_root / "topics" / f"{topic_key}.md"
        if not topic_note_path.exists():
            continue
        links.append(f"[{TOPIC_DEFINITIONS[topic_key].title}]({_relative_link(note_path, topic_note_path)})")
    return links


def _related_weekly_links(
    candidates: list[CollectionCandidate],
    note_path: Path,
    weekly_mentions: Mapping[str, tuple[WeeklyMention, ...]],
) -> list[str]:
    period_keys: list[str] = []
    for candidate in candidates:
        for mention in weekly_mentions.get(candidate.tweet_id, ()):
            if mention.period_key not in period_keys:
                period_keys.append(mention.period_key)
    return [_link_for_weekly_period(note_path, note_path.parents[1], period_key) for period_key in period_keys[:3]]


def _link_for_weekly_period(note_path: Path, vault_root: Path, period_key: str) -> str:
    weekly_note_path = vault_root / "synthesis" / "weekly" / period_key[:4] / f"{period_key}.md"
    return f"[{period_key}]({_relative_link(note_path, weekly_note_path)})"


def _scan_weekly_mentions(vault_root: Path) -> dict[str, tuple[WeeklyMention, ...]]:
    mentions: dict[str, list[WeeklyMention]] = {}
    weekly_root = vault_root / "synthesis" / "weekly"
    if not weekly_root.exists():
        return {}

    for weekly_note_path in sorted(weekly_root.glob("**/*.md")):
        content = weekly_note_path.read_text(encoding="utf-8")
        period_match = WEEKLY_NOTE_PATTERN.search(weekly_note_path.stem)
        if not period_match:
            period_match = WEEKLY_NOTE_PATTERN.search(content)
        if not period_match:
            continue
        period_key = period_match.group(1)
        for tweet_id in sorted(set(SOURCE_URL_PATTERN.findall(content))):
            mentions.setdefault(tweet_id, []).append(
                WeeklyMention(period_key=period_key, note_path=weekly_note_path)
            )

    return {
        tweet_id: tuple(
            sorted(
                rows,
                key=lambda mention: mention.period_key,
                reverse=True,
            )
        )
        for tweet_id, rows in mentions.items()
    }


def _validate_collection_database(connection, db_path: Path) -> None:
    try:
        connection.execute(
            "SELECT tweet_id, text, raw_urls, first_seen_at FROM bookmarks LIMIT 1"
        ).fetchall()
        connection.execute(
            "SELECT tweet_id, summary, tags, topic, validation_status FROM enrichments LIMIT 1"
        ).fetchall()
        connection.execute(
            """
            SELECT tweet_id, strategic_relevance, time_horizon, organizational_impact,
                   leadership_question, validation_status, prompt_version, schema_version
            FROM leadership_metadata LIMIT 1
            """
        ).fetchall()
    except Exception as exc:  # pragma: no cover - defensive wrapper.
        raise CollectionGenerationError(
            f"SQLite database is not ready for collection-note generation: {db_path}"
        ) from exc


def _validate_metadata_preferences(
    raw_preferences: Mapping[str, Any],
    *,
    initiative_slug: str,
) -> Mapping[str, tuple[str, ...]]:
    if not isinstance(raw_preferences, Mapping):
        raise CollectionGenerationError(
            f"metadata_preferences must be a mapping for {initiative_slug}."
        )

    allowed_fields = {
        "strategic_relevance": STRATEGIC_RELEVANCE_VALUES,
        "time_horizon": TIME_HORIZON_VALUES,
        "organizational_impact": ORGANIZATIONAL_IMPACT_VALUES,
    }
    validated: dict[str, tuple[str, ...]] = {}
    for field_name, raw_value in raw_preferences.items():
        if field_name not in allowed_fields:
            raise CollectionGenerationError(
                f"Unknown metadata preference '{field_name}' for {initiative_slug}."
            )
        if isinstance(raw_value, str):
            values = (raw_value,)
        elif isinstance(raw_value, list):
            values = tuple(str(item) for item in raw_value)
        else:
            raise CollectionGenerationError(
                f"metadata preference '{field_name}' must be a string or list for {initiative_slug}."
            )
        invalid_values = [value for value in values if value not in allowed_fields[field_name]]
        if invalid_values:
            raise CollectionGenerationError(
                f"Invalid values for {field_name} in {initiative_slug}: {', '.join(invalid_values)}"
            )
        validated[field_name] = values
    return validated


def _metadata_matches_preferences(
    row: Mapping[str, Any],
    preferences: Mapping[str, tuple[str, ...]],
) -> bool:
    if not preferences:
        return False
    for field_name, allowed_values in preferences.items():
        if row[field_name] not in allowed_values:
            return False
    return True


def _metadata_is_current(row: Mapping[str, Any]) -> bool:
    return (
        row["metadata_validation_status"] == "valid"
        and row["metadata_prompt_version"] == METADATA_PROMPT_VERSION
        and row["metadata_schema_version"] == METADATA_SCHEMA_VERSION
    )


def _render_metadata_from_row(row: Mapping[str, Any]) -> str:
    parts = [row["strategic_relevance"], row["time_horizon"], row["organizational_impact"]]
    return " · ".join(str(part).replace("-", " ").title() for part in parts if part)


def _render_candidate_metadata(candidate: CollectionCandidate) -> str | None:
    if not candidate.metadata_is_current:
        return None
    if not all((candidate.strategic_relevance, candidate.time_horizon, candidate.organizational_impact)):
        return None
    return " · ".join(
        [
            str(candidate.strategic_relevance).replace("-", " ").title(),
            str(candidate.time_horizon).replace("-", " ").title(),
            str(candidate.organizational_impact).replace("-", " ").title(),
        ]
    )


def _should_render_leadership_question(candidate: CollectionCandidate) -> bool:
    if not candidate.metadata_is_current:
        return False
    if not isinstance(candidate.leadership_question, str) or not candidate.leadership_question.strip():
        return False
    return candidate.strategic_relevance == "strategic" or (
        candidate.strategic_relevance == "important" and candidate.time_horizon == "now"
    )


def _render_metadata_preferences(preferences: Mapping[str, tuple[str, ...]]) -> str:
    rendered: list[str] = []
    for field_name in ("strategic_relevance", "time_horizon", "organizational_impact"):
        values = preferences.get(field_name)
        if not values:
            continue
        label = field_name.replace("_", " ")
        rendered.append(f"{label}={'/'.join(value.replace('-', ' ') for value in values)}")
    return "; ".join(rendered)


def _author_handle(row: Mapping[str, Any]) -> str:
    username = row["author_username"]
    if isinstance(username, str) and username.strip():
        return f"@{username.lstrip('@')}"
    display_name = row["author_display_name"]
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()
    return f"tweet {row['tweet_id']}"


def _build_context(row: Mapping[str, Any]) -> str:
    for value in (row["summary"], row["topic"], row["text"]):
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


def _load_json_list(value: Any) -> list[str]:
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item.strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, str) and item.strip()]
    return []


def _strategic_rank(value: str | None) -> int:
    return {"strategic": 3, "important": 2, "monitor": 1}.get(str(value), 0)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _require_string(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CollectionGenerationError(f"Missing required string field '{key}'.")
    return value.strip()


def _optional_string(raw: Mapping[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CollectionGenerationError(f"Optional field '{key}' must be a non-empty string when present.")
    return value.strip()


def _relative_link(from_path: Path, to_path: Path) -> str:
    return os.path.relpath(to_path, start=from_path.parent).replace(os.sep, "/")


def _escape_quotes(value: str) -> str:
    return value.replace('"', "'")


def _write_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as tmp:
        tmp.write(content)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
