from __future__ import annotations

import json

from leeknowledge.db import get_connection
from leeknowledge.intake import import_urls


def test_import_url_persists_raw_archive_and_source_identity(tmp_path):
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "state" / "app.db"

    result = import_urls(
        urls=["HTTPS://Example.com/path?b=2&a=1#frag"],
        raw_output_dir=raw_dir,
        db_path=db_path,
    )

    assert result.archive_path.exists()
    assert result.imported_record_count == 1
    assert result.inserted_record_count == 1
    assert result.quarantined_record_count == 0

    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT tweet_id, source_name, source_type, source_item_id, source_ref, raw_urls FROM bookmarks"
        ).fetchone()

    assert row["source_name"] == "manual"
    assert row["source_type"] == "import_url"
    assert row["source_ref"] == "https://example.com/path?a=1&b=2"
    assert row["tweet_id"] == f"manual:import_url:{row['source_item_id']}"
    assert json.loads(row["raw_urls"]) == ["https://example.com/path?a=1&b=2"]
