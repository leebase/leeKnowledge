from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from leeknowledge import cli
from leeknowledge.db import (
    get_connection,
    initialize_database,
    insert_bookmark,
    insert_enrichment,
    upsert_url_cache,
)
from leeknowledge.exporter import (
    ExportError,
    export_markdown,
    export_story_markdown,
)


def _bookmark(tweet_id: str = "123") -> dict[str, object]:
    return {
        "tweet_id": tweet_id,
        "text": "Useful bookmark for the vault",
        "author_username": "lee",
        "author_display_name": "Lee Harrington",
        "created_at": None,
        "conversation_id": tweet_id,
        "in_reply_to_id": None,
        "media_urls": ["https://pbs.twimg.com/media/example.jpg"],
        "raw_urls": ["https://t.co/example"],
        "first_seen_at": "2026-04-07T09:05:00Z",
    }


def _enrichment(tweet_id: str = "123") -> dict[str, object]:
    return {
        "tweet_id": tweet_id,
        "summary": "A concise summary",
        "tags": ["research", "reading"],
        "entities": ["Example Inc"],
        "topic": "research",
        "model": "gpt-4o",
        "prompt_version": "1",
        "schema_version": "1",
        "validation_status": "valid",
        "enriched_at": "2026-04-07T09:10:00Z",
    }


