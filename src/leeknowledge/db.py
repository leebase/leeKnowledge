"""
SQLite bootstrap helpers for leeKnowledge.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

APP_DB_PATH = Path("state/app.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookmarks (
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
);

CREATE TABLE IF NOT EXISTS enrichments (
    tweet_id TEXT PRIMARY KEY,
    summary TEXT,
    tags TEXT,
    entities TEXT,
    topic TEXT,
    model TEXT,
    prompt_version TEXT,
    schema_version TEXT,
    validation_status TEXT,
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

CREATE TABLE IF NOT EXISTS leadership_metadata (
    tweet_id TEXT PRIMARY KEY,
    strategic_relevance TEXT,
    time_horizon TEXT,
    organizational_impact TEXT,
    leadership_question TEXT,
    model TEXT,
    prompt_version TEXT,
    schema_version TEXT,
    validation_status TEXT,
    generated_at TIMESTAMP,
    FOREIGN KEY (tweet_id) REFERENCES bookmarks(tweet_id)
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

BOOKMARK_COLUMNS = {
    "source_name": "TEXT",
    "source_type": "TEXT",
    "source_item_id": "TEXT",
    "source_ref": "TEXT",
}

ENRICHMENT_COLUMNS = {
    "prompt_version": "TEXT",
    "schema_version": "TEXT",
    "validation_status": "TEXT",
}

LEADERSHIP_METADATA_COLUMNS = {
    "strategic_relevance": "TEXT",
    "time_horizon": "TEXT",
    "organizational_impact": "TEXT",
    "leadership_question": "TEXT",
    "model": "TEXT",
    "prompt_version": "TEXT",
    "schema_version": "TEXT",
    "validation_status": "TEXT",
    "generated_at": "TIMESTAMP",
}


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
        _migrate_bookmarks_table(connection)
        _migrate_enrichments_table(connection)
        _migrate_leadership_metadata_table(connection)
        _ensure_bookmark_indexes(connection)
        connection.commit()
    return resolved_path


def insert_bookmark(
    connection: sqlite3.Connection,
    bookmark: Mapping[str, Any],
) -> bool:
    """Insert a bookmark record, ignoring duplicates by tweet ID."""
    source_name = str(bookmark.get("source_name") or "x")
    source_type = str(bookmark.get("source_type") or "x_bookmark")
    source_item_id = str(bookmark.get("source_item_id") or bookmark["tweet_id"])
    payload = {
        "tweet_id": bookmark["tweet_id"],
        "source_name": source_name,
        "source_type": source_type,
        "source_item_id": source_item_id,
        "source_ref": bookmark.get("source_ref") or _default_source_ref(source_name, bookmark["tweet_id"]),
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
        ) VALUES (
            :tweet_id,
            :source_name,
            :source_type,
            :source_item_id,
            :source_ref,
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


def insert_enrichment(
    connection: sqlite3.Connection,
    enrichment: Mapping[str, Any],
) -> bool:
    """Insert a single enrichment row, leaving existing history untouched."""
    payload = {
        "tweet_id": enrichment["tweet_id"],
        "summary": enrichment.get("summary"),
        "tags": _to_json_or_none(enrichment.get("tags")),
        "entities": _to_json_or_none(enrichment.get("entities")),
        "topic": enrichment.get("topic"),
        "model": enrichment.get("model"),
        "prompt_version": enrichment.get("prompt_version"),
        "schema_version": enrichment.get("schema_version"),
        "validation_status": enrichment.get("validation_status"),
        "enriched_at": enrichment.get("enriched_at"),
    }
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO enrichments (
            tweet_id,
            summary,
            tags,
            entities,
            topic,
            model,
            prompt_version,
            schema_version,
            validation_status,
            enriched_at
        ) VALUES (
            :tweet_id,
            :summary,
            :tags,
            :entities,
            :topic,
            :model,
            :prompt_version,
            :schema_version,
            :validation_status,
            :enriched_at
        )
        """,
        payload,
    )
    connection.commit()
    return cursor.rowcount == 1


def upsert_url_cache(
    connection: sqlite3.Connection,
    url_entry: Mapping[str, Any],
) -> None:
    """Store a resolved URL mapping for replayable enrichment."""
    payload = {
        "original_url": url_entry["original_url"],
        "resolved_url": url_entry.get("resolved_url"),
        "page_title": url_entry.get("page_title"),
        "page_description": url_entry.get("page_description"),
        "cached_at": url_entry.get("cached_at"),
    }
    connection.execute(
        """
        INSERT INTO url_cache (
            original_url,
            resolved_url,
            page_title,
            page_description,
            cached_at
        ) VALUES (
            :original_url,
            :resolved_url,
            :page_title,
            :page_description,
            :cached_at
        )
        ON CONFLICT(original_url) DO UPDATE SET
            resolved_url = excluded.resolved_url,
            page_title = excluded.page_title,
            page_description = excluded.page_description,
            cached_at = excluded.cached_at
        """,
        payload,
    )
    connection.commit()


