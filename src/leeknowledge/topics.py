"""
Deterministic topic-index-note generation.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from leeknowledge.db import APP_DB_PATH, get_connection
from leeknowledge.exporter import (
    DEFAULT_VAULT_DIR,
    ExportError,
    build_bookmark_note_path,
    build_source_link,
    select_bookmark_note_date,
)

TOPIC_NOTES_DIRNAME = "topics"
TAXONOMY_VERSION = "sprint-6-v1"


class TopicGenerationError(RuntimeError):
    """Raised when topic-note generation cannot complete safely."""


@dataclass(frozen=True)
class TopicRunResult:
    """Summary of a completed topic-note generation run."""

    generated_note_count: int
    written_paths: tuple[Path, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TopicDefinition:
    key: str
    title: str
    scope: str
    exclusions: str
    grouping_hints: tuple[str, ...]
    strong_keywords: tuple[str, ...]
    summary_keywords: tuple[str, ...]
    text_keywords: tuple[str, ...]


@dataclass(frozen=True)
class TopicEntry:
    tweet_id: str
    note_path: Path
    note_link: str
    source_label: str | None
    source_url: str | None
    author_handle: str
    bookmark_date: str
    sort_date: datetime
    context: str
    matched_signals: tuple[str, ...]


TOPIC_DEFINITIONS: dict[str, TopicDefinition] = {
    "ai-governance": TopicDefinition(
        key="ai-governance",
        title="AI Governance",
        scope=(
            "AI policy, risk, compliance, safety, regulation, auditability, "
            "model controls, and operating guardrails."
        ),
        exclusions=(
            "Exclude generic launches, benchmarks, and agent implementation "
            "tips unless governance or risk is central."
        ),
        grouping_hints=(
            "Structured topic or tags mentioning governance, policy, risk, compliance, safety, evaluation, or guardrails.",
            "Summary text reinforcing regulation, auditability, responsible AI, or model-control framing.",
            "Raw tweet text only when governance language is more than a single weak mention.",
        ),
        strong_keywords=(
            "ai governance",
            "governance",
            "policy",
            "regulation",
            "regulated",
            "risk",
            "compliance",
            "safety",
            "guardrail",
            "guardrails",
            "audit",
            "auditability",
            "evaluation",
            "responsible ai",
            "model control",
            "model controls",
        ),
        summary_keywords=(
            "governance",
            "policy",
            "regulation",
            "risk",
            "compliance",
            "safety",
            "guardrail",
            "audit",
            "evaluation",
            "responsible ai",
            "model control",
        ),
        text_keywords=(
            "governance",
            "policy",
            "regulation",
            "risk",
            "compliance",
            "safety",
            "guardrail",
            "audit",
            "evaluation",
            "responsible ai",
            "model control",
        ),
    ),
    "enterprise-agents": TopicDefinition(
        key="enterprise-agents",
        title="Enterprise Agents",
        scope=(
            "Agent workflows, copilots, orchestration, evaluation, "
            "human-in-the-loop automation, and enterprise deployment patterns."
        ),
        exclusions=(
            "Exclude general model news or data-platform posts unless the "
            "operational agent pattern is central."
        ),
        grouping_hints=(
            "Structured topic or tags naming agents, agentic systems, copilots, orchestration, or workflow automation.",
            "Summary text connecting agents to enterprise rollout, evaluation, or human-in-the-loop operations.",
            "Raw tweet text must contain more than a single generic agent mention before it is grouped here.",
        ),
        strong_keywords=(
            "enterprise agents",
            "agent",
            "agents",
            "agentic",
            "copilot",
            "copilots",
            "orchestration",
            "workflow",
            "human-in-the-loop",
            "human in the loop",
            "tool use",
            "automation",
            "evaluation",
        ),
        summary_keywords=(
            "agent",
            "agents",
            "agentic",
            "copilot",
            "orchestration",
            "workflow",
            "human-in-the-loop",
            "human in the loop",
            "tool use",
            "automation",
            "evaluation",
        ),
        text_keywords=(
            "agent",
            "agents",
            "agentic",
            "copilot",
            "orchestration",
            "workflow",
            "human-in-the-loop",
            "human in the loop",
            "tool use",
            "automation",
            "evaluation",
        ),
    ),
    "data-platform": TopicDefinition(
        key="data-platform",
        title="Data Platform",
        scope=(
            "Data architecture, pipelines, analytics engineering, semantic "
            "layers, observability, data quality, and platform operating models."
        ),
        exclusions=(
            "Exclude pure AI product chatter unless there is a clear "
            "data-platform implication."
        ),
        grouping_hints=(
            "Structured topic or tags naming pipelines, warehouses, lakehouses, semantic layers, or analytics engineering.",
            "Summary text reinforcing platform design, observability, or data-quality operating patterns.",
            "Raw tweet text only when multiple data-platform signals appear together.",
        ),
        strong_keywords=(
            "data platform",
            "pipeline",
            "pipelines",
            "etl",
            "elt",
            "analytics engineering",
            "semantic layer",
            "semantic layers",
            "warehouse",
            "lakehouse",
            "observability",
            "data quality",
            "dbt",
        ),
        summary_keywords=(
            "data platform",
            "pipeline",
            "pipelines",
            "etl",
            "elt",
            "analytics engineering",
            "semantic layer",
            "warehouse",
            "lakehouse",
            "observability",
            "data quality",
            "dbt",
        ),
        text_keywords=(
            "data platform",
            "pipeline",
            "pipelines",
            "etl",
            "elt",
            "analytics engineering",
            "semantic layer",
            "warehouse",
            "lakehouse",
            "observability",
            "data quality",
            "dbt",
        ),
    ),
    "vendor-landscape": TopicDefinition(
        key="vendor-landscape",
        title="Vendor Landscape",
        scope=(
            "Vendor comparisons, provider launches, pricing, partnerships, "
            "competitive movement, and market scans."
        ),
        exclusions=(
            "Exclude general technical advice with no clear vendor, pricing, "
            "launch, comparison, or partnership angle."
        ),
        grouping_hints=(
            "Structured topic or tags pairing vendor names with launch, pricing, partnership, comparison, or benchmark framing.",
            "Summary text that describes provider movement, vendor positioning, or category comparison.",
            "Raw URLs are only weak support; a vendor/domain mention alone is not enough without movement or comparison language.",
        ),
        strong_keywords=(
            "launch",
            "pricing",
            "vendor",
            "partner",
            "partnership",
            "acquisition",
            "comparison",
            "benchmark",
            "model provider",
            "openai",
            "anthropic",
            "google",
            "microsoft",
            "snowflake",
            "databricks",
        ),
        summary_keywords=(
            "launch",
            "pricing",
            "vendor",
            "partner",
            "partnership",
            "acquisition",
            "comparison",
            "benchmark",
            "model provider",
            "openai",
            "anthropic",
            "google",
            "microsoft",
            "snowflake",
            "databricks",
        ),
        text_keywords=(
            "launch",
            "pricing",
            "vendor",
            "partner",
            "partnership",
            "acquisition",
            "comparison",
            "benchmark",
            "model provider",
            "openai",
            "anthropic",
            "google",
            "microsoft",
            "snowflake",
            "databricks",
        ),
    ),
}

VENDOR_MOVEMENT_KEYWORDS = (
    "launch",
    "pricing",
    "vendor",
    "partner",
    "partnership",
    "acquisition",
    "comparison",
    "benchmark",
    "model provider",
)
VENDOR_NAMES = (
    "openai",
    "anthropic",
    "google",
    "microsoft",
    "snowflake",
    "databricks",
)


def generate_topic_notes(
    db_path: Path | str = APP_DB_PATH,
    vault_dir: Path | str = DEFAULT_VAULT_DIR,
) -> TopicRunResult:
    """Render one deterministic topic index note per Sprint 6 topic."""

    resolved_db_path = Path(db_path)
    if not resolved_db_path.exists():
        raise TopicGenerationError(
            f"SQLite database does not exist: {resolved_db_path}"
        )

    vault_root = Path(vault_dir)

    topic_entries: dict[str, list[TopicEntry]] = {
        topic_key: [] for topic_key in TOPIC_DEFINITIONS
    }

    with get_connection(resolved_db_path) as connection:
        _validate_topic_database(connection, resolved_db_path)
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
                e.model,
                e.prompt_version,
                e.schema_version,
                e.validation_status,
                e.enriched_at
            FROM bookmarks AS b
            LEFT JOIN enrichments AS e ON e.tweet_id = b.tweet_id
            ORDER BY b.first_seen_at DESC, b.tweet_id DESC
            """
        ).fetchall()

        for row in rows:
            matched_topics = assign_topics(row)
            if not matched_topics:
                continue
            note_path = build_bookmark_note_path(vault_root, row)
            if not note_path.exists():
                raise TopicGenerationError(
                    f"Bookmark note does not exist for tweet {row['tweet_id']}: {note_path}. Run 'export' before 'topics'."
                )
            relative_note_path = note_path.relative_to(vault_root)
            note_link = Path("..") / relative_note_path
            note_date = select_bookmark_note_date(row)
            author_handle = _author_handle(row)
            context = _build_context(row)
            source_link = build_source_link(row)
            for topic_key, matched_signals in matched_topics.items():
                topic_entries[topic_key].append(
                    TopicEntry(
                        tweet_id=str(row["tweet_id"]),
                        note_path=note_path,
                        note_link=note_link.as_posix(),
                        source_label=source_link[0] if source_link else None,
                        source_url=source_link[1] if source_link else None,
                        author_handle=author_handle,
                        bookmark_date=note_date.strftime("%Y-%m-%d"),
                        sort_date=note_date,
                        context=context,
                        matched_signals=tuple(matched_signals),
                    )
                )

    topics_root = vault_root / TOPIC_NOTES_DIRNAME
    topics_root.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for topic_key, definition in TOPIC_DEFINITIONS.items():
        entries = sorted(
            topic_entries[topic_key],
            key=lambda entry: (entry.sort_date, entry.tweet_id),
            reverse=True,
        )
        note_path = topics_root / f"{topic_key}.md"
        rendered = _render_topic_note(definition, entries, generated_at)
        _write_atomically(note_path, rendered)
        written_paths.append(note_path)

    return TopicRunResult(
        generated_note_count=len(written_paths),
        written_paths=tuple(written_paths),
    )


