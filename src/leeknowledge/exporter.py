"""
Export stage implementation.
"""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

try:  # pragma: no cover - dependency availability varies in the shell.
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:  # pragma: no cover - exercised when dev deps are absent.
    Environment = None
    FileSystemLoader = None
    StrictUndefined = None

from leeknowledge.db import APP_DB_PATH, get_connection

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_VAULT_DIR = Path("vault")


class ExportError(RuntimeError):
    """Raised when Markdown export cannot complete safely."""


@dataclass(frozen=True)
class ResolvedLink:
    """Resolved URL metadata used by the export template."""

    original_url: str
    resolved_url: str
    page_title: str | None = None
    page_description: str | None = None
    cached_at: str | None = None


@dataclass(frozen=True)
class ExportRunResult:
    """Summary of a completed export run."""

    exported_note_count: int
    written_paths: tuple[Path, ...] = field(default_factory=tuple)


def export_markdown(
    db_path: Path | str = APP_DB_PATH,
    vault_dir: Path | str = DEFAULT_VAULT_DIR,
) -> ExportRunResult:
    """Render one Markdown note per bookmark row in SQLite."""

    resolved_db_path = Path(db_path)
    if not resolved_db_path.exists():
        raise ExportError(f"SQLite database does not exist: {resolved_db_path}")

    vault_root = Path(vault_dir)
    vault_root.mkdir(parents=True, exist_ok=True)

    template = _load_template()
    written_paths: list[Path] = []

    with get_connection(resolved_db_path) as connection:
        _validate_export_database(connection, resolved_db_path)
        rows = connection.execute(
            """
            SELECT
                b.tweet_id,
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
            ORDER BY b.first_seen_at, b.tweet_id
            """
        ).fetchall()

        for row in rows:
            written_paths.append(_render_note(row, connection, template, vault_root))

    return ExportRunResult(
        exported_note_count=len(written_paths),
        written_paths=tuple(written_paths),
    )


class _FallbackTemplate:
    def render(self, **context: Any) -> str:
        return _render_note_text(context)


def _load_template():
    if Environment is None:
        return _FallbackTemplate()

    if not TEMPLATE_DIR.exists():
        raise ExportError(f"Missing export template directory: {TEMPLATE_DIR}")

    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined,
    )
    environment.filters["yaml_scalar"] = _yaml_scalar
    environment.filters["markdown_escape"] = _markdown_escape
    return environment.get_template("bookmark.md.j2")


def _render_note(
    row: Mapping[str, Any],
    connection,
    template,
    vault_root: Path,
) -> Path:
    raw_urls = _load_json_list(row["raw_urls"])
    media_urls = _load_json_list(row["media_urls"])
    tags = _load_json_list(row["tags"])
    entities = _load_json_list(row["entities"])
    resolved_links = _resolve_links(connection, raw_urls)
    note_date = _select_note_date(row)
    note_path = _build_note_path(vault_root, note_date, row["text"], row["tweet_id"])
    rendered = template.render(
        tweet_id=row["tweet_id"],
        text=row["text"],
        author_username=row["author_username"],
        author_display_name=row["author_display_name"],
        created_at=row["created_at"],
        conversation_id=row["conversation_id"],
        in_reply_to_id=row["in_reply_to_id"],
        media_urls=media_urls,
        raw_urls=raw_urls,
        resolved_urls=[entry.resolved_url for entry in resolved_links],
        resolved_links=resolved_links,
        summary=row["summary"],
        tags=tags,
        entities=entities,
        topic=row["topic"],
        model=row["model"],
        prompt_version=row["prompt_version"],
        schema_version=row["schema_version"],
        validation_status=row["validation_status"],
        enriched_at=row["enriched_at"],
        note_title=_build_note_title(row),
        note_date=note_date.strftime("%Y-%m-%d"),
        source_url=f"https://x.com/i/web/status/{row['tweet_id']}",
    )
    _write_atomically(note_path, rendered)
    return note_path


def _resolve_links(connection, raw_urls: Iterable[str]) -> list[ResolvedLink]:
    resolved_links: list[ResolvedLink] = []
    for raw_url in raw_urls:
        row = connection.execute(
            """
            SELECT original_url, resolved_url, page_title, page_description, cached_at
            FROM url_cache
            WHERE original_url = ?
            """,
            (raw_url,),
        ).fetchone()
        if row is None:
            resolved_links.append(
                ResolvedLink(original_url=raw_url, resolved_url=raw_url)
            )
            continue
        resolved_links.append(
            ResolvedLink(
                original_url=str(row["original_url"]),
                resolved_url=str(row["resolved_url"] or row["original_url"]),
                page_title=row["page_title"],
                page_description=row["page_description"],
                cached_at=row["cached_at"],
            )
        )
    return resolved_links


def _build_note_title(row: Mapping[str, Any]) -> str:
    label: str
    if isinstance(row["author_username"], str) and row["author_username"].strip():
        label = f"@{row['author_username'].lstrip('@')}"
    elif isinstance(row["author_display_name"], str) and row["author_display_name"].strip():
        label = row["author_display_name"].strip()
    else:
        label = f"tweet {row['tweet_id']}"
    note_date = _select_note_date(row).strftime("%Y-%m-%d")
    return f"{label} — {note_date}"


def _build_note_path(vault_root: Path, note_date: datetime, text: str, tweet_id: str) -> Path:
    year_dir = vault_root / note_date.strftime("%Y") / note_date.strftime("%m")
    year_dir.mkdir(parents=True, exist_ok=True)
    slug = _slugify(text) or f"tweet-{tweet_id}"
    return year_dir / f"{slug}-{tweet_id}.md"