def get_url_cache_entry(
    connection: sqlite3.Connection,
    original_url: str,
) -> sqlite3.Row | None:
    """Return a cached URL resolution when available."""
    return connection.execute(
        """
        SELECT original_url, resolved_url, page_title, page_description, cached_at
        FROM url_cache
        WHERE original_url = ?
        """,
        (original_url,),
    ).fetchone()


def upsert_leadership_metadata(
    connection: sqlite3.Connection,
    metadata_row: Mapping[str, Any],
) -> None:
    """Store one current leadership metadata row per tweet ID."""
    payload = {
        "tweet_id": metadata_row["tweet_id"],
        "strategic_relevance": metadata_row.get("strategic_relevance"),
        "time_horizon": metadata_row.get("time_horizon"),
        "organizational_impact": metadata_row.get("organizational_impact"),
        "leadership_question": metadata_row.get("leadership_question"),
        "model": metadata_row.get("model"),
        "prompt_version": metadata_row.get("prompt_version"),
        "schema_version": metadata_row.get("schema_version"),
        "validation_status": metadata_row.get("validation_status"),
        "generated_at": metadata_row.get("generated_at"),
    }
    connection.execute(
        """
        INSERT INTO leadership_metadata (
            tweet_id,
            strategic_relevance,
            time_horizon,
            organizational_impact,
            leadership_question,
            model,
            prompt_version,
            schema_version,
            validation_status,
            generated_at
        ) VALUES (
            :tweet_id,
            :strategic_relevance,
            :time_horizon,
            :organizational_impact,
            :leadership_question,
            :model,
            :prompt_version,
            :schema_version,
            :validation_status,
            :generated_at
        )
        ON CONFLICT(tweet_id) DO UPDATE SET
            strategic_relevance = excluded.strategic_relevance,
            time_horizon = excluded.time_horizon,
            organizational_impact = excluded.organizational_impact,
            leadership_question = excluded.leadership_question,
            model = excluded.model,
            prompt_version = excluded.prompt_version,
            schema_version = excluded.schema_version,
            validation_status = excluded.validation_status,
            generated_at = excluded.generated_at
        """,
        payload,
    )
    connection.commit()


def list_unenriched_bookmarks(
    connection: sqlite3.Connection,
) -> list[sqlite3.Row]:
    """Return bookmarks that do not already have an enrichment row."""
    return connection.execute(
        """
        SELECT b.*
        FROM bookmarks AS b
        LEFT JOIN enrichments AS e ON e.tweet_id = b.tweet_id
        WHERE e.tweet_id IS NULL
        ORDER BY b.first_seen_at, b.tweet_id
        """
    ).fetchall()


def _migrate_bookmarks_table(connection: sqlite3.Connection) -> None:
    existing_columns = {row[1] for row in connection.execute("PRAGMA table_info(bookmarks)")}
    for column, column_type in BOOKMARK_COLUMNS.items():
        if column not in existing_columns:
            connection.execute(
                f"ALTER TABLE bookmarks ADD COLUMN {column} {column_type}"
            )

    connection.execute(
        "UPDATE bookmarks SET source_name = 'x' WHERE source_name IS NULL OR source_name = ''"
    )
    connection.execute(
        "UPDATE bookmarks SET source_type = 'x_bookmark' WHERE source_type IS NULL OR source_type = ''"
    )
    connection.execute(
        "UPDATE bookmarks SET source_item_id = tweet_id WHERE source_item_id IS NULL OR source_item_id = ''"
    )
    connection.execute(
        "UPDATE bookmarks SET source_ref = 'https://x.com/i/web/status/' || tweet_id WHERE (source_ref IS NULL OR source_ref = '') AND source_name = 'x' AND tweet_id IS NOT NULL"
    )


def _migrate_enrichments_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(enrichments)")
    }
    for column, column_type in ENRICHMENT_COLUMNS.items():
        if column not in existing_columns:
            connection.execute(
                f"ALTER TABLE enrichments ADD COLUMN {column} {column_type}"
            )


def _migrate_leadership_metadata_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS leadership_metadata (
            tweet_id TEXT PRIMARY KEY,
            strategic_relevance TEXT,
            time_horizon TEXT,
            organizational_impact TEXT,
            leadership_question TEXT,
            model TEXT,
            prompt_version TEXT,
            schema_version TEXT,
            validation_status TEXT,
            generated_at TIMESTAMP,
            FOREIGN KEY (tweet_id) REFERENCES bookmarks(tweet_id)
        )
        """
    )
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(leadership_metadata)")
    }
    for column, column_type in LEADERSHIP_METADATA_COLUMNS.items():
        if column not in existing_columns:
            connection.execute(
                f"ALTER TABLE leadership_metadata ADD COLUMN {column} {column_type}"
            )


def _ensure_bookmark_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bookmarks_source_identity
        ON bookmarks(source_name, source_type, source_item_id)
        """
    )


def _default_source_ref(source_name: str, tweet_id: Any) -> str | None:
    if source_name == "x" and tweet_id not in (None, ""):
        return f"https://x.com/i/web/status/{tweet_id}"
    return None


def _to_json(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _to_json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)
