from __future__ import annotations

import textwrap
from pathlib import Path

from leeknowledge import cli
from leeknowledge.collections import (
    CollectionGenerationError,
    generate_collection_notes,
    load_collection_definitions,
)
from leeknowledge.db import get_connection, initialize_database, insert_bookmark, insert_enrichment
from leeknowledge.exporter import build_bookmark_note_path
from leeknowledge.metadata import generate_leadership_metadata
from leeknowledge.synthesis import generate_weekly_synthesis
from leeknowledge.topics import generate_topic_notes


def _bookmark(
    tweet_id: str,
    *,
    text: str,
    created_at: str,
    first_seen_at: str,
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
        "validation_status": "valid",
        "enriched_at": "2026-04-08T10:05:00Z",
    }


def _write_exported_note(vault_dir: Path, row) -> None:
    note_path = build_bookmark_note_path(vault_dir, row)
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(f"bookmark note for {row['tweet_id']}\n")


def _write_definitions(path: Path) -> Path:
    path.write_text(
        textwrap.dedent(
            """
            collections:
              - initiative_slug: ai-operating-model
                title: AI Operating Model
                status: active
                leadership_question: What external signals should shape our AI operating model this quarter?
                scope_note: Governance and agent-delivery signals for operating-model choices.
                topic_keys:
                  - ai-governance
                  - enterprise-agents
                metadata_preferences:
                  strategic_relevance:
                    - strategic
                    - important
                  time_horizon:
                    - now
                    - next-quarter
                include_tags_any:
                  - policy
                  - workflow
                source_window_days: 365
                max_items: 2
                weekly_priority: true
                description: Curated evidence for AI operating-model decisions.

              - initiative_slug: empty-watchlist
                title: Empty Watchlist
                status: watching
                leadership_question: What are we still missing?
                scope_note: Intentionally narrow definition to confirm empty-state rendering.
                topic_keys: []
                metadata_preferences:
                  strategic_relevance:
                    - strategic
                include_tags_any:
                  - partnership
                source_window_days: 30
                max_items: 3
                weekly_priority: false
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def test_load_collection_definitions_validates_allowed_values(tmp_path):
    definitions_path = tmp_path / "collections.yaml"
    definitions_path.write_text(
        textwrap.dedent(
            """
            collections:
              - initiative_slug: not_kebab
                title: Broken
                status: active-now
                leadership_question: Broken question
                scope_note: Broken scope
                max_items: 20
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

    try:
        load_collection_definitions(definitions_path)
    except CollectionGenerationError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("invalid definitions should fail validation")

    assert "initiative_slug" in message or "status" in message


def test_generate_collection_notes_renders_related_views_reasons_and_empty_state(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    definitions_path = _write_definitions(tmp_path / "curated-collections.yaml")
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "9101",
                text="OpenAI launch changes pricing for enterprise copilots this quarter.",
                created_at="2026-04-08T10:00:00Z",
                first_seen_at="2026-04-08T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "9101",
                summary="Vendor comparison after the OpenAI launch and pricing change.",
                tags=["pricing", "comparison"],
                topic="vendor landscape",
            ),
        )
        insert_bookmark(
            connection,
            _bookmark(
                "9102",
                text="Agent orchestration needs human-in-the-loop evaluation before rollout.",
                created_at="2026-04-09T11:00:00Z",
                first_seen_at="2026-04-09T11:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "9102",
                summary="Enterprise agents workflow evaluation and deployment guidance.",
                tags=["workflow", "automation"],
                topic="enterprise agents",
            ),
        )
        insert_bookmark(
            connection,
            _bookmark(
                "9103",
                text="Model controls and audit logs matter for regulated agent deployments.",
                created_at="2026-04-10T09:00:00Z",
                first_seen_at="2026-04-10T09:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "9103",
                summary="AI governance checklist for regulated deployments.",
                tags=["policy", "risk"],
                topic="AI governance",
            ),
        )
        rows = connection.execute("SELECT * FROM bookmarks ORDER BY tweet_id").fetchall()

    for row in rows:
        _write_exported_note(vault_dir, row)

    generate_topic_notes(db_path=db_path, vault_dir=vault_dir)
    generate_leadership_metadata(db_path=db_path)
    generate_weekly_synthesis(period_key="2026-W15", db_path=db_path, vault_dir=vault_dir)

    result = generate_collection_notes(
        db_path=db_path,
        vault_dir=vault_dir,
        definitions_path=definitions_path,
    )

    assert result.generated_note_count == 2

    operating_model_note = (vault_dir / "collections" / "ai-operating-model.md").read_text()
    assert 'note_type: "curated_collection"' in operating_model_note
    assert 'initiative_slug: "ai-operating-model"' in operating_model_note
    assert "## Leadership question" in operating_model_note
    assert "## Related views" in operating_model_note
    assert "## Current evidence" in operating_model_note
    assert "## Generation notes" in operating_model_note
    assert "Topic note: [AI Governance](../topics/ai-governance.md)" in operating_model_note
    assert "Weekly brief: [2026-W15](../synthesis/weekly/2026/2026-W15.md)" in operating_model_note
    assert "Inclusion reasons:" in operating_model_note
    assert "topic match: AI Governance" in operating_model_note or "topic match: Enterprise Agents" in operating_model_note
    assert "metadata fit: Strategic · Now · Company Wide" in operating_model_note
    assert "Bookmark note: [Open note](../2026/04/model-controls-and-audit-logs-matter-for-regulated-agent-deployments-9103.md)" in operating_model_note
    assert "Source: [View on X](https://x.com/i/web/status/9103)" in operating_model_note
    assert "Triage: Strategic · Now · Company Wide" in operating_model_note
    assert "Leadership question: What guardrails or controls should we tighten now?" in operating_model_note
    assert operating_model_note.count("- 2026-04-") == 2
    assert "openai-launch-changes-pricing" not in operating_model_note

    empty_note = (vault_dir / "collections" / "empty-watchlist.md").read_text()
    assert "No current evidence met the initiative definition" in empty_note
    assert "What are we still missing?" in empty_note

    index_note = (vault_dir / "collections" / "index.md").read_text()
    assert 'note_type: "collection_index"' in index_note
    assert "# Curated Collections" in index_note
    assert "[AI Operating Model](ai-operating-model.md)" in index_note
    assert "[Empty Watchlist](empty-watchlist.md)" in index_note
    assert "Leadership question: What external signals should shape our AI operating model this quarter?" in index_note

    rerun = generate_collection_notes(
        db_path=db_path,
        vault_dir=vault_dir,
        definitions_path=definitions_path,
    )
    assert rerun.written_paths == result.written_paths


def test_generate_collection_notes_fails_when_selected_bookmark_note_is_missing(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    definitions_path = _write_definitions(tmp_path / "curated-collections.yaml")
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "9201",
                text="Policy and compliance controls matter for regulated deployments.",
                created_at="2026-04-08T10:00:00Z",
                first_seen_at="2026-04-08T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "9201",
                summary="AI governance checklist for regulated deployments.",
                tags=["policy", "risk"],
                topic="AI governance",
            ),
        )

    generate_leadership_metadata(db_path=db_path)

    try:
        generate_collection_notes(
            db_path=db_path,
            vault_dir=vault_dir,
            definitions_path=definitions_path,
        )
    except CollectionGenerationError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("collections should fail when selected bookmark notes are missing")

    assert "Bookmark note does not exist" in message