def _select_note_date(row: Mapping[str, Any]) -> datetime:
    for candidate in (row["created_at"], row["first_seen_at"]):
        parsed = _parse_date(candidate)
        if parsed is not None:
            return parsed
    raise ExportError(f"Could not determine note date for tweet {row['tweet_id']}")


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    parsers = (
        lambda text: datetime.fromisoformat(text.replace("Z", "+00:00")),
        lambda text: datetime.strptime(text, "%a %b %d %H:%M:%S %z %Y"),
        lambda text: datetime.strptime(text, "%Y-%m-%d"),
    )
    for parser in parsers:
        try:
            parsed = parser(value)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:80]


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


def _validate_export_database(connection, db_path: Path) -> None:
    if not _table_exists(connection, "bookmarks"):
        raise ExportError(
            f"SQLite database is missing required table 'bookmarks': {db_path}"
        )
    if not _table_exists(connection, "enrichments"):
        raise ExportError(
            f"SQLite database is missing required table 'enrichments': {db_path}"
        )
    if not _table_exists(connection, "url_cache"):
        raise ExportError(
            f"SQLite database is missing required table 'url_cache': {db_path}"
        )

    required_bookmark_columns = {
        "tweet_id",
        "text",
        "author_username",
        "author_display_name",
        "created_at",
        "conversation_id",
        "in_reply_to_id",
        "media_urls",
        "raw_urls",
        "first_seen_at",
    }
    required_enrichment_columns = {
        "tweet_id",
        "summary",
        "tags",
        "entities",
        "topic",
        "model",
        "prompt_version",
        "schema_version",
        "validation_status",
        "enriched_at",
    }
    required_url_cache_columns = {
        "original_url",
        "resolved_url",
        "page_title",
        "page_description",
        "cached_at",
    }

    _validate_columns(
        connection,
        "bookmarks",
        required_bookmark_columns,
        db_path,
    )
    _validate_columns(
        connection,
        "enrichments",
        required_enrichment_columns,
        db_path,
    )
    _validate_columns(
        connection,
        "url_cache",
        required_url_cache_columns,
        db_path,
    )


def _table_exists(connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _validate_columns(
    connection,
    table_name: str,
    required_columns: set[str],
    db_path: Path,
) -> None:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    available_columns = {str(row["name"]) for row in rows}
    missing_columns = sorted(required_columns - available_columns)
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise ExportError(
            f"SQLite database table '{table_name}' is missing required columns "
            f"({missing_text}): {db_path}"
        )


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value)
    return json.dumps(value)


def _markdown_escape(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = re.sub(r"([`*_{}\[\]()#+.!|>~-])", r"\\\1", text)
    return text.replace("\n", "  \n")


def _text_fence(value: Any) -> list[str]:
    text = "" if value is None else str(value)
    fence = "```"
    while fence in text:
        fence += "`"
    return [fence + "text", text, fence]


def _render_note_text(context: Mapping[str, Any]) -> str:
    lines: list[str] = ["---"]
    lines.extend(
        [
            f"tweet_id: {_yaml_scalar(context['tweet_id'])}",
            f"author_username: {_yaml_scalar(context['author_username'])}",
            f"author_display_name: {_yaml_scalar(context['author_display_name'])}",
            f"created_at: {_yaml_scalar(context['created_at'])}",
            f"conversation_id: {_yaml_scalar(context['conversation_id'])}",
            f"in_reply_to_id: {_yaml_scalar(context['in_reply_to_id'])}",
            f"topic: {_yaml_scalar(context['topic'])}",
        ]
    )
    lines.extend(_render_list_block("tags", context["tags"]))
    lines.append(f"summary: {_yaml_scalar(context['summary'])}")
    lines.extend(_render_list_block("entities", context["entities"]))
    lines.extend(_render_list_block("raw_urls", context["raw_urls"]))
    lines.extend(_render_list_block("resolved_urls", context["resolved_urls"]))
    lines.extend(_render_list_block("media_urls", context["media_urls"]))
    lines.extend(
        [
            f"model: {_yaml_scalar(context['model'])}",
            f"prompt_version: {_yaml_scalar(context['prompt_version'])}",
            f"schema_version: {_yaml_scalar(context['schema_version'])}",
            f"validation_status: {_yaml_scalar(context['validation_status'])}",
            f"enriched_at: {_yaml_scalar(context['enriched_at'])}",
            "---",
            "",
            f"# {context['note_title']}",
            "",
        ]
    )
    if context["summary"]:
        lines.extend(["## Summary", ""])
        lines.extend(_text_fence(context["summary"]))
        lines.append("")
    lines.extend(
        [
            "## Tweet",
            "",
        ]
    )
    lines.extend(_text_fence(context["text"]))
    lines.extend(
        [
            "",
            "## Resolved Links",
        ]
    )
    resolved_links = context["resolved_links"]
    if resolved_links:
        for entry in resolved_links:
            line = f"- URL: [{entry.resolved_url}]({entry.resolved_url})"
            if entry.page_title:
                line += f" | Title: {_markdown_escape(entry.page_title)}"
            if entry.page_description:
                line += f" | Description: {_markdown_escape(entry.page_description)}"
            lines.append(line)
    else:
        lines.append("- None")
    lines.extend(["", "## Source", f"- [View on X]({context['source_url']})"])
    return "\n".join(lines)


def _render_list_block(key: str, values: Iterable[Any]) -> list[str]:
    items = list(values)
    if not items:
        return [f"{key}: []"]
    lines = [f"{key}:"]
    lines.extend(f"  - {_yaml_scalar(value)}" for value in items)
    return lines


def _write_atomically(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", delete=False, dir=path.parent, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