def assign_topics(row: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    """Return matched topic keys and visible signal text for one bookmark row."""

    tags = _load_json_list(_row_value(row, "tags"))
    raw_urls = _load_json_list(_row_value(row, "raw_urls"))
    structured_topic = _normalize_text(_row_value(row, "topic"))
    summary_text = _normalize_text(_row_value(row, "summary"))
    bookmark_text = _normalize_text(_row_value(row, "text"))
    joined_tags = " ".join(_normalize_text(tag) for tag in tags)
    url_text = " ".join(_normalize_text(url) for url in raw_urls)
    governance_non_evaluation_hits = _keyword_hits(
        tuple(
            keyword
            for keyword in TOPIC_DEFINITIONS["ai-governance"].summary_keywords
            if keyword != "evaluation"
        ),
        (structured_topic, joined_tags, summary_text, bookmark_text),
    )

    matches: dict[str, tuple[str, ...]] = {}
    structured_hits: dict[str, bool] = {}
    medium_hits: dict[str, bool] = {}
    summary_hit_map: dict[str, tuple[str, ...]] = {}
    text_hit_map: dict[str, tuple[str, ...]] = {}

    for topic_key, definition in TOPIC_DEFINITIONS.items():
        signals: list[str] = []
        strong_matches = _keyword_hits(
            definition.strong_keywords,
            (structured_topic, joined_tags),
        )
        if strong_matches:
            if structured_topic and _contains_any(structured_topic, strong_matches):
                signals.append(f"topic={_row_value(row, 'topic')}")
            tag_hits = [tag for tag in tags if _contains_any(_normalize_text(tag), strong_matches)]
            if tag_hits:
                signals.append(f"tags={', '.join(tag_hits[:3])}")
            structured_hits[topic_key] = True
        else:
            structured_hits[topic_key] = False

        summary_matches = _keyword_hits(definition.summary_keywords, (summary_text,))
        if topic_key == "ai-governance" and summary_matches == ["evaluation"] and not governance_non_evaluation_hits:
            summary_matches = []
        summary_hit_map[topic_key] = tuple(summary_matches)
        if summary_matches:
            signals.append(f"summary keywords={', '.join(summary_matches[:3])}")
            medium_hits[topic_key] = True
        else:
            medium_hits[topic_key] = False

        text_matches = _keyword_hits(definition.text_keywords, (bookmark_text,))
        if topic_key == "ai-governance" and text_matches == ["evaluation"] and not governance_non_evaluation_hits:
            text_matches = []
        text_hit_map[topic_key] = tuple(text_matches)
        allow_text_match = len(text_matches) >= 2 or structured_hits[topic_key] or medium_hits[topic_key]
        if allow_text_match and text_matches:
            signals.append(f"text keywords={', '.join(text_matches[:3])}")

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
            if not (strong_matches or summary_matches or allow_text_match):
                continue
            vendor_url_hits = _keyword_hits(VENDOR_NAMES, (url_text,))
            if vendor_url_hits:
                signals.append(f"url signals={', '.join(vendor_url_hits[:2])}")

        if structured_hits[topic_key] or summary_matches or (allow_text_match and text_matches):
            matches[topic_key] = tuple(dict.fromkeys(signal for signal in signals if signal))

    return _apply_ambiguity_rules(
        matches,
        structured_hits,
        medium_hits,
        summary_hit_map,
        text_hit_map,
    )


def _apply_ambiguity_rules(
    matches: Mapping[str, tuple[str, ...]],
    structured_hits: Mapping[str, bool],
    medium_hits: Mapping[str, bool],
    summary_hit_map: Mapping[str, tuple[str, ...]],
    text_hit_map: Mapping[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    filtered = dict(matches)
    if "ai-governance" not in filtered:
        return filtered

    governance_is_strong = structured_hits.get("ai-governance") or medium_hits.get(
        "ai-governance"
    )
    if not governance_is_strong:
        return filtered

    for weaker_topic in ("enterprise-agents", "vendor-landscape"):
        if weaker_topic not in filtered:
            continue
        if weaker_topic == "enterprise-agents":
            enterprise_hits = set(summary_hit_map.get(weaker_topic, ())) | set(
                text_hit_map.get(weaker_topic, ())
            )
            generic_agent_only = bool(enterprise_hits) and enterprise_hits <= {"agent", "agents"}
            if not structured_hits.get(weaker_topic) and generic_agent_only:
                filtered.pop(weaker_topic, None)
                continue
        if structured_hits.get(weaker_topic) or medium_hits.get(weaker_topic):
            continue
        filtered.pop(weaker_topic, None)
    return filtered


def _vendor_landscape_matches(
    *,
    structured_topic: str,
    joined_tags: str,
    summary_text: str,
    bookmark_text: str,
    url_text: str,
    has_structured_match: bool,
) -> bool:
    strong_zone = " ".join((structured_topic, joined_tags, summary_text, bookmark_text))
    movement_hits = _keyword_hits(VENDOR_MOVEMENT_KEYWORDS, (strong_zone,))
    vendor_hits = _keyword_hits(VENDOR_NAMES, (strong_zone, url_text))
    return bool(movement_hits and (vendor_hits or has_structured_match))


def _keyword_hits(keywords: Iterable[str], texts: Iterable[str]) -> list[str]:
    normalized_texts = [text for text in texts if text]
    hits: list[str] = []
    for keyword in keywords:
        normalized_keyword = _normalize_text(keyword)
        if any(_contains_phrase(text, normalized_keyword) for text in normalized_texts):
            hits.append(keyword)
    return hits


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(_contains_phrase(text, _normalize_text(keyword)) for keyword in keywords)


def _contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
    return re.search(pattern, text) is not None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return re.sub(r"\s+", " ", text)


def _row_value(row: Mapping[str, Any], key: str) -> Any:
    if hasattr(row, "keys") and key in row.keys():
        return row[key]
    return row.get(key) if hasattr(row, "get") else None


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


def _author_handle(row: Mapping[str, Any]) -> str:
    username = _row_value(row, "author_username")
    if isinstance(username, str) and username.strip():
        return f"@{username.lstrip('@')}"
    display_name = _row_value(row, "author_display_name")
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()
    return f"tweet {row['tweet_id']}"


def _build_context(row: Mapping[str, Any]) -> str:
    for value in (
        _row_value(row, "summary"),
        _row_value(row, "topic"),
        _row_value(row, "text"),
    ):
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


def _render_topic_note(
    definition: TopicDefinition,
    entries: list[TopicEntry],
    generated_at: str,
) -> str:
    lines = [
        "---",
        'note_type: "topic_index"',
        f'topic_key: "{definition.key}"',
        f'taxonomy_version: "{TAXONOMY_VERSION}"',
        f'generated_at: "{generated_at}"',
        f"bookmark_count: {len(entries)}",
        "---",
        "",
        f"# {definition.title}",
        "",
        "Generated derived view from local bookmark and enrichment state. Regenerate instead of editing by hand.",
        "",
        "## Scope",
        "",
        f"- Include: {definition.scope}",
        f"- Exclude: {definition.exclusions}",
        "",
        "## Grouping hints",
        "",
    ]
    lines.extend(f"- {hint}" for hint in definition.grouping_hints)
    lines.extend(["", "## Recent bookmarks", ""])

    if not entries:
        lines.append("- None yet.")
    else:
        for entry in entries:
            lines.append(
                f"- {entry.bookmark_date} — {entry.author_handle} — {entry.context}"
            )
            lines.append(f"  - Bookmark note: [Open note]({entry.note_link})")
            if entry.source_url and entry.source_label:
                lines.append(f"  - Source: [{entry.source_label}]({entry.source_url})")
            if entry.matched_signals:
                lines.append(
                    f"  - Matched signals: {'; '.join(entry.matched_signals)}"
                )

    lines.extend(
        [
            "",
            "## Generation notes",
            "",
            "- This note is regenerated from SQLite plus deterministic bookmark-note paths.",
            "- It does not call X, Playwright, or the LLM.",
            "- Source bookmark notes remain the system of record for individual posts.",
        ]
    )
    return "\n".join(lines)


def _validate_topic_database(connection, db_path: Path) -> None:
    try:
        rows = connection.execute(
            "SELECT tweet_id, text, raw_urls, first_seen_at FROM bookmarks LIMIT 1"
        ).fetchall()
        del rows
        rows = connection.execute(
            "SELECT tweet_id, summary, tags, topic FROM enrichments LIMIT 1"
        ).fetchall()
        del rows
    except Exception as exc:  # pragma: no cover - defensive wrapper.
        raise TopicGenerationError(
            f"SQLite database is not ready for topic-note generation: {db_path}"
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
