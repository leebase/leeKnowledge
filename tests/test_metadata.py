from __future__ import annotations

from leeknowledge import cli
from leeknowledge.db import (
    get_connection,
    initialize_database,
    insert_bookmark,
    insert_enrichment,
    upsert_leadership_metadata,
)
from leeknowledge.metadata import MetadataError, generate_leadership_metadata


def _bookmark(
    tweet_id: str,
    *,
    text: str,
    created_at: str = "2026-04-08T10:00:00Z",
    first_seen_at: str = "2026-04-08T10:00:00Z",
) -> dict[str, object]:
    return {
        "tweet_id": tweet_id,
        "text": text,
        "author_username": f"user{tweet_id}",
        "author_display_name": f"User {tweet_id}",
        "created_at": created_at,
        "conversation_id": tweet_id,
        "in_reply_to_id": None,
        "media_urls": [],
        "raw_urls": ["https://example.com/article"],
        "first_seen_at": first_seen_at,
    }


def _enrichment(
    tweet_id: str,
    *,
    summary: str,
    tags: list[str] | None = None,
    topic: str,
    validation_status: str = "valid",
) -> dict[str, object]:
    return {
        "tweet_id": tweet_id,
        "summary": summary,
        "tags": tags or [],
        "entities": [],
        "topic": topic,
        "model": "gpt-4o",
        "prompt_version": "1",
        "schema_version": "1",
        "validation_status": validation_status,
        "enriched_at": "2026-04-08T10:05:00Z",
    }


def test_generate_leadership_metadata_persists_triage_fields_and_skips_current_rows(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "8101",
                text="OpenAI launch changes pricing for enterprise copilots this quarter.",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "8101",
                summary="Vendor comparison after the OpenAI launch and pricing change.",
                tags=["pricing", "comparison"],
                topic="vendor landscape",
            ),
        )
        insert_bookmark(
            connection,
            _bookmark(
                "8102",
                text="A small team process note about personal reading workflow.",
                first_seen_at="2026-04-08T11:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "8102",
                summary="Workflow note for one team backlog.",
                tags=["workflow"],
                topic="operations",
            ),
        )

    result = generate_leadership_metadata(db_path=db_path)

    assert result.processed_bookmark_count == 2
    assert result.inserted_metadata_count == 2
    assert result.skipped_existing_count == 0

    with get_connection(db_path) as connection:
        vendor_row = connection.execute(
            """
            SELECT strategic_relevance, time_horizon, organizational_impact,
                   leadership_question, validation_status
            FROM leadership_metadata
            WHERE tweet_id = ?
            """,
            ("8101",),
        ).fetchone()
        workflow_row = connection.execute(
            """
            SELECT strategic_relevance, time_horizon, organizational_impact,
                   leadership_question, validation_status
            FROM leadership_metadata
            WHERE tweet_id = ?
            """,
            ("8102",),
        ).fetchone()

    assert vendor_row["strategic_relevance"] in {"important", "strategic"}
    assert vendor_row["time_horizon"] == "now"
    assert vendor_row["organizational_impact"] == "company-wide"
    assert vendor_row["leadership_question"] == "Does this change our vendor posture this quarter?"
    assert vendor_row["validation_status"] == "valid"

    assert workflow_row["strategic_relevance"] in {"monitor", "important"}
    assert workflow_row["validation_status"] == "valid"

    rerun = generate_leadership_metadata(db_path=db_path)
    assert rerun.processed_bookmark_count == 0
    assert rerun.inserted_metadata_count == 0
    assert rerun.skipped_existing_count == 2