def test_cli_collections_command_generates_notes(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    definitions_path = _write_definitions(tmp_path / "curated-collections.yaml")
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "9301",
                text="Model controls and audit logs matter for regulated agent deployments.",
                created_at="2026-04-10T09:00:00Z",
                first_seen_at="2026-04-10T09:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "9301",
                summary="AI governance checklist for regulated deployments.",
                tags=["policy", "risk"],
                topic="AI governance",
            ),
        )
        row = connection.execute("SELECT * FROM bookmarks WHERE tweet_id = ?", ("9301",)).fetchone()

    _write_exported_note(vault_dir, row)
    generate_topic_notes(db_path=db_path, vault_dir=vault_dir)
    generate_leadership_metadata(db_path=db_path)

    monkeypatch.setattr(
        "sys.argv",
        [
            "leeknowledge",
            "collections",
            "--db-path",
            str(db_path),
            "--vault-dir",
            str(vault_dir),
            "--definitions-path",
            str(definitions_path),
        ],
    )

    try:
        cli.main()
    except SystemExit as exc:
        assert exc.code == 0
    captured = capsys.readouterr()

    assert "Generated 2 curated collection notes" in captured.out
    assert (vault_dir / "collections" / "ai-operating-model.md").exists()


def test_generate_collection_notes_excludes_weekly_only_candidates(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    definitions_path = _write_definitions(tmp_path / "curated-collections.yaml")
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "9401",
                text="Vendor pricing move changes enterprise AI buying patterns.",
                created_at="2026-04-08T10:00:00Z",
                first_seen_at="2026-04-08T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "9401",
                summary="Vendor comparison after the OpenAI pricing move.",
                tags=["pricing", "comparison"],
                topic="vendor landscape",
            ),
        )
        insert_bookmark(
            connection,
            _bookmark(
                "9402",
                text="General leadership roundup with no operating-model framing.",
                created_at="2026-04-09T11:00:00Z",
                first_seen_at="2026-04-09T11:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "9402",
                summary="General leadership roundup.",
                tags=["strategy"],
                topic="data platform",
            ),
        )
        rows = connection.execute("SELECT * FROM bookmarks ORDER BY tweet_id").fetchall()

    for row in rows:
        _write_exported_note(vault_dir, row)

    generate_topic_notes(db_path=db_path, vault_dir=vault_dir)
    generate_leadership_metadata(db_path=db_path)
    generate_weekly_synthesis(period_key="2026-W15", db_path=db_path, vault_dir=vault_dir)
    generate_collection_notes(
        db_path=db_path,
        vault_dir=vault_dir,
        definitions_path=definitions_path,
    )

    note = (vault_dir / "collections" / "ai-operating-model.md").read_text()
    assert "9402" not in note
    assert "general-leadership-roundup" not in note
    assert "9401" not in note
    assert "vendor-pricing-move-changes-enterprise-ai-buying-patterns" not in note
