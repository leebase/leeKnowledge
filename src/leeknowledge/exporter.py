"""
Export stage implementation.
"""

from __future__ import annotations

import json
import base64
import re
import tempfile
import html
import urllib.request
from urllib.parse import urlparse, unquote
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

try:  # pragma: no cover - dependency availability varies in the shell.
    from jinja2 import Environment, FileSystemLoader, StrictUndefined
except ImportError:  # pragma: no cover - exercised when dev deps are absent.
    Environment = None
    FileSystemLoader = None
    StrictUndefined = None

from leeknowledge.db import APP_DB_PATH, get_connection

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
DEFAULT_VAULT_DIR = Path("vault")
DEFAULT_STORY_VAULT_SUBDIR = "stories"
DEFAULT_STORY_FETCH_TIMEOUT_SECONDS = 12.0


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


StoryContentFetcher = Callable[[str], str | None]


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
            ORDER BY b.first_seen_at, b.tweet_id
            """
        ).fetchall()

        for row in rows:
            written_paths.append(_render_note(row, connection, template, vault_root))

    return ExportRunResult(
        exported_note_count=len(written_paths),
        written_paths=tuple(written_paths),
    )


def export_story_markdown(
    db_path: Path | str = APP_DB_PATH,
    vault_dir: Path | str = DEFAULT_VAULT_DIR,
    story_content_fetcher: StoryContentFetcher | None = None,
) -> ExportRunResult:
    """Export one content-first Markdown file per bookmark row in SQLite."""

    resolved_db_path = Path(db_path)
    if not resolved_db_path.exists():
        raise ExportError(f"SQLite database does not exist: {resolved_db_path}")

    vault_root = Path(vault_dir)
    vault_root.mkdir(parents=True, exist_ok=True)

    template = _load_template("story-bookmark.md.j2")
    fetcher = story_content_fetcher or _fetch_story_content
    written_paths: list[Path] = []

    with get_connection(resolved_db_path) as connection:
        _validate_story_export_database(connection, resolved_db_path)
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
                b.first_seen_at
            FROM bookmarks AS b
            ORDER BY b.first_seen_at, b.tweet_id
            """
        ).fetchall()

        for row in rows:
            written_paths.append(
                _render_story_note(
                    row=row,
                    connection=connection,
                    template=template,
                    vault_root=vault_root,
                    story_content_fetcher=fetcher,
                )
            )

    return ExportRunResult(
        exported_note_count=len(written_paths),
        written_paths=tuple(written_paths),
    )


class _FallbackTemplate:
    def render(self, **context: Any) -> str:
        if "story_content" in context:
            return _render_story_note_text(context)
        return _render_note_text(context)


def _load_template(template_name: str = "bookmark.md.j2"):
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
    return environment.get_template(template_name)


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
    note_date = select_bookmark_note_date(row)
    note_path = build_bookmark_note_path(vault_root, row)
    source_link = build_source_link(row)
    rendered = template.render(
        tweet_id=row["tweet_id"],
        source_name=row["source_name"],
        source_type=row["source_type"],
        source_item_id=row["source_item_id"],
        source_ref=row["source_ref"],
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
        source_url=source_link[1] if source_link else None,
        source_label=source_link[0] if source_link else None,
    )
    _write_atomically(note_path, rendered)
    return note_path


def _render_story_note(
    row: Mapping[str, Any],
    connection,
    template,
    vault_root: Path,
    story_content_fetcher: StoryContentFetcher,
) -> Path:
    raw_urls = _load_json_list(row["raw_urls"])
    media_urls = _load_json_list(row["media_urls"])
    resolved_links = _resolve_links(connection, raw_urls)
    note_date = select_bookmark_note_date(row)
    note_path = build_story_note_path(vault_root, row)
    source_link = build_source_link(row)
    story_url, story_content, story_source_label = _resolve_story_content_source(
        row=row,
        resolved_links=resolved_links,
        story_content_fetcher=story_content_fetcher,
        connection=connection,
    )
    rendered = template.render(
        tweet_id=row["tweet_id"],
        source_name=row["source_name"],
        source_type=row["source_type"],
        source_item_id=row["source_item_id"],
        source_ref=row["source_ref"],
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
        note_title=_build_note_title(row),
        note_date=note_date.strftime("%Y-%m-%d"),
        source_url=source_link[1] if source_link else None,
        source_label=source_link[0] if source_link else None,
        story_url=story_url,
        story_source_label=story_source_label,
        story_content=story_content,
        story_fallback=story_source_label,
    )
    _write_atomically(note_path, rendered)
    return note_path


