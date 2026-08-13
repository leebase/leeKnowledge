from __future__ import annotations

import plistlib

from leeknowledge.db import get_connection
from leeknowledge.intake import import_safari_bookmarks


def test_import_safari_bookmarks_quarantines_missing_folder_lineage(tmp_path):
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "state" / "app.db"
    safari_path = tmp_path / "Bookmarks.plist"
    safari_payload = {
        "Children": [
            {
                "Title": "Leadership",
                "Children": [
                    {
                        "WebBookmarkType": "WebBookmarkTypeLeaf",
                        "URLString": "https://example.com/leadership",
                        "URIDictionary": {"title": "Leadership article"},
                    }
                ],
            },
            {
                "WebBookmarkType": "WebBookmarkTypeLeaf",
                "URLString": "https://example.com/root-only",
                "URIDictionary": {"title": "Root only"},
            },
        ]
    }
    with safari_path.open("wb") as handle:
        plistlib.dump(safari_payload, handle)

    result = import_safari_bookmarks(
        input_path=safari_path,
        raw_output_dir=raw_dir,
        db_path=db_path,
    )

    assert result.archive_path.exists()
    assert result.imported_record_count == 1
    assert result.inserted_record_count == 1
    assert result.quarantined_record_count == 1
    assert result.quarantine_path is not None and result.quarantine_path.exists()

    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT source_name, source_type, source_ref, text FROM bookmarks"
        ).fetchone()

    assert row["source_name"] == "safari"
    assert row["source_type"] == "bookmark_export"
    assert row["source_ref"] == "https://example.com/leadership"
    assert row["text"] == "Leadership article"