def test_export_markdown_renders_source_grounded_notes(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(connection, _bookmark())
        insert_enrichment(connection, _enrichment())
        upsert_url_cache(
            connection,
            {
                "original_url": "https://t.co/example",
                "resolved_url": "https://example.com/article",
                "page_title": "Example article",
                "page_description": "A useful reference",
                "cached_at": "2026-04-07T09:08:00Z",
            },
        )

    result = export_markdown(db_path=db_path, vault_dir=vault_dir)

    assert result.exported_note_count == 1
    note_path = result.written_paths[0]
    assert note_path == vault_dir / "2026" / "04" / "useful-bookmark-for-the-vault-123.md"

    note_text = note_path.read_text()
    assert 'tweet_id: "123"' in note_text
    assert not (vault_dir / "topics").exists()
    assert 'author_username: "lee"' in note_text
    assert 'created_at: null' in note_text
    assert 'summary: "A concise summary"' in note_text
    assert 'resolved_urls:' in note_text
    assert '- "https://example.com/article"' in note_text
    assert '# @lee — 2026-04-07' in note_text
    assert 'Useful bookmark for the vault' in note_text
    assert '```text\nUseful bookmark for the vault\n```' in note_text
    assert 'URL: [https://example.com/article](https://example.com/article)' in note_text
    assert 'Title: Example article' in note_text
    assert 'Description: A useful reference' in note_text
    assert '[View on X](https://x.com/i/web/status/123)' in note_text


def test_export_story_markdown_fetches_story_content(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(connection, _bookmark())
        upsert_url_cache(
            connection,
            {
                "original_url": "https://t.co/example",
                "resolved_url": "https://example.com/article",
                "page_title": "Example article",
                "page_description": "A useful reference",
                "cached_at": "2026-04-07T09:08:00Z",
            },
        )

    fetched_urls: list[str] = []

    def fetcher(url: str) -> str:
        fetched_urls.append(url)
        return "Fetched full article body"

    result = export_story_markdown(
        db_path=db_path,
        vault_dir=vault_dir,
        story_content_fetcher=fetcher,
    )

    assert result.exported_note_count == 1
    note_path = result.written_paths[0]
    assert note_path == vault_dir / "stories" / "2026" / "04" / "useful-bookmark-for-the-vault-123.md"

    note_text = note_path.read_text()
    assert "## Story content" in note_text
    assert "```text\nFetched full article body\n```" in note_text
    assert "## Tweet text" in note_text
    assert "Useful bookmark for the vault" in note_text
    assert fetched_urls == ["https://example.com/article"]


def test_export_story_markdown_falls_back_to_tweet_text_when_fetch_fails(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark("x-fallback"),
        )

    def fetcher(url: str) -> str:
        return ""

    result = export_story_markdown(
        db_path=db_path,
        vault_dir=vault_dir,
        story_content_fetcher=fetcher,
    )

    assert result.exported_note_count == 1
    note_text = result.written_paths[0].read_text()
    assert "story_content_type: \"Tweet text\"" in note_text
    assert "```text\nUseful bookmark for the vault\n```" in note_text


def test_export_story_markdown_ignores_x_error_page_and_falls_back_to_tweet_text(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark("x-error")
            | {
                "tweet_id": "x-error",
                "source_name": "x",
                "source_type": "x_bookmark",
                "source_item_id": "x-error",
                "source_ref": "https://x.com/i/web/status/x-error",
                "raw_urls": [],
            },
        )

    def fetcher(url: str) -> str:
        return (
            "Something went wrong, but don’t fret — let’s give it another shot.\n"
            "Try again\n"
            "Some privacy related extensions may cause issues on x.com. "
            "Please disable them and try again."
        )

    result = export_story_markdown(
        db_path=db_path,
        vault_dir=vault_dir,
        story_content_fetcher=fetcher,
    )

    assert result.exported_note_count == 1
    note_text = result.written_paths[0].read_text()
    assert "story_content_type: \"Tweet text\"" in note_text
    assert "## Tweet text" in note_text
    assert "Useful bookmark for the vault" in note_text
    assert "Something went wrong" not in note_text


def test_export_story_markdown_follows_linked_tweet_when_article_exists(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark("111111111111111111")
            | {
                "source_name": "x",
                "source_type": "x_bookmark",
                "source_item_id": "111111111111111111",
                "source_ref": "https://x.com/i/web/status/Tm90ZVR3ZWV0OjExMTExMTExMTExMTExMTE=",
                "text": (
                    "Quoted post here: https://x.com/i/web/status/2043362828090748928 "
                    "for the actual article."
                ),
                "raw_urls": [],
            },
        )
        upsert_url_cache(
            connection,
            {
                "original_url": "https://t.co/example",
                "resolved_url": "https://example.com/linked-story",
                "page_title": "Linked article",
                "page_description": "A story reference",
                "cached_at": "2026-04-15T14:00:00Z",
            },
        )
        insert_bookmark(
            connection,
            _bookmark("2043362828090748928")
            | {
                "source_name": "x",
                "source_type": "x_bookmark",
                "source_item_id": "2043362828090748928",
                "source_ref": "https://x.com/i/web/status/2043362828090748928",
                "raw_urls": ["https://t.co/example"],
                "text": "Linked tweet with article link.",
            },
        )

    def fetcher(url: str) -> str:
        if url == "https://example.com/linked-story":
            return "Linked tweet article body"
        return ""

    result = export_story_markdown(
        db_path=db_path,
        vault_dir=vault_dir,
        story_content_fetcher=fetcher,
    )

    assert result.exported_note_count == 2
    linked_notes = [
        path.read_text()
        for path in result.written_paths
        if "2043362828090748928" in path.name
    ]
    assert linked_notes, "expected linked tweet story file to be exported"
    note_text = linked_notes[0]
    assert "story_content_type: \"Linked tweet story (2043362828090748928)\"" in note_text
    assert "```text\nLinked tweet article body\n```" in note_text


def test_export_fails_when_database_path_is_missing(tmp_path):
    db_path = tmp_path / "state" / "missing.db"
    vault_dir = tmp_path / "vault"

    try:
        export_markdown(db_path=db_path, vault_dir=vault_dir)
    except ExportError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("export_markdown() should fail for a missing database")

    assert "SQLite database does not exist" in message
    assert not db_path.exists()


def test_export_fails_for_legacy_database_schema(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE bookmarks (
                tweet_id TEXT PRIMARY KEY,
                source_name TEXT,
                source_type TEXT,
                source_item_id TEXT,
                source_ref TEXT,
                text TEXT NOT NULL,
                author_username TEXT,
                author_display_name TEXT,
                created_at TIMESTAMP,
                conversation_id TEXT,
                in_reply_to_id TEXT,
                media_urls TEXT,
                raw_urls TEXT,
                first_seen_at TIMESTAMP NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE enrichments (
                tweet_id TEXT PRIMARY KEY,
                summary TEXT,
                tags TEXT,
                entities TEXT,
                topic TEXT,
                model TEXT,
                enriched_at TIMESTAMP,
                FOREIGN KEY (tweet_id) REFERENCES bookmarks(tweet_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE url_cache (
                original_url TEXT PRIMARY KEY,
                resolved_url TEXT,
                page_title TEXT,
                page_description TEXT,
                cached_at TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            INSERT INTO bookmarks (
                tweet_id,
                source_name,
                source_type,
                source_item_id,
                source_ref,
                text,
                author_username,
                author_display_name,
                created_at,
                conversation_id,
                in_reply_to_id,
                media_urls,
                raw_urls,
                first_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "123",
                "x",
                "x_bookmark",
                "123",
                "https://x.com/i/web/status/123",
                "Legacy database bookmark",
                "lee",
                "Lee Harrington",
                None,
                "123",
                None,
                '["https://pbs.twimg.com/media/example.jpg"]',
                '["https://t.co/example"]',
                "2026-04-07T09:05:00Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO enrichments (
                tweet_id,
                summary,
                tags,
                entities,
                topic,
                model,
                enriched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "123",
                "A concise summary",
                '["research"]',
                '["Example Inc"]',
                "research",
                "gpt-4o",
                "2026-04-07T09:10:00Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO url_cache (
                original_url,
                resolved_url,
                page_title,
                page_description,
                cached_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "https://t.co/example",
                "https://example.com/article",
                "Example article",
                "A useful reference",
                "2026-04-07T09:08:00Z",
            ),
        )
        connection.commit()

    try:
        export_markdown(db_path=db_path, vault_dir=vault_dir)
    except ExportError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("export_markdown() should fail for a legacy schema")

    assert "missing required columns" in message
    assert "prompt_version" in message
    assert "schema_version" in message
    assert "validation_status" in message


def test_export_preserves_markdown_sensitive_content(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark("md-1")
            | {
                "text": "# Header\n- bullet with *stars* and [link](https://example.com)",
            },
        )
        insert_enrichment(
            connection,
            _enrichment("md-1")
            | {
                "summary": "Summary with #hash and *stars* plus [link](https://example.com)",
            },
        )
        upsert_url_cache(
            connection,
            {
                "original_url": "https://t.co/example",
                "resolved_url": "https://example.com/article",
                "page_title": "Example [article]",
                "page_description": "Description with *stars* and #hash",
                "cached_at": "2026-04-07T09:08:00Z",
            },
        )

    result = export_markdown(db_path=db_path, vault_dir=vault_dir)
    note_text = result.written_paths[0].read_text()

    assert "```text\nSummary with #hash and *stars* plus [link](https://example.com)\n```" in note_text
    assert "```text\n# Header\n- bullet with *stars* and [link](https://example.com)\n```" in note_text
    assert r"Title: Example \[article\]" in note_text
    assert r"Description: Description with \*stars\* and \#hash" in note_text


def test_sync_runs_extract_enrich_export_in_order(tmp_path, monkeypatch):
    calls: list[str] = []

    def fake_extract_bookmarks(**kwargs):
        calls.append("extract")
        return SimpleNamespace(
            captured_payload_count=1,
            normalized_record_count=1,
            inserted_record_count=1,
            archive_path=tmp_path / "raw" / "bookmarks_2026-04-07.json",
            skipped_issues=(),
        )

    def fake_enrich_bookmarks(**kwargs):
        calls.append("enrich")
        return SimpleNamespace(
            processed_bookmark_count=1,
            inserted_enrichment_count=1,
            skipped_existing_count=0,
            placeholder_count=0,
            cached_url_count=0,
        )

    def fake_export_markdown(**kwargs):
        calls.append("export")
        return SimpleNamespace(exported_note_count=1, written_paths=(tmp_path / "vault" / "note.md",))

    monkeypatch.setattr(cli, "extract_bookmarks", fake_extract_bookmarks)
    monkeypatch.setattr(cli, "enrich_bookmarks", fake_enrich_bookmarks)
    monkeypatch.setattr(cli, "export_markdown", fake_export_markdown)

    cli.run_sync(
        raw_output_dir=tmp_path / "raw",
        db_path=tmp_path / "state" / "app.db",
        chrome_profile_dir=None,
        headless=False,
        config_path=tmp_path / "config" / "llm.yaml",
        vault_dir=tmp_path / "vault",
    )

    assert calls == ["extract", "enrich", "export"]