def _resolve_links(connection, raw_urls: Iterable[str]) -> list[ResolvedLink]:
    resolved_links: list[ResolvedLink] = []
    if not _table_exists(connection, "url_cache"):
        for raw_url in raw_urls:
            resolved_links.append(ResolvedLink(original_url=raw_url, resolved_url=raw_url))
        return resolved_links
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


def _resolve_story_content_source(
    row: Mapping[str, Any],
    resolved_links: Iterable[ResolvedLink],
    story_content_fetcher: StoryContentFetcher,
    connection,
    _seen_tweet_ids: set[str] | None = None,
) -> tuple[str | None, str, str | None]:
    source_name = _mapping_value(row, "source_name")
    source_ref = _mapping_value(row, "source_ref")
    tweet_id = _mapping_value(row, "tweet_id")
    if _seen_tweet_ids is None:
        _seen_tweet_ids = set()
    seen_tweet_ids = set(_seen_tweet_ids)
    if tweet_id is not None:
        seen_tweet_ids.add(str(tweet_id))
        normalized_current = _normalize_x_tweet_id(str(tweet_id))
        if normalized_current:
            seen_tweet_ids.add(normalized_current)
    ordered_urls: list[str] = []
    if source_name != "x" and isinstance(source_ref, str) and source_ref.strip():
        ordered_urls.append(source_ref.strip())
    for entry in resolved_links:
        if entry.resolved_url not in ordered_urls:
            ordered_urls.append(entry.resolved_url)
    if source_name == "x":
        for entry in resolved_links:
            if not _is_x_url(entry.resolved_url):
                if entry.resolved_url not in ordered_urls:
                    ordered_urls.append(entry.resolved_url)
        if isinstance(source_ref, str) and source_ref.strip() and source_ref not in ordered_urls:
            ordered_urls.append(source_ref.strip())
    else:
        if tweet_id:
            fallback_x = bookmark_source_url(str(tweet_id))
            if fallback_x not in ordered_urls:
                ordered_urls.append(fallback_x)

    for candidate in ordered_urls:
        if not _is_http_url(candidate):
            continue
        try:
            story_content = story_content_fetcher(candidate)
        except Exception:
            story_content = ""
        if _is_usable_story_content(candidate, story_content):
            return candidate, story_content, "Story content"

    fallback_content = str(row["text"] or "")
    fallback_label = "Tweet text"
    if source_name == "x":
        for linked_tweet_id in _extract_linked_tweet_ids(
            row=row,
            resolved_links=resolved_links,
            source_ref=source_ref,
            seen_tweet_ids=seen_tweet_ids,
        ):
            linked_row = _lookup_bookmark_by_tweet_id(connection, linked_tweet_id)
            if linked_row is None:
                continue
            linked_tweet_id_value = _mapping_value(linked_row, "tweet_id")
            if linked_tweet_id_value is None:
                continue
            linked_tweet_id_value = str(linked_tweet_id_value)
            if linked_tweet_id_value in seen_tweet_ids:
                continue
            linked_seen = set(seen_tweet_ids)
            linked_seen.add(linked_tweet_id_value)
            linked_resolved_urls = _load_json_list(linked_row["raw_urls"])
            linked_resolved_links = _resolve_links(connection, linked_resolved_urls)
            linked_story_url, linked_story_content, linked_label = _resolve_story_content_source(
                row=linked_row,
                resolved_links=linked_resolved_links,
                story_content_fetcher=story_content_fetcher,
                connection=connection,
                _seen_tweet_ids=linked_seen,
            )
            if linked_label != fallback_label:
                return (
                    linked_story_url,
                    linked_story_content,
                    f"Linked tweet story ({linked_tweet_id})",
                )
    return None, fallback_content, fallback_label


