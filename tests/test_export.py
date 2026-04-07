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
from leeknowledge.exporter import export_markdown


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
    assert 'author_username: "lee"' in note_text
    assert 'created_at: null' in note_text
    assert 'summary: "A concise summary"' in note_text
    assert 'resolved_urls:' in note_text
    assert '- "https://example.com/article"' in note_text
    assert '# @lee — 2026-04-07' in note_text
    assert 'Useful bookmark for the vault' in note_text
    assert 'Example article' in note_text
    assert 'A useful reference' in note_text
    assert '[View on X](https://x.com/i/web/status/123)' in note_text


def test_export_migrates_existing_database_schema(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE bookmarks (
                tweet_id TEXT PRIMARY KEY,
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
                text,
                author_username,
                author_display_name,
                created_at,
                conversation_id,
                in_reply_to_id,
                media_urls,
                raw_urls,
                first_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "123",
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

    result = export_markdown(db_path=db_path, vault_dir=vault_dir)

    assert result.exported_note_count == 1
    note_path = result.written_paths[0]
    assert note_path.exists()
    assert note_path.read_text().startswith("---\ntweet_id: \"123\"")


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
