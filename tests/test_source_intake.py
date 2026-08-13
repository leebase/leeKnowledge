from __future__ import annotations

from leeknowledge.db import get_connection
from leeknowledge.intake import canonicalize_url


def test_export_supports_non_x_source_links(tmp_path):
    from leeknowledge.db import initialize_database, insert_bookmark
    from leeknowledge.exporter import export_markdown

    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)
    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            {
                "tweet_id": "manual:import_url:abc123",
                "source_name": "manual",
                "source_type": "import_url",
                "source_item_id": "abc123",
                "source_ref": "https://example.com/source",
                "text": "Imported note",
                "author_username": None,
                "author_display_name": None,
                "created_at": None,
                "conversation_id": None,
                "in_reply_to_id": None,
                "media_urls": [],
                "raw_urls": ["https://example.com/source"],
                "first_seen_at": "2026-04-08T12:00:00Z",
            },
        )

    result = export_markdown(db_path=db_path, vault_dir=vault_dir)
    note_text = result.written_paths[0].read_text(encoding="utf-8")

    assert 'source_name: "manual"' in note_text
    assert 'source_type: "import_url"' in note_text
    assert 'source_ref: "https://example.com/source"' in note_text
    assert "[View source](https://example.com/source)" in note_text
    assert "View on X" not in note_text


def test_canonicalize_url_normalizes_case_query_and_fragment():
    assert canonicalize_url("HTTPS://Example.com?a=2&b=1#frag") == "https://example.com/?a=2&b=1"
    assert canonicalize_url("not-a-url") is None
