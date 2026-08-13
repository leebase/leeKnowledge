from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from leeknowledge.db import get_connection, initialize_database
from leeknowledge.extractor import (
    DEFAULT_BOOKMARKS_URL,
    AuthenticationError,
    EmptyCaptureError,
    capture_bookmarks_from_chrome,
    extract_bookmarks,
    _ensure_authenticated_bookmarks_page,
)
from leeknowledge.normalizer import normalize_payloads, normalize_raw_archive


def _graphql_like_bookmark_payload(tweet_id: str = "123") -> dict[str, object]:
    full_text = "A useful bookmark"
    created_at = "Mon Apr 07 09:00:00 +0000 2026"
    conversation_id_str = tweet_id
    in_reply_to_status_id_str = None
    expanded_url = "https://example.com/article"
    media_url_https = "https://pbs.twimg.com/media/example.jpg"
    screen_name = "lee"
    display_name = "Lee Harrington"

    legacy_user = {
        "screen_name": screen_name,
        "name": display_name,
    }
    entities = {
        "urls": [
            {
                "url": "https://t.co/example",
                "expanded_url": expanded_url,
            }
        ],
        "media": [
            {
                "media_url_https": media_url_https,
            }
        ],
    }
    legacy = {
        "full_text": full_text,
        "created_at": created_at,
        "conversation_id_str": conversation_id_str,
        "in_reply_to_status_id_str": in_reply_to_status_id_str,
        "entities": entities,
    }
    user_results = {
        "result": {
            "legacy": legacy_user,
        }
    }
    core = {
        "user_results": user_results,
    }

    return {
        "payload": {
            "data": {
                "bookmark_timeline": {
                    "timeline": {
                        "instructions": [
                            {
                                "type": "TimelineAddEntries",
                                "entries": [
                                    {
                                        "entryId": f"tweet-{tweet_id}",
                                        "content": {
                                            "entryType": "TimelineTimelineItem",
                                            "itemContent": {
                                                "itemType": "TimelineTweet",
                                                "tweet_results": {
                                                    "result": {
                                                        "rest_id": tweet_id,
                                                        "legacy": legacy,
                                                        "core": core,
                                                    }
                                                },
                                            },
                                        },
                                    }
                                ],
                            }
                        ]
                    }
                }
            }
        }
    }


def test_normalize_raw_archive_extracts_canonical_fields_and_dedupes():
    archive = {
        "captured_at": "2026-04-07T09:05:00Z",
        "bookmark_payloads": [
            _graphql_like_bookmark_payload("123"),
            _graphql_like_bookmark_payload("123"),
            {"payload": {"data": {"noop": True}}},
        ],
    }

    result = normalize_raw_archive(archive)

    assert len(result.records) == 1
    assert len(result.skipped) == 1
    record = result.records[0]
    assert record["tweet_id"] == "123"
    assert record["text"] == "A useful bookmark"
    assert record["author_username"] == "lee"
    assert record["author_display_name"] == "Lee Harrington"
    assert record["created_at"] == "Mon Apr 07 09:00:00 +0000 2026"
    assert record["conversation_id"] == "123"
    assert record["in_reply_to_id"] is None
    assert record["media_urls"] == ["https://pbs.twimg.com/media/example.jpg"]
    assert record["raw_urls"] == ["https://t.co/example"]
    assert record["first_seen_at"] == "2026-04-07T09:05:00Z"

    assert normalize_payloads(archive)[0]["tweet_id"] == "123"


def test_extract_bookmarks_persists_raw_archive_and_inserts_rows(tmp_path, monkeypatch):
    db_path = tmp_path / "state" / "app.db"
    initialize_database(db_path)

    chrome_profile_dir = tmp_path / "chrome"
    chrome_profile_dir.mkdir(parents=True)
    raw_output_dir = tmp_path / "raw"

    captured_payload = _graphql_like_bookmark_payload("456")

    def fake_capture(*args, **kwargs):
        return [captured_payload]

    result = extract_bookmarks(
        raw_output_dir=raw_output_dir,
        db_path=db_path,
        chrome_profile_dir=chrome_profile_dir,
        capture_func=fake_capture,
    )

    assert result.captured_payload_count == 1
    assert result.normalized_record_count == 1
    assert result.inserted_record_count == 1
    assert result.archive_path.exists()

    archive = json.loads(result.archive_path.read_text())
    assert archive["source"]["chrome_profile_dir"] == str(chrome_profile_dir)
    assert archive["bookmark_payloads"]

    with get_connection(db_path) as connection:
        row = connection.execute(
            (
                "SELECT tweet_id, text, author_username, raw_urls, media_urls "
                "FROM bookmarks WHERE tweet_id = ?"
            ),
            ("456",),
        ).fetchone()

    assert row["tweet_id"] == "456"
    assert row["text"] == "A useful bookmark"
    assert row["author_username"] == "lee"
    assert json.loads(row["raw_urls"]) == ["https://t.co/example"]
    assert json.loads(row["media_urls"]) == ["https://pbs.twimg.com/media/example.jpg"]


