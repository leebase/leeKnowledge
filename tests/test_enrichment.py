from __future__ import annotations

import json

import pytest

from leeknowledge.db import get_connection, initialize_database, insert_bookmark
from leeknowledge.enricher import EnrichmentConfigError, enrich_bookmarks


class _FakeResponse:
    def __init__(self, url: str, text: str):
        self.url = url
        self.text = text


class _FakeClient:
    def __init__(self, response_url: str, response_text: str):
        self.response_url = response_url
        self.response_text = response_text
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, follow_redirects: bool = True, timeout: float | None = None):
        self.calls.append(url)
        return _FakeResponse(self.response_url, self.response_text)


def _bookmark(tweet_id: str, raw_url: str = "https://example.com/article") -> dict[str, object]:
    return {
        "tweet_id": tweet_id,
        "text": "A useful bookmark",
        "author_username": "lee",
        "author_display_name": "Lee Harrington",
        "created_at": "2026-04-07T09:00:00Z",
        "conversation_id": tweet_id,
        "in_reply_to_id": None,
        "media_urls": [],
        "raw_urls": [raw_url],
        "first_seen_at": "2026-04-07T09:05:00Z",
    }


def test_enrich_bookmarks_persists_valid_rows_and_reuses_url_cache(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(connection, _bookmark("123", "https://example.com/a"))
        insert_bookmark(connection, _bookmark("456", "https://example.com/a"))

    client = _FakeClient(
        "https://example.com/final",
        "<html><head><title>Example article</title><meta name='description' content='A summary'></head><body></body></html>",
    )

    prompts: list[str] = []

    def model_runner(config, prompt: str):
        prompts.append(prompt)
        return {
            "summary": "Concise summary",
            "tags": ["reading", "research"],
            "entities": ["Example Inc"],
            "topic": "Research",
        }

    result = enrich_bookmarks(
        db_path=db_path,
        model_runner=model_runner,
        http_client_factory=lambda: client,
    )

    assert result.processed_bookmark_count == 2
    assert result.inserted_enrichment_count == 2
    assert result.placeholder_count == 0
    assert result.cached_url_count == 1
    assert client.calls == ["https://example.com/a"]
    assert prompts[0]
    assert "A useful bookmark" in prompts[0]
    assert "https://example.com/final" in prompts[0]

    with get_connection(db_path) as connection:
        first_row = connection.execute(
            """
            SELECT tweet_id, summary, tags, entities, topic, model,
                   prompt_version, schema_version, validation_status
            FROM enrichments
            WHERE tweet_id = ?
            """,
            ("123",),
        ).fetchone()
        cache_row = connection.execute(
            "SELECT original_url, resolved_url, page_title, page_description FROM url_cache"
        ).fetchone()

    assert first_row["tweet_id"] == "123"
    assert first_row["summary"] == "Concise summary"
    assert json.loads(first_row["tags"]) == ["reading", "research"]
    assert json.loads(first_row["entities"]) == ["Example Inc"]
    assert first_row["topic"] == "Research"
    assert first_row["model"] == "gpt-4o"
    assert first_row["prompt_version"] == "1"
    assert first_row["schema_version"] == "1"
    assert first_row["validation_status"] == "valid"
    assert cache_row["original_url"] == "https://example.com/a"
    assert cache_row["resolved_url"] == "https://example.com/final"
    assert cache_row["page_title"] == "Example article"
    assert cache_row["page_description"] == "A summary"

    rerun = enrich_bookmarks(db_path=db_path, model_runner=model_runner, http_client_factory=lambda: client)
    assert rerun.processed_bookmark_count == 0
    assert rerun.inserted_enrichment_count == 0


def test_enrich_bookmarks_records_placeholder_for_invalid_json(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(connection, _bookmark("789"))

    result = enrich_bookmarks(
        db_path=db_path,
        model_runner=lambda config, prompt: "not valid json",
        http_client_factory=lambda: _FakeClient("https://example.com/final", "<html></html>"),
    )

    assert result.processed_bookmark_count == 1
    assert result.inserted_enrichment_count == 1
    assert result.placeholder_count == 1
    assert result.failed_bookmark_count == 1

    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT summary, tags, entities, topic, validation_status FROM enrichments WHERE tweet_id = ?",
            ("789",),
        ).fetchone()

    assert row["summary"] is None
    assert row["tags"] is None
    assert row["entities"] is None
    assert row["topic"] is None
    assert row["validation_status"] == "invalid_json"


def test_enrich_bookmarks_fails_before_creating_db_when_config_is_missing(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    config_path = tmp_path / "missing" / "llm.yaml"

    with pytest.raises(EnrichmentConfigError):
        enrich_bookmarks(db_path=db_path, config_path=config_path)

    assert not db_path.exists()
