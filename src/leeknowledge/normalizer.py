"""
Normalization stage implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class NormalizationIssue:
    """A record that could not be converted into the canonical schema."""

    reason: str
    payload_index: int | None = None
    tweet_id: str | None = None
    payload_preview: str | None = None


@dataclass(frozen=True)
class NormalizationResult:
    """Deterministic output of raw-to-canonical normalization."""

    records: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[NormalizationIssue] = field(default_factory=list)


def normalize_payloads(
    payloads: Iterable[dict[str, Any]] | Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Normalize raw payloads into canonical bookmark records.

    Backwards-compatible wrapper that returns only the records list.
    """

    return normalize_raw_archive(payloads).records


def normalize_raw_archive(
    archive: Iterable[dict[str, Any]] | Mapping[str, Any],
) -> NormalizationResult:
    """Normalize a raw archive or raw payload iterable into canonical rows."""

    first_seen_at, payload_items = _extract_archive_items(archive)
    records: list[dict[str, Any]] = []
    skipped: list[NormalizationIssue] = []
    seen_tweet_ids: set[str] = set()

    for index, item in enumerate(payload_items):
        record_first_seen_at = _coalesce(
            _mapping_get(item, "captured_at"),
            _mapping_get(item, "first_seen_at"),
            first_seen_at,
        )
        candidate = _mapping_get(item, "payload", item)
        normalized_any = False
        for raw_candidate in _iter_candidate_mappings(candidate):
            normalized = _normalize_candidate(raw_candidate, record_first_seen_at)
            if normalized is None:
                continue
            normalized_any = True
            tweet_id = normalized["tweet_id"]
            if tweet_id in seen_tweet_ids:
                continue
            seen_tweet_ids.add(tweet_id)
            records.append(normalized)

        if not normalized_any:
            preview = _preview(item)
            skipped.append(
                NormalizationIssue(
                    reason="No bookmark-shaped tweet record found in raw payload.",
                    payload_index=index,
                    payload_preview=preview,
                )
            )

    return NormalizationResult(records=records, skipped=skipped)


def _extract_archive_items(
    archive: Iterable[dict[str, Any]] | Mapping[str, Any],
) -> tuple[str | None, list[dict[str, Any]]]:
    if isinstance(archive, Mapping):
        captured_at = _coalesce(
            archive.get("captured_at"),
            archive.get("first_seen_at"),
        )
        items = archive.get("bookmark_payloads") or archive.get("payloads") or []
        if isinstance(items, list):
            return captured_at, [item for item in items if isinstance(item, dict)]
        return captured_at, []

    return None, [item for item in archive if isinstance(item, dict)]