def test_extract_bookmarks_with_empty_capture_writes_archive_then_stops(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    initialize_database(db_path)

    chrome_profile_dir = tmp_path / "chrome"
    chrome_profile_dir.mkdir(parents=True)
    raw_output_dir = tmp_path / "raw"

    with pytest.raises(EmptyCaptureError):
        extract_bookmarks(
            raw_output_dir=raw_output_dir,
            db_path=db_path,
            chrome_profile_dir=chrome_profile_dir,
            capture_func=lambda *args, **kwargs: [],
        )

    with get_connection(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM bookmarks"
        ).fetchone()["count"]

    assert count == 0
    assert any(raw_output_dir.glob("bookmarks_*.json"))


def test_extract_bookmarks_with_empty_capture_does_not_create_database(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    chrome_profile_dir = tmp_path / "chrome"
    chrome_profile_dir.mkdir(parents=True)
    raw_output_dir = tmp_path / "raw"

    with pytest.raises(EmptyCaptureError):
        extract_bookmarks(
            raw_output_dir=raw_output_dir,
            db_path=db_path,
            chrome_profile_dir=chrome_profile_dir,
            capture_func=lambda *args, **kwargs: [],
        )

    assert not db_path.exists()
    assert any(raw_output_dir.glob("bookmarks_*.json"))


def test_extract_bookmarks_uses_custom_bookmarks_url(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    initialize_database(db_path)

    chrome_profile_dir = tmp_path / "chrome"
    chrome_profile_dir.mkdir(parents=True)
    raw_output_dir = tmp_path / "raw"

    captured_payload = _graphql_like_bookmark_payload("789")
    observed_urls: list[str] = []

    def fake_capture(*args, **kwargs):
        observed_urls.append(args[1])
        return [captured_payload]

    folder_url = "https://x.com/i/bookmarks/folder/my-favorite-folder"
    extract_bookmarks(
        raw_output_dir=raw_output_dir,
        db_path=db_path,
        chrome_profile_dir=chrome_profile_dir,
        bookmarks_url=folder_url,
        capture_func=fake_capture,
    )

    assert observed_urls == [folder_url]

    archive = json.loads(next(raw_output_dir.glob("bookmarks_*.json")).read_text())
    assert archive["source"]["bookmarks_url"] == folder_url


def test_extract_bookmarks_defaults_to_global_bookmarks_url(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    initialize_database(db_path)

    chrome_profile_dir = tmp_path / "chrome"
    chrome_profile_dir.mkdir(parents=True)
    raw_output_dir = tmp_path / "raw"

    captured_payload = _graphql_like_bookmark_payload("790")

    def fake_capture(*args, **kwargs):
        return [captured_payload]

    extract_bookmarks(
        raw_output_dir=raw_output_dir,
        db_path=db_path,
        chrome_profile_dir=chrome_profile_dir,
        capture_func=fake_capture,
    )

    archive = json.loads(next(raw_output_dir.glob("bookmarks_*.json")).read_text())
    assert archive["source"]["bookmarks_url"] == DEFAULT_BOOKMARKS_URL


def test_capture_bookmarks_uses_explicit_cdp_endpoint_without_launching(
    tmp_path, monkeypatch
):
    calls: list[tuple[str, str | None]] = []

    class FakePage:
        url = DEFAULT_BOOKMARKS_URL

        def on(self, *_args):
            return None

        def goto(self, url, **_kwargs):
            self.url = url

        def title(self):
            return "Bookmarks / X"

        def content(self):
            return "<html><body>Bookmarks</body></html>"

        def evaluate(self, *_args):
            return None

        def wait_for_timeout(self, *_args):
            return None

    class FakeContext:
        pages = [FakePage()]

        def new_page(self):
            return FakePage()

        def close(self):
            calls.append(("close", None))

    class FakeBrowser:
        contexts = [FakeContext()]

        def new_context(self):
            return FakeContext()

    class FakeChromium:
        def connect_over_cdp(self, endpoint):
            calls.append(("connect_over_cdp", endpoint))
            return FakeBrowser()

        def launch_persistent_context(self, **_kwargs):
            calls.append(("launch_persistent_context", None))
            raise AssertionError("explicit CDP endpoint should not launch Chrome")

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeSyncPlaywright:
        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, *_args):
            return None

    fake_sync_api = SimpleNamespace(sync_playwright=lambda: FakeSyncPlaywright())
    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync_api)

    payloads = capture_bookmarks_from_chrome(
        chrome_profile_dir=tmp_path,
        cdp_endpoint="http://127.0.0.1:9222",
        scroll_delay_seconds=(0, 0),
        no_new_content_retries=1,
        max_scroll_attempts=1,
    )

    assert payloads == []
    assert calls == [("connect_over_cdp", "http://127.0.0.1:9222")]


def test_ensure_authenticated_bookmarks_page_raises_for_unauthenticated_folder_url():
    page = SimpleNamespace(
        url="https://x.com/i/bookmarks/1861633264378626184",
        title=lambda: "Page not found / X",
        content=lambda: "<html><body>Log in</body></html>",
    )

    with pytest.raises(AuthenticationError):
        _ensure_authenticated_bookmarks_page(page)