def test_generate_leadership_metadata_writes_placeholder_for_invalid_enrichment_rows(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "8201",
                text="Governance note awaiting a better enrichment pass.",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "8201",
                summary="placeholder",
                tags=["risk"],
                topic="ai governance",
                validation_status="invalid_json",
            ),
        )

    result = generate_leadership_metadata(db_path=db_path)

    assert result.processed_bookmark_count == 1
    assert result.inserted_metadata_count == 1

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT strategic_relevance, time_horizon, organizational_impact,
                   leadership_question, validation_status
            FROM leadership_metadata
            WHERE tweet_id = ?
            """,
            ("8201",),
        ).fetchone()

    assert row["strategic_relevance"] is None
    assert row["time_horizon"] is None
    assert row["organizational_impact"] is None
    assert row["leadership_question"] is None
    assert row["validation_status"] == "blocked_enrichment_invalid"


def test_generate_leadership_metadata_replaces_stale_versions(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "8301",
                text="Policy and compliance controls matter for regulated deployments.",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "8301",
                summary="AI governance checklist for regulated deployments.",
                tags=["policy", "risk"],
                topic="AI governance",
            ),
        )
        upsert_leadership_metadata(
            connection,
            {
                "tweet_id": "8301",
                "strategic_relevance": "monitor",
                "time_horizon": "longer-term",
                "organizational_impact": "team",
                "leadership_question": None,
                "model": "old-rules",
                "prompt_version": "0",
                "schema_version": "0",
                "validation_status": "valid",
                "generated_at": "2026-04-01T00:00:00Z",
            },
        )

    result = generate_leadership_metadata(db_path=db_path)
    assert result.processed_bookmark_count == 1
    assert result.inserted_metadata_count == 1

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT strategic_relevance, time_horizon, organizational_impact,
                   leadership_question, prompt_version, schema_version
            FROM leadership_metadata
            WHERE tweet_id = ?
            """,
            ("8301",),
        ).fetchone()

    assert row["strategic_relevance"] == "strategic"
    assert row["time_horizon"] == "now"
    assert row["organizational_impact"] == "company-wide"
    assert row["leadership_question"] == "What guardrails or controls should we tighten now?"
    assert row["prompt_version"] == "1"
    assert row["schema_version"] == "1"


def test_generate_leadership_metadata_counts_placeholder_rows_for_generation_failures(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "state" / "app.db"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "8401",
                text="This row should force a metadata-generation failure.",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "8401",
                summary="Failure-path coverage for metadata generation.",
                topic="vendor landscape",
            ),
        )

    def fake_build_metadata_record(row):
        raise RuntimeError("boom")

    monkeypatch.setattr("leeknowledge.metadata._build_metadata_record", fake_build_metadata_record)

    result = generate_leadership_metadata(db_path=db_path)

    assert result.processed_bookmark_count == 1
    assert result.inserted_metadata_count == 1
    assert result.placeholder_count == 1
    assert result.failed_bookmark_count == 1

    with get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT strategic_relevance, time_horizon, organizational_impact,
                   leadership_question, validation_status
            FROM leadership_metadata
            WHERE tweet_id = ?
            """,
            ("8401",),
        ).fetchone()

    assert row["strategic_relevance"] is None
    assert row["time_horizon"] is None
    assert row["organizational_impact"] is None
    assert row["leadership_question"] is None
    assert row["validation_status"] == "error:RuntimeError"


def test_generate_leadership_metadata_fails_for_missing_db_path(tmp_path):
    db_path = tmp_path / "state" / "missing.db"

    try:
        generate_leadership_metadata(db_path=db_path)
    except MetadataError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("metadata generation should fail for a missing SQLite path")

    assert "SQLite database does not exist" in message
    assert not db_path.exists()


def test_metadata_cli_runner_calls_generator(tmp_path, monkeypatch):
    calls: list[object] = []

    def fake_generate_leadership_metadata(**kwargs):
        calls.append(kwargs["db_path"])
        return type(
            "MetadataResult",
            (),
            {
                "processed_bookmark_count": 0,
                "inserted_metadata_count": 0,
                "skipped_existing_count": 0,
                "placeholder_count": 0,
                "failed_bookmark_count": 0,
            },
        )()

    monkeypatch.setattr(cli, "generate_leadership_metadata", fake_generate_leadership_metadata)

    result = cli.run_metadata(db_path=tmp_path / "state" / "app.db")

    assert result.inserted_metadata_count == 0
    assert calls == [tmp_path / "state" / "app.db"]
