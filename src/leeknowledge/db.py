"""
SQLite bootstrap helpers for leeKnowledge.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

APP_DB_PATH = Path("state/app.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookmarks (
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
);

CREATE TABLE IF NOT EXISTS enrichments (
    tweet_id TEXT PRIMARY KEY,
    summary TEXT,
    tags TEXT,
    entities TEXT,
    topic TEXT,
    model TEXT,
    enriched_at TIMESTAMP,
    FOREIGN KEY (tweet_id) REFERENCES bookmarks(tweet_id)
);

CREATE TABLE IF NOT EXISTS url_cache (
    original_url TEXT PRIMARY KEY,
    resolved_url TEXT,
    page_title TEXT,
    page_description TEXT,
    cached_at TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS bookmarks_fts USING fts5(
    tweet_id,
    text,
    author_username,
    content='bookmarks',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS bookmarks_ai AFTER INSERT ON bookmarks BEGIN
    INSERT INTO bookmarks_fts(rowid, tweet_id, text, author_username)
    VALUES (new.rowid, new.tweet_id, new.text, new.author_username);
END;

CREATE TRIGGER IF NOT EXISTS bookmarks_ad AFTER DELETE ON bookmarks BEGIN
    INSERT INTO bookmarks_fts(bookmarks_fts, rowid, tweet_id, text, author_username)
    VALUES ('delete', old.rowid, old.tweet_id, old.text, old.author_username);
END;

CREATE TRIGGER IF NOT EXISTS bookmarks_au AFTER UPDATE ON bookmarks BEGIN
    INSERT INTO bookmarks_fts(bookmarks_fts, rowid, tweet_id, text, author_username)
    VALUES ('delete', old.rowid, old.tweet_id, old.text, old.author_username);
    INSERT INTO bookmarks_fts(rowid, tweet_id, text, author_username)
    VALUES (new.rowid, new.tweet_id, new.text, new.author_username);
END;
"""


def get_connection(db_path: Path | str = APP_DB_PATH) -> sqlite3.Connection:
    """Return a SQLite connection with row access enabled."""
    resolved_path = Path(db_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(db_path: Path | str = APP_DB_PATH) -> Path:
    """Create the database file and required tables if needed."""
    resolved_path = Path(db_path)
    with get_connection(resolved_path) as connection:
        connection.executescript(SCHEMA)
        connection.commit()
    return resolved_path


def insert_bookmark(
    connection: sqlite3.Connection,
    bookmark: Mapping[str, Any],
) -> bool:
    """Insert a bookmark record, ignoring duplicates by tweet ID."""
    payload = {
        "tweet_id": bookmark["tweet_id"],
        "text": bookmark["text"],
        "author_username": bookmark.get("author_username"),
        "author_display_name": bookmark.get("author_display_name"),
        "created_at": bookmark.get("created_at"),
        "conversation_id": bookmark.get("conversation_id"),
        "in_reply_to_id": bookmark.get("in_reply_to_id"),
        "media_urls": _to_json(bookmark.get("media_urls", [])),
        "raw_urls": _to_json(bookmark.get("raw_urls", [])),
        "first_seen_at": bookmark["first_seen_at"],
    }
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO bookmarks (
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
        ) VALUES (
            :tweet_id,
            :text,
            :author_username,
            :author_display_name,
            :created_at,
            :conversation_id,
            :in_reply_to_id,
            :media_urls,
            :raw_urls,
            :first_seen_at
        )
        """,
        payload,
    )
    connection.commit()
    return cursor.rowcount == 1


def _to_json(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)