def _iter_candidate_mappings(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _iter_candidate_mappings(nested)
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _iter_candidate_mappings(item)


def _normalize_candidate(
    candidate: Mapping[str, Any],
    first_seen_at: str | None,
) -> dict[str, Any] | None:
    tweet_id = _extract_tweet_id(candidate)
    if not tweet_id:
        return None

    text = _extract_text(candidate)
    if not text:
        return None

    normalized = {
        "tweet_id": tweet_id,
        "text": text,
        "author_username": _extract_author_username(candidate),
        "author_display_name": _extract_author_display_name(candidate),
        "created_at": _coalesce(
            _mapping_get(candidate, "created_at"),
            _mapping_get(candidate, "createdAt"),
            _nested_get(candidate, ("legacy", "created_at")),
            _nested_get(candidate, ("legacy", "createdAt")),
        ),
        "conversation_id": _coalesce(
            _mapping_get(candidate, "conversation_id"),
            _mapping_get(candidate, "conversationId"),
            _nested_get(candidate, ("legacy", "conversation_id")),
            _nested_get(candidate, ("legacy", "conversation_id_str")),
        ),
        "in_reply_to_id": _coalesce(
            _mapping_get(candidate, "in_reply_to_id"),
            _mapping_get(candidate, "inReplyToTweetId"),
            _nested_get(candidate, ("legacy", "in_reply_to_status_id_str")),
            _nested_get(candidate, ("legacy", "in_reply_to_status_id")),
        ),
        "media_urls": _collect_media_urls(candidate),
        "raw_urls": _collect_raw_urls(candidate),
        "first_seen_at": first_seen_at,
    }

    if normalized["first_seen_at"] is None:
        return None

    return normalized


def _extract_tweet_id(candidate: Mapping[str, Any]) -> str | None:
    direct_keys = (
        "tweet_id",
        "tweetId",
        "rest_id",
        "status_id",
        "id_str",
        "id",
    )
    for key in direct_keys:
        value = candidate.get(key)
        if value not in (None, ""):
            return str(value)

    legacy = candidate.get("legacy")
    if isinstance(legacy, Mapping):
        for key in ("id_str", "id"):
            value = legacy.get(key)
            if value not in (None, ""):
                return str(value)

    tweet_results = candidate.get("tweet_results") or candidate.get("tweetResults")
    if isinstance(tweet_results, Mapping):
        result = tweet_results.get("result")
        if isinstance(result, Mapping):
            return _extract_tweet_id(result)

    return None


def _extract_text(candidate: Mapping[str, Any]) -> str | None:
    direct_keys = ("text", "full_text", "content", "message")
    for key in direct_keys:
        value = candidate.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    legacy = candidate.get("legacy")
    if isinstance(legacy, Mapping):
        for key in ("full_text", "text"):
            value = legacy.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    note_tweet = candidate.get("note_tweet")
    if isinstance(note_tweet, Mapping):
        note_results = note_tweet.get("note_tweet_results")
        if isinstance(note_results, Mapping):
            result = note_results.get("result")
            if isinstance(result, Mapping):
                note_text = _extract_text(result)
                if note_text:
                    return note_text

    tweet_results = candidate.get("tweet_results") or candidate.get("tweetResults")
    if isinstance(tweet_results, Mapping):
        result = tweet_results.get("result")
        if isinstance(result, Mapping):
            return _extract_text(result)

    return None


def _extract_author_username(candidate: Mapping[str, Any]) -> str | None:
    username_keys = ("author_username", "username", "screen_name", "handle")
    for key in username_keys:
        value = _nested_or_direct(candidate, key)
        if isinstance(value, str) and value.strip():
            return value.strip().lstrip("@")

    core_user = _nested_get(candidate, ("core", "user_results", "result"))
    if isinstance(core_user, Mapping):
        core_legacy = _nested_get(
            candidate, ("core", "user_results", "result", "legacy")
        )
        if isinstance(core_legacy, Mapping):
            for key in ("screen_name", "username"):
                value = core_legacy.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().lstrip("@")

        legacy = core_user.get("legacy")
        if isinstance(legacy, Mapping):
            for key in ("screen_name", "username"):
                value = legacy.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip().lstrip("@")

        for key in ("screen_name", "username"):
            value = core_user.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lstrip("@")

    fallback = _deep_find_first_string(candidate, ("screen_name", "username"))
    if fallback:
        return fallback.lstrip("@")

    return None


def _extract_author_display_name(candidate: Mapping[str, Any]) -> str | None:
    display_keys = ("author_display_name", "display_name", "name", "authorName")
    for key in display_keys:
        value = _nested_or_direct(candidate, key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    core_user = _nested_get(candidate, ("core", "user_results", "result"))
    if isinstance(core_user, Mapping):
        core_legacy = _nested_get(
            candidate, ("core", "user_results", "result", "legacy")
        )
        if isinstance(core_legacy, Mapping):
            for key in ("name", "display_name"):
                value = core_legacy.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        legacy = core_user.get("legacy")
        if isinstance(legacy, Mapping):
            for key in ("name", "display_name"):
                value = legacy.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        for key in ("name", "display_name"):
            value = core_user.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    fallback = _deep_find_first_string(candidate, ("name", "display_name"))
    if fallback:
        return fallback

    return None


def _collect_media_urls(candidate: Mapping[str, Any]) -> list[str]:
    media_urls: list[str] = []
    for path in (
        ("legacy", "extended_entities", "media"),
        ("legacy", "entities", "media"),
        ("extended_entities", "media"),
        ("entities", "media"),
    ):
        for media in _collect_nested_items(candidate, path):
            media_url = _coalesce(
                media.get("media_url_https"),
                media.get("media_url"),
                media.get("url"),
            )
            if isinstance(media_url, str) and media_url not in media_urls:
                media_urls.append(media_url)

    return media_urls


def _collect_raw_urls(candidate: Mapping[str, Any]) -> list[str]:
    raw_urls: list[str] = []
    for url_entry in _collect_nested_items(candidate, ("legacy", "entities", "urls")):
        for key in ("url", "expanded_url", "display_url"):
            url_value = url_entry.get(key)
            if isinstance(url_value, str) and url_value and url_value not in raw_urls:
                raw_urls.append(url_value)
                break

    for url_entry in _collect_nested_items(candidate, ("entities", "urls")):
        for key in ("url", "expanded_url", "display_url"):
            url_value = url_entry.get(key)
            if isinstance(url_value, str) and url_value and url_value not in raw_urls:
                raw_urls.append(url_value)
                break

    return raw_urls


def _collect_nested_items(
    candidate: Mapping[str, Any],
    path: tuple[str, ...],
) -> list[Mapping[str, Any]]:
    value = _nested_get(candidate, path)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        return [value]
    return []


def _nested_get(candidate: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = candidate
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _nested_or_direct(candidate: Mapping[str, Any], key: str) -> Any:
    if key in candidate:
        return candidate.get(key)
    legacy = candidate.get("legacy")
    if isinstance(legacy, Mapping) and key in legacy:
        return legacy.get(key)
    return None


def _mapping_get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return default


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _deep_find_first_string(value: Any, key_names: tuple[str, ...]) -> str | None:
    if isinstance(value, Mapping):
        for key in key_names:
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
        for nested in value.values():
            found = _deep_find_first_string(nested, key_names)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _deep_find_first_string(item, key_names)
            if found:
                return found
    return None


def _preview(value: Any, limit: int = 240) -> str | None:
    try:
        preview = repr(value)
    except Exception:
        return None
    if len(preview) > limit:
        return f"{preview[:limit]}…"
    return preview
