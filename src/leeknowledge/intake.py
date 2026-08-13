"""Universal source-intake adapters for Sprint 10."""

from __future__ import annotations

import csv
import hashlib
import json
import plistlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import parse_qsl, urlparse, urlunparse, urlencode

from leeknowledge.db import APP_DB_PATH, get_connection, initialize_database, insert_bookmark

URL_PATTERN = re.compile(r"https?://[^\s)>\]}]+", re.IGNORECASE)


class IntakeError(RuntimeError):
    """Raised when a source-intake command cannot complete safely."""


@dataclass(frozen=True)
class IntakeIssue:
    reason: str
    payload_index: int | None = None
    source_ref: str | None = None
    payload_preview: str | None = None


@dataclass(frozen=True)
class IntakeRunResult:
    archive_path: Path
    imported_record_count: int
    inserted_record_count: int
    quarantined_record_count: int
    quarantine_path: Path | None = None
    issues: tuple[IntakeIssue, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RawImportArchive:
    imported_at: str
    adapter: str
    source: Mapping[str, Any]
    items: tuple[Any, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "imported_at": self.imported_at,
            "adapter": self.adapter,
            "source": dict(self.source),
            "items": list(self.items),
        }


@dataclass(frozen=True)
class SourceRecord:
    tweet_id: str
    source_name: str
    source_type: str
    source_item_id: str
    source_ref: str | None
    text: str
    author_username: str | None = None
    author_display_name: str | None = None
    created_at: str | None = None
    conversation_id: str | None = None
    in_reply_to_id: str | None = None
    media_urls: tuple[str, ...] = ()
    raw_urls: tuple[str, ...] = ()
    first_seen_at: str = ""

    def to_bookmark(self) -> dict[str, Any]:
        return {
            "tweet_id": self.tweet_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "source_item_id": self.source_item_id,
            "source_ref": self.source_ref,
            "text": self.text,
            "author_username": self.author_username,
            "author_display_name": self.author_display_name,
            "created_at": self.created_at,
            "conversation_id": self.conversation_id,
            "in_reply_to_id": self.in_reply_to_id,
            "media_urls": list(self.media_urls),
            "raw_urls": list(self.raw_urls),
            "first_seen_at": self.first_seen_at,
        }


def import_urls(
    *,
    urls: Iterable[str],
    raw_output_dir: Path,
    db_path: Path | str = APP_DB_PATH,
) -> IntakeRunResult:
    imported_at = _utc_now()
    items = [{"url": str(url)} for url in urls]
    archive = RawImportArchive(
        imported_at=imported_at,
        adapter="import-url",
        source={"url_count": len(items)},
        items=tuple(items),
    )
    archive_path = persist_import_archive(archive, raw_output_dir)

    records: list[SourceRecord] = []
    issues: list[IntakeIssue] = []
    for index, item in enumerate(items):
        canonical_url = canonicalize_url(item["url"])
        if canonical_url is None:
            issues.append(
                IntakeIssue(
                    reason="Missing or invalid absolute URL.",
                    payload_index=index,
                    source_ref=item["url"],
                    payload_preview=repr(item),
                )
            )
            continue
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

    return _persist_records(
        archive_path=archive_path,
        raw_output_dir=raw_output_dir,
        adapter="import-url",
        source={"command": "import-url"},
        records=records,
        issues=issues,
        db_path=db_path,
    )


def import_safari_bookmarks(
    *,
    input_path: Path | str,
    raw_output_dir: Path,
    db_path: Path | str = APP_DB_PATH,
) -> IntakeRunResult:
    path = Path(input_path)
    if not path.exists():
        raise IntakeError(f"Safari bookmark input does not exist: {path}")

    imported_at = _utc_now()
    try:
        with path.open("rb") as handle:
            parsed = plistlib.load(handle)
    except Exception as exc:
        raise IntakeError(f"Safari bookmark input is not a readable plist: {path}") from exc

    archive = RawImportArchive(
        imported_at=imported_at,
        adapter="import-safari-folder",
        source={"input_path": str(path)},
        items=(parsed,),
    )
    archive_path = persist_import_archive(archive, raw_output_dir)

    records: list[SourceRecord] = []
    issues: list[IntakeIssue] = []
    for index, item in enumerate(_iter_safari_entries(parsed)):
        lineage = item["folder_lineage"]
        raw_url = item.get("url")
        canonical_url = canonicalize_url(raw_url)
        if canonical_url is None:
            issues.append(
                IntakeIssue(
                    reason="Missing canonical URL in Safari bookmark entry.",
                    payload_index=index,
                    source_ref=str(raw_url) if raw_url else None,
                    payload_preview=repr(item),
                )
            )
            continue
        if not lineage:
            issues.append(
                IntakeIssue(
                    reason="Missing folder lineage in Safari bookmark entry.",
                    payload_index=index,
                    source_ref=canonical_url,
                    payload_preview=repr(item),
                )
            )
            continue
        title = item.get("title") or canonical_url
        records.append(
            _build_source_record(
                source_name="safari",
                source_type="bookmark_export",
                source_item_key="/".join(lineage) + "|" + canonical_url,
                source_ref=canonical_url,
                text=str(title),
                raw_urls=[canonical_url],
                first_seen_at=imported_at,
            )
        )

    return _persist_records(
        archive_path=archive_path,
        raw_output_dir=raw_output_dir,
        adapter="import-safari-folder",
        source={"input_path": str(path)},
        records=records,
        issues=issues,
        db_path=db_path,
    )


def import_research_artifact(
    *,
    input_path: Path | str,
    raw_output_dir: Path,
    db_path: Path | str = APP_DB_PATH,
) -> IntakeRunResult:
    path = Path(input_path)
    if not path.exists():
        raise IntakeError(f"Research artifact input does not exist: {path}")

    imported_at = _utc_now()
    items = tuple(_load_research_items(path))
    archive = RawImportArchive(
        imported_at=imported_at,
        adapter="import-research",
        source={"input_path": str(path), "suffix": path.suffix.lower()},
        items=items,
    )
    archive_path = persist_import_archive(archive, raw_output_dir)

    records: list[SourceRecord] = []
    issues: list[IntakeIssue] = []
    artifact_identity = str(path.resolve())
    for index, item in enumerate(items):
        if isinstance(item, str):
            text = item.strip()
            raw_urls = list(dict.fromkeys(URL_PATTERN.findall(item)))
            if not text:
                issues.append(
                    IntakeIssue(
                        reason="Unreadable research item.",
                        payload_index=index,
                        payload_preview=repr(item),
                    )
                )
                continue
            source_ref = raw_urls[0] if raw_urls else str(path)
            records.append(
                _build_source_record(
                    source_name="research",
                    source_type="artifact_item",
                    source_item_key=f"{artifact_identity}|line:{index}",
                    source_ref=source_ref,
                    text=text,
                    raw_urls=raw_urls,
                    first_seen_at=imported_at,
                )
            )
            continue

        if not isinstance(item, Mapping):
            issues.append(
                IntakeIssue(
                    reason="Unreadable research row.",
                    payload_index=index,
                    payload_preview=repr(item),
                )
            )
            continue

        text = _research_text(item)
        source_ref = _research_source_ref(item) or str(path)
        raw_urls = _research_raw_urls(item)
        created_at = _first_string(item, ("created_at", "published_at", "date", "timestamp"))
        if not text:
            issues.append(
                IntakeIssue(
                    reason="Unreadable research row.",
                    payload_index=index,
                    source_ref=source_ref,
                    payload_preview=repr(item),
                )
            )
            continue
        locator = _first_string(item, ("id", "slug", "title", "url", "source_url")) or str(index)
        records.append(
            _build_source_record(
                source_name="research",
                source_type="artifact_item",
                source_item_key=f"{artifact_identity}|{locator}",
                source_ref=source_ref,
                text=text,
                raw_urls=raw_urls,
                created_at=created_at,
                first_seen_at=imported_at,
            )
        )

    return _persist_records(
        archive_path=archive_path,
        raw_output_dir=raw_output_dir,
        adapter="import-research",
        source={"input_path": str(path)},
        records=records,
        issues=issues,
        db_path=db_path,
    )


def persist_import_archive(archive: RawImportArchive, raw_output_dir: Path) -> Path:
    raw_output_dir.mkdir(parents=True, exist_ok=True)
    stem = archive.adapter.replace("-", "_")
    base_path = raw_output_dir / f"{stem}_{archive.imported_at[:10]}.json"
    archive_path = base_path if not base_path.exists() else _unique_path(base_path)
    archive_path.write_text(json.dumps(archive.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return archive_path


def canonicalize_url(url: Any) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return None
    normalized_query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
        query=normalized_query,
        path=parsed.path or "/",
    )
    return urlunparse(normalized)


def _persist_records(
    *,
    archive_path: Path,
    raw_output_dir: Path,
    adapter: str,
    source: Mapping[str, Any],
    records: list[SourceRecord],
    issues: list[IntakeIssue],
    db_path: Path | str,
) -> IntakeRunResult:
    if not records and issues:
        quarantine_path = _write_quarantine(adapter=adapter, raw_output_dir=raw_output_dir, archive_path=archive_path, source=source, issues=issues)
        return IntakeRunResult(
            archive_path=archive_path,
            imported_record_count=0,
            inserted_record_count=0,
            quarantined_record_count=len(issues),
            quarantine_path=quarantine_path,
            issues=tuple(issues),
        )

    initialize_database(db_path)
    inserted_count = 0
    with get_connection(db_path) as connection:
        for record in records:
            if insert_bookmark(connection, record.to_bookmark()):
                inserted_count += 1

    quarantine_path = None
    if issues:
        quarantine_path = _write_quarantine(
            adapter=adapter,
            raw_output_dir=raw_output_dir,
            archive_path=archive_path,
            source=source,
            issues=issues,
        )

    return IntakeRunResult(
        archive_path=archive_path,
        imported_record_count=len(records),
        inserted_record_count=inserted_count,
        quarantined_record_count=len(issues),
        quarantine_path=quarantine_path,
        issues=tuple(issues),
    )


def _write_quarantine(
    *,
    adapter: str,
    raw_output_dir: Path,
    archive_path: Path,
    source: Mapping[str, Any],
    issues: Iterable[IntakeIssue],
) -> Path:
    payload = {
        "adapter": adapter,
        "raw_archive_path": str(archive_path),
        "source": dict(source),
        "issues": [issue.__dict__ for issue in issues],
    }
    base_path = raw_output_dir / f"quarantine_{adapter.replace('-', '_')}_{_utc_now()[:10]}.json"
    quarantine_path = base_path if not base_path.exists() else _unique_path(base_path)
    quarantine_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return quarantine_path


def _build_source_record(
    *,
    source_name: str,
    source_type: str,
    source_item_key: str,
    source_ref: str | None,
    text: str,
    raw_urls: Iterable[str],
    first_seen_at: str,
    created_at: str | None = None,
) -> SourceRecord:
    source_item_id = hashlib.sha256(source_item_key.encode("utf-8")).hexdigest()[:24]
    tweet_id = f"{source_name}:{source_type}:{source_item_id}"
    deduped_urls = tuple(dict.fromkeys(url for url in raw_urls if isinstance(url, str) and url.strip()))
    return SourceRecord(
        tweet_id=tweet_id,
        source_name=source_name,
        source_type=source_type,
        source_item_id=source_item_id,
        source_ref=source_ref,
        text=text.strip(),
        created_at=created_at,
        raw_urls=deduped_urls,
        first_seen_at=first_seen_at,
    )


def _iter_safari_entries(node: Any, lineage: tuple[str, ...] = ()) -> Iterable[dict[str, Any]]:
    if isinstance(node, Mapping):
        title = _safari_title(node)
        node_type = str(node.get("WebBookmarkType") or "")
        children = node.get("Children")
        next_lineage = lineage
        if title and node_type != "WebBookmarkTypeLeaf":
            next_lineage = lineage + (title,)
        if isinstance(children, list):
            for child in children:
                yield from _iter_safari_entries(child, next_lineage)
        elif node_type == "WebBookmarkTypeLeaf" or node.get("URLString"):
            yield {
                "title": title,
                "url": node.get("URLString"),
                "folder_lineage": lineage,
            }
    elif isinstance(node, list):
        for item in node:
            yield from _iter_safari_entries(item, lineage)


def _safari_title(node: Mapping[str, Any]) -> str | None:
    title = node.get("Title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    uri = node.get("URIDictionary")
    if isinstance(uri, Mapping):
        value = uri.get("title")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _load_research_items(path: Path) -> list[Any]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        parsed = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, Mapping):
            if isinstance(parsed.get("items"), list):
                return list(parsed["items"])
            return [parsed]
        return [parsed]
    if suffix == ".jsonl":
        items: list[Any] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                items.append(json.loads(line))
        return items
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    if suffix in {".md", ".markdown", ".txt"}:
        return [path.read_text(encoding="utf-8")]
    raise IntakeError(f"Unsupported research artifact format: {path}")


def _research_text(item: Mapping[str, Any]) -> str | None:
    title = _first_string(item, ("title",))
    body = _first_string(item, ("text", "content", "summary", "body", "markdown", "note", "description"))
    if title and body:
        return f"{title}\n\n{body}".strip()
    if body:
        return body.strip()
    if title:
        return title.strip()
    source_ref = _research_source_ref(item)
    if source_ref:
        return source_ref
    return None


def _research_source_ref(item: Mapping[str, Any]) -> str | None:
    source_ref = _first_string(item, ("source_url", "url", "link", "href", "source_ref", "path"))
    if source_ref:
        canonical = canonicalize_url(source_ref)
        return canonical or source_ref
    return None


def _research_raw_urls(item: Mapping[str, Any]) -> list[str]:
    urls: list[str] = []
    for key in ("source_url", "url", "link", "href"):
        value = item.get(key)
        canonical = canonicalize_url(value)
        if canonical and canonical not in urls:
            urls.append(canonical)
    for text_field in ("text", "content", "summary", "body", "markdown", "note", "description"):
        value = item.get(text_field)
        if isinstance(value, str):
            for match in URL_PATTERN.findall(value):
                canonical = canonicalize_url(match)
                if canonical and canonical not in urls:
                    urls.append(canonical)
    return urls


def _first_string(item: Mapping[str, Any], keys: Iterable[str]) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _unique_path(base_path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
    candidate = base_path.with_name(f"{base_path.stem}_{timestamp}{base_path.suffix}")
    suffix = 1
    while candidate.exists():
        candidate = base_path.with_name(f"{base_path.stem}_{timestamp}_{suffix}{base_path.suffix}")
        suffix += 1
    return candidate


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
