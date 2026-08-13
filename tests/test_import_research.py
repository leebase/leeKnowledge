from __future__ import annotations

import csv
import json

from leeknowledge.db import get_connection
from leeknowledge.intake import import_research_artifact


def test_import_research_artifact_imports_valid_rows_and_quarantines_invalid_ones(tmp_path):
    raw_dir = tmp_path / "raw"
    db_path = tmp_path / "state" / "app.db"
    research_path = tmp_path / "research.csv"
    with research_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["title", "summary", "url"])
        writer.writeheader()
        writer.writerow(
            {
                "title": "Research note",
                "summary": "Useful summary",
                "url": "https://example.com/research",
            }
        )
        writer.writerow({"title": "", "summary": "", "url": ""})

    result = import_research_artifact(
        input_path=research_path,
        raw_output_dir=raw_dir,
        db_path=db_path,
    )

    assert result.archive_path.exists()
    assert result.imported_record_count == 1
    assert result.inserted_record_count == 1
    assert result.quarantined_record_count == 1

    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT source_name, source_type, source_ref, text, raw_urls FROM bookmarks"
        ).fetchone()

    assert row["source_name"] == "research"
    assert row["source_type"] == "artifact_item"
    assert row["source_ref"] == "https://example.com/research"
    assert "Research note" in row["text"]
    assert json.loads(row["raw_urls"]) == ["https://example.com/research"]
