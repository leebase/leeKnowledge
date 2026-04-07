"""
Extraction stage implementation.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from leeknowledge import __version__
from leeknowledge.db import (
    APP_DB_PATH,
    get_connection,
    initialize_database,
    insert_bookmark,
)
from leeknowledge.normalizer import NormalizationIssue, normalize_raw_archive

DEFAULT_BOOKMARKS_URL = "https://x.com/i/bookmarks"
DEFAULT_SCROLL_DELAY_SECONDS = (1.5, 3.0)
DEFAULT_NO_NEW_CONTENT_RETRIES = 5
DEFAULT_MAX_SCROLL_ATTEMPTS = 100
DEFAULT_VIEWPORT = {"width": 1280, "height": 800}


class ExtractionError(RuntimeError):
    """Raised when the extraction pipeline cannot complete safely."""


class AuthenticationError(ExtractionError):
    """Raised when X redirects the browser to the login flow."""


class EmptyCaptureError(ExtractionError):
    """Raised when no bookmark payloads are captured."""


@dataclass(frozen=True)
class ExtractionConfig:
    """Configuration for a single extraction run."""

    chrome_profile_dir: Path
    raw_output_dir: Path = Path("data/raw")
    db_path: Path = APP_DB_PATH
    bookmarks_url: str = DEFAULT_BOOKMARKS_URL
    headless: bool = False
    scroll_delay_seconds: tuple[float, float] = DEFAULT_SCROLL_DELAY_SECONDS
    no_new_content_retries: int = DEFAULT_NO_NEW_CONTENT_RETRIES
    max_scroll_attempts: int = DEFAULT_MAX_SCROLL_ATTEMPTS


@dataclass(frozen=True)
class ExtractionRunResult:
    """Summary of a completed extraction run."""

    archive_path: Path
    captured_payload_count: int
    normalized_record_count: int
    inserted_record_count: int
    skipped_issues: tuple[NormalizationIssue, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RawCaptureArchive:
    """Immutable raw archive written before normalization starts."""

    captured_at: str
    source: Mapping[str, Any]
    bookmark_payloads: tuple[Mapping[str, Any], ...]
    version: str = __version__

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "captured_at": self.captured_at,
            "source": dict(self.source),
            "bookmark_payloads": [dict(payload) for payload in self.bookmark_payloads],
        }


CaptureFunction = Callable[
    [Path, str, bool, tuple[float, float], int, int], list[dict[str, Any]]
]


def resolve_chrome_profile_dir(chrome_profile_dir: Path | str | None = None) -> Path:
    """Resolve the Chrome user data directory used for extraction.

    Lee can point this at the root Chrome user data directory or a specific
    profile path. The resolver is intentionally explicit so the extractor fails
    fast when the browser state is not configured.
    """

    if chrome_profile_dir is not None:
        resolved = Path(chrome_profile_dir).expanduser()
        if resolved.exists():
            return resolved
        raise ExtractionError(f"Chrome profile directory does not exist: {resolved}")

    env_value = os.environ.get("LEEKNOWLEDGE_CHROME_PROFILE_DIR") or os.environ.get(
        "LEEKNOWLEDGE_CHROME_USER_DATA_DIR"
    )
    if env_value:
        resolved = Path(env_value).expanduser()
        if resolved.exists():
            return resolved
        raise ExtractionError(f"Chrome profile directory does not exist: {resolved}")

    mac_default = Path.home() / "Library/Application Support/Google/Chrome"
    if mac_default.exists():
        return mac_default

    raise ExtractionError(
        "Chrome profile directory is not configured. Set "
        "LEEKNOWLEDGE_CHROME_PROFILE_DIR to your Chrome user data directory."
    )


def capture_bookmarks_from_chrome(
    chrome_profile_dir: Path,
    bookmarks_url: str = DEFAULT_BOOKMARKS_URL,
    headless: bool = False,
    scroll_delay_seconds: tuple[float, float] = DEFAULT_SCROLL_DELAY_SECONDS,
    no_new_content_retries: int = DEFAULT_NO_NEW_CONTENT_RETRIES,
    max_scroll_attempts: int = DEFAULT_MAX_SCROLL_ATTEMPTS,
) -> list[dict[str, Any]]:
    """Launch Chrome, navigate to bookmarks, and capture GraphQL bookmark payloads."""

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - depends on local environment.
        raise ExtractionError(
            "Playwright is required for extraction. Install the dev dependencies "
            "before running `extract`."
        ) from exc

    captured_payloads: list[dict[str, Any]] = []
    last_count = 0
    no_new_content_count = 0

    def handle_response(response: Any) -> None:
        payload = _response_to_captured_payload(response)
        if payload is not None:
            captured_payloads.append(payload)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(chrome_profile_dir),
            channel="chrome",
            headless=headless,
            viewport=DEFAULT_VIEWPORT,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.on("response", handle_response)
            page.goto(bookmarks_url, wait_until="domcontentloaded", timeout=45_000)
            _ensure_authenticated_bookmarks_page(page)

            for _ in range(max_scroll_attempts):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(int(random.uniform(*scroll_delay_seconds) * 1000))

                if len(captured_payloads) == last_count:
                    no_new_content_count += 1
                    if no_new_content_count >= no_new_content_retries:
                        break
                else:
                    last_count = len(captured_payloads)
                    no_new_content_count = 0
        finally:
            context.close()

    return captured_payloads


def persist_raw_archive(
    archive: RawCaptureArchive,
    raw_output_dir: Path,
) -> Path:
    """Write the immutable raw archive to disk and never overwrite an existing run."""

    raw_output_dir.mkdir(parents=True, exist_ok=True)
    base_path = raw_output_dir / f"bookmarks_{archive.captured_at[:10]}.json"
    archive_path = (
        base_path if not base_path.exists() else _unique_archive_path(base_path)
    )
    archive_path.write_text(
        json.dumps(archive.to_dict(), indent=2, ensure_ascii=False) + "\n"
    )
    return archive_path


def extract_bookmarks(
    raw_output_dir: Path,
    db_path: Path | None = None,
    chrome_profile_dir: Path | str | None = None,
    headless: bool = False,
    capture_func: CaptureFunction | None = None,
) -> ExtractionRunResult:
    """Run the extraction slice end-to-end.

    The extractor owns Chrome access, raw archive persistence, and SQLite writes.
    Normalization is deterministic and happens only after the raw archive is
    safely written.
    """

    resolved_db_path = Path(db_path) if db_path is not None else APP_DB_PATH
    resolved_profile_dir = resolve_chrome_profile_dir(chrome_profile_dir)
    capture = capture_func or capture_bookmarks_from_chrome
    captured_payloads = capture(
        resolved_profile_dir,
        DEFAULT_BOOKMARKS_URL,
        headless,
        DEFAULT_SCROLL_DELAY_SECONDS,
        DEFAULT_NO_NEW_CONTENT_RETRIES,
        DEFAULT_MAX_SCROLL_ATTEMPTS,
    )

    archive = RawCaptureArchive(
        captured_at=_utc_now(),
        source={
            "bookmarks_url": DEFAULT_BOOKMARKS_URL,
            "chrome_profile_dir": str(resolved_profile_dir),
            "headless": headless,
        },
        bookmark_payloads=tuple(captured_payloads),
    )
    archive_path = persist_raw_archive(archive, raw_output_dir)

    if not captured_payloads:
        raise EmptyCaptureError(
            f"No bookmark payloads were captured from {DEFAULT_BOOKMARKS_URL}. "
            f"Raw archive written to {archive_path}, SQLite left unchanged."
        )

    normalization_result = normalize_raw_archive(archive.to_dict())
    initialize_database(resolved_db_path)

    inserted_count = 0
    with get_connection(resolved_db_path) as connection:
        for bookmark in normalization_result.records:
            if insert_bookmark(connection, bookmark):
                inserted_count += 1

    return ExtractionRunResult(
        archive_path=archive_path,
        captured_payload_count=len(captured_payloads),
        normalized_record_count=len(normalization_result.records),
        inserted_record_count=inserted_count,
        skipped_issues=tuple(normalization_result.skipped),
    )


def _ensure_authenticated_bookmarks_page(page: Any) -> None:
    current_url = getattr(page, "url", "").lower()
    if any(marker in current_url for marker in ("/i/flow/login", "/login", "/signin")):
        raise AuthenticationError(
            "Chrome reached the X login flow instead of "
            "the authenticated bookmarks page."
        )

    try:
        title = page.title().lower()
    except Exception:  # pragma: no cover - defensive against browser oddities.
        title = ""

    if "sign in" in title and "bookmarks" not in current_url:
        raise AuthenticationError(
            "Chrome did not reach an authenticated bookmarks session. "
            "Please log in to X in the selected Chrome profile and retry."
        )


def _response_to_captured_payload(response: Any) -> dict[str, Any] | None:
    request = getattr(response, "request", None)
    response_url = getattr(response, "url", "")
    request_url = getattr(request, "url", "")
    post_data = getattr(request, "post_data", None)
    if callable(post_data):
        try:
            post_data = post_data()
        except Exception:  # pragma: no cover - defensive.
            post_data = None

    candidate_markers = [
        str(response_url),
        str(request_url),
        str(post_data or ""),
    ]
    if not any("graphql" in marker.lower() for marker in candidate_markers):
        return None
    if not any("bookmark" in marker.lower() for marker in candidate_markers):
        return None

    try:
        body_text = response.text()
    except Exception:
        body_text = ""

    if not body_text:
        return None

    try:
        parsed_body: Any = json.loads(body_text)
    except json.JSONDecodeError:
        parsed_body = body_text

    operation_name = _extract_operation_name(post_data, body_text, parsed_body)
    if operation_name and "bookmark" not in operation_name.lower():
        return None

    return {
        "captured_at": _utc_now(),
        "response_url": response_url,
        "request_url": request_url,
        "request_method": getattr(request, "method", None),
        "status": getattr(response, "status", None),
        "operation_name": operation_name,
        "payload": parsed_body,
        "raw_text": body_text,
    }


def _extract_operation_name(
    post_data: Any,
    body_text: str,
    parsed_body: Any,
) -> str | None:
    for source in (post_data, body_text):
        if isinstance(source, str) and "Bookmarks" in source:
            return "Bookmarks"

    if isinstance(parsed_body, Mapping):
        operation = parsed_body.get("operationName") or parsed_body.get(
            "operation_name"
        )
        if isinstance(operation, str):
            return operation

    return None


def _unique_archive_path(base_path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%H%M%S")
    candidate = base_path.with_name(f"{base_path.stem}_{timestamp}{base_path.suffix}")
    suffix = 1
    while candidate.exists():
        candidate = base_path.with_name(
            f"{base_path.stem}_{timestamp}_{suffix}{base_path.suffix}"
        )
        suffix += 1
    return candidate


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
