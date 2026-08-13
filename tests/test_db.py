from __future__ import annotations

from leeknowledge.db import get_connection, initialize_database, insert_bookmark


def test_initialize_database_creates_expected_tables(tmp_path):
    db_path = tmp_path / "app.db"

    initialize_database(db_path)

    with get_connection(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()

    table_names = {row["name"] for row in rows}
    assert {"bookmarks", "enrichments", "url_cache", "leadership_metadata", "bookmarks_fts"} <= table_names

    with get_connection(db_path) as connection:
        enrichment_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(enrichments)")
        }
        leadership_metadata_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(leadership_metadata)")
        }

    assert {"prompt_version", "schema_version", "validation_status"} <= enrichment_columns
    assert {
        "strategic_relevance",
        "time_horizon",
        "organizational_impact",
        "leadership_question",
        "model",
        "prompt_version",
        "schema_version",
        "validation_status",
        "generated_at",
    } <= leadership_metadata_columns


def test_insert_bookmark_ignores_duplicate_tweet_ids(tmp_path):
    db_path = tmp_path / "app.db"
    initialize_database(db_path)

    bookmark = {
        "tweet_id": "123",
        "text": "A useful bookmark",
        "author_username": "lee",
        "author_display_name": "Lee Harrington",
        "created_at": "2026-04-07T09:00:00Z",
        "conversation_id": "123",
        "in_reply_to_id": None,
        "media_urls": [],
        "raw_urls": ["https://t.co/example"],
        "first_seen_at": "2026-04-07T09:05:00Z",
    }

    with get_connection(db_path) as connection:
        first_insert = insert_bookmark(connection, bookmark)
        second_insert = insert_bookmark(connection, bookmark)
        row = connection.execute(
            "SELECT tweet_id, text FROM bookmarks WHERE tweet_id = ?",
            (bookmark["tweet_id"],),
        ).fetchone()
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM bookmarks"
        ).fetchone()["count"]

    assert first_insert is True
    assert second_insert is False
    assert row["tweet_id"] == "123"
    assert row["text"] == "A useful bookmark"
    assert count == 1