def _extract_urls_from_text(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    urls = re.findall(r"https?://[^\s\]}\)>\"']+", text)
    cleaned_urls = []
    for raw_url in urls:
        cleaned_url = raw_url.rstrip(".,!?:;)") 
        if cleaned_url:
            cleaned_urls.append(cleaned_url)
    return cleaned_urls


def _normalize_x_tweet_id(raw_id: str | None) -> str | None:
    if not raw_id:
        return None
    value = raw_id.strip()
    if value.isdigit():
        return value
    try:
        decoded = _decode_base64_note_tweet_id(value)
    except Exception:
        decoded = None
    if decoded:
        return decoded
    return None


def _decode_base64_note_tweet_id(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    padded = normalized + "=" * ((4 - len(normalized) % 4) % 4)
    decoded_candidates: list[bytes] = []
    for decoder in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            decoded_candidates.append(decoder(padded.encode("utf-8"), validate=True))
        except Exception:
            continue
    for decoded in decoded_candidates:
        text = decoded.decode("utf-8", errors="replace")
        match = re.match(r"(?i)^note(?:tweet)?:([0-9]{6,})$", text)
        if match:
            return match.group(1)
        if re.fullmatch(r"[0-9]{6,}", text):
            return text
    return None


def _extract_x_tweet_id_from_url(url: str) -> str | None:
    if not _is_http_url(url):
        return None
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host.endswith("x.com") and not host.endswith("twitter.com"):
        return None
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        return None
    token: str | None = None
    if len(segments) >= 4 and segments[0].lower() == "i" and segments[1].lower() == "web" and segments[2].lower() == "status":
        token = segments[3]
    elif len(segments) >= 2 and segments[-2].lower() == "status":
        token = segments[-1]
    if not token:
        return None
    token = unquote(token)
    return _normalize_x_tweet_id(token)


def _extract_linked_tweet_ids(
    row: Mapping[str, Any],
    resolved_links: Iterable[ResolvedLink],
    source_ref: str | None,
    seen_tweet_ids: set[str],
) -> list[str]:
    extracted_ids: list[str] = []
    candidate_urls: list[str] = []
    candidate_urls.extend(entry.resolved_url for entry in resolved_links)
    candidate_urls.extend(_extract_urls_from_text(_mapping_value(row, "text")))
    if source_ref:
        candidate_urls.append(source_ref)
    for url in candidate_urls:
        linked_id = _extract_x_tweet_id_from_url(url)
        if not linked_id:
            continue
        if linked_id in seen_tweet_ids:
            continue
        if linked_id not in extracted_ids:
            extracted_ids.append(linked_id)
    return extracted_ids


def _lookup_bookmark_by_tweet_id(connection, tweet_id: str):
    return connection.execute(
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
            b.first_seen_at
        FROM bookmarks AS b
        WHERE b.tweet_id = ? OR b.source_item_id = ?
        LIMIT 1
        """,
        (tweet_id, tweet_id),
    ).fetchone()


def _fetch_story_content(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/16.6 Safari/605.1.15"
            )
        },
    )
    with urllib.request.urlopen(
        request, timeout=DEFAULT_STORY_FETCH_TIMEOUT_SECONDS
    ) as response:
        if not _http_success(response):
            return ""
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type and "text/plain" not in content_type:
            return ""
        try:
            raw_html = response.read().decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            return ""
    return _extract_readable_text(raw_html)


def _is_usable_story_content(url: str | None, story_content: str | None) -> bool:
    if not isinstance(story_content, str):
        return False
    content = story_content.strip()
    if not content:
        return False
    if _is_x_url(url) and _looks_like_x_blocked_page(content):
        return False
    return True


def _looks_like_x_blocked_page(content: str) -> bool:
    lowered = content.lower()
    blocked_markers = (
        "something went wrong, but don’t fret",
        "something went wrong, but dont fret",
        "try again",
        "some privacy related extensions may cause issues",
        "privacy related extensions",
        "please enable javascript",
        "log in to x",
        "sign in",
        "javascript is turned off",
        "captcha",
    )
    return any(marker in lowered for marker in blocked_markers)


def _is_http_url(value: str | None) -> bool:
    if value is None:
        return False
    return value.startswith("http://") or value.startswith("https://")


def _http_success(response: object) -> bool:
    status = getattr(response, "status", None)
    if status is None:
        return True
    try:
        status_code = int(status)
    except (TypeError, ValueError):
        return False
    return 200 <= status_code < 400


def _extract_readable_text(raw_html: str) -> str:
    if not raw_html:
        return ""
    body = _extract_body_or_main(raw_html)
    cleaned = re.sub(r"(?is)<script[^>]*>.*?</script>", "", body)
    cleaned = re.sub(r"(?is)<style[^>]*>.*?</style>", "", cleaned)
    cleaned = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", "", cleaned)
    cleaned = re.sub(r"(?is)<svg[^>]*>.*?</svg>", "", cleaned)
    cleaned = re.sub(r"\r\n|\r", "\n", cleaned)
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"</(p|div|section|article|main|li|ul|ol|blockquote|pre)>",
        "\n",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    text = html.unescape(cleaned)
    lines = [line.strip() for line in text.split("\n")]
    text_lines = [line for line in lines if line]
    return "\n\n".join(text_lines).strip()


def _extract_body_or_main(raw_html: str) -> str:
    for tag in ("article", "main", "body"):
        match = re.search(
            rf"<{tag}[^>]*>(.*?)</{tag}>",
            raw_html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1)
    return raw_html


def _is_x_url(value: str | None) -> bool:
    if value is None:
        return False
    return "x.com/" in value or "twitter.com/" in value


def _build_note_title(row: Mapping[str, Any]) -> str:
    label: str
    if isinstance(row["author_username"], str) and row["author_username"].strip():
        label = f"@{row['author_username'].lstrip('@')}"
    elif isinstance(row["author_display_name"], str) and row["author_display_name"].strip():
        label = row["author_display_name"].strip()
    else:
        label = f"tweet {row['tweet_id']}"
    note_date = select_bookmark_note_date(row).strftime("%Y-%m-%d")
    return f"{label} — {note_date}"


def build_bookmark_note_path(vault_root: Path, row: Mapping[str, Any]) -> Path:
    note_date = select_bookmark_note_date(row)
    item_id = bookmark_identity(row)
    text = str(row["text"] or "")
    year_dir = vault_root / note_date.strftime("%Y") / note_date.strftime("%m")
    slug = _slugify(text) or f"bookmark-{_slugify(item_id) or 'item'}"
    return year_dir / f"{slug}-{_slugify(item_id) or item_id}.md"


def build_story_note_path(vault_root: Path, row: Mapping[str, Any]) -> Path:
    note_date = select_bookmark_note_date(row)
    item_id = bookmark_identity(row)
    text = str(row["text"] or "")
    year_dir = (
        vault_root / DEFAULT_STORY_VAULT_SUBDIR / note_date.strftime("%Y") / note_date.strftime("%m")
    )
    slug = _slugify(text) or f"story-{_slugify(item_id) or 'item'}"
    return year_dir / f"{slug}-{_slugify(item_id) or item_id}.md"


def bookmark_source_url(tweet_id: str) -> str:
    return f"https://x.com/i/web/status/{tweet_id}"


def bookmark_identity(row: Mapping[str, Any]) -> str:
    source_name = _mapping_value(row, "source_name")
    source_type = _mapping_value(row, "source_type")
    source_item_id = _mapping_value(row, "source_item_id")
    if source_name and source_type and source_item_id and source_name != "x":
        return f"{source_name}:{source_type}:{source_item_id}"
    return str(row["tweet_id"])


def build_source_link(row: Mapping[str, Any]) -> tuple[str, str] | None:
    source_name = _mapping_value(row, "source_name")
    tweet_id = _mapping_value(row, "tweet_id")
    if source_name == "x" and tweet_id:
        resolved_tweet_id = _normalize_x_tweet_id(str(tweet_id)) or str(tweet_id)
        return ("View on X", bookmark_source_url(str(resolved_tweet_id)))
    source_ref = _mapping_value(row, "source_ref")
    if isinstance(source_ref, str) and source_ref.strip():
        return ("View source", source_ref.strip())
    return None


def select_bookmark_note_date(row: Mapping[str, Any]) -> datetime:
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
        "source_name",
        "source_type",
        "source_item_id",
        "source_ref",
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


def _validate_story_export_database(connection, db_path: Path) -> None:
    if not _table_exists(connection, "bookmarks"):
        raise ExportError(
            f"SQLite database is missing required table 'bookmarks': {db_path}"
        )

    required_bookmark_columns = {
        "tweet_id",
        "source_name",
        "source_type",
        "source_item_id",
        "source_ref",
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

    _validate_columns(
        connection,
        "bookmarks",
        required_bookmark_columns,
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


def _mapping_value(row: Mapping[str, Any], key: str) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


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
            f"source_name: {_yaml_scalar(context['source_name'])}",
            f"source_type: {_yaml_scalar(context['source_type'])}",
            f"source_item_id: {_yaml_scalar(context['source_item_id'])}",
            f"source_ref: {_yaml_scalar(context['source_ref'])}",
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
    lines.extend(["", "## Source"])
    if context["source_url"] and context["source_label"]:
        lines.append(f"- [{context['source_label']}]({context['source_url']})")
    else:
        lines.append("- None")
    return "\n".join(lines)


def _render_story_note_text(context: Mapping[str, Any]) -> str:
    lines: list[str] = ["---"]
    lines.extend(
        [
            f"tweet_id: {_yaml_scalar(context['tweet_id'])}",
            f"source_name: {_yaml_scalar(context['source_name'])}",
            f"source_type: {_yaml_scalar(context['source_type'])}",
            f"source_item_id: {_yaml_scalar(context['source_item_id'])}",
            f"source_ref: {_yaml_scalar(context['source_ref'])}",
            f"author_username: {_yaml_scalar(context['author_username'])}",
            f"author_display_name: {_yaml_scalar(context['author_display_name'])}",
            f"created_at: {_yaml_scalar(context['created_at'])}",
            f"conversation_id: {_yaml_scalar(context['conversation_id'])}",
            f"in_reply_to_id: {_yaml_scalar(context['in_reply_to_id'])}",
            f"story_source_label: {_yaml_scalar(context['story_source_label'])}",
            f"story_url: {_yaml_scalar(context['story_url'])}",
            f"story_content_type: {_yaml_scalar(context['story_fallback'])}",
            f"note_date: {_yaml_scalar(context['note_date'])}",
        ]
    )
    lines.extend(_render_list_block("raw_urls", context["raw_urls"]))
    lines.extend(_render_list_block("resolved_urls", context["resolved_urls"]))
    lines.extend(
        [
            "---",
            "",
            f"# {context['note_title']}",
            "",
            "## Tweet text",
            "",
        ]
    )
    lines.extend(_text_fence(context["text"]))
    lines.extend(
        [
            "",
            "## Story content",
            "",
        ]
    )
    if context["story_source_label"] == "Tweet text":
        lines.append("No usable article content was extracted from the source URL for this bookmark.")
    else:
        lines.extend(_text_fence(context["story_content"]))
    lines.extend(["", "## Links"])
    if context["story_url"]:
        label = context["story_source_label"] or "Story source"
        lines.append(f"- [{label}]({context['story_url']})")
    resolved_links = context["resolved_links"]
    if resolved_links:
        for entry in resolved_links:
            if entry.resolved_url == context["story_url"]:
                continue
            line = f"- URL: [{entry.resolved_url}]({entry.resolved_url})"
            if entry.page_title:
                line += f" | Title: {_markdown_escape(entry.page_title)}"
            if entry.page_description:
                line += f" | Description: {_markdown_escape(entry.page_description)}"
            lines.append(line)
    else:
        lines.append("- None")
    lines.extend(["", "## Source"])
    if context["source_url"] and context["source_label"]:
        lines.append(f"- [{context['source_label']}]({context['source_url']})")
    else:
        lines.append("- None")
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
