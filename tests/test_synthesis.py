from __future__ import annotations

from pathlib import Path

from leeknowledge import cli
from leeknowledge.db import get_connection, initialize_database, insert_bookmark, insert_enrichment
from leeknowledge.exporter import build_bookmark_note_path
from leeknowledge.metadata import generate_leadership_metadata
from leeknowledge.synthesis import SynthesisError, generate_weekly_synthesis
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
        "raw_urls": ["https://t.co/example"],
        "first_seen_at": first_seen_at,
    }


def _enrichment(
    tweet_id: str,
    *,
    summary: str | None = None,
    tags: list[str] | None = None,
    topic: str | None = None,
) -> dict[str, object]:
    return {
        "tweet_id": tweet_id,
        "summary": summary,
        "tags": tags,
        "entities": [],
        "topic": topic,
        "model": "gpt-4o",
        "prompt_version": "1",
        "schema_version": "1",
        "validation_status": "valid",
        "enriched_at": "2026-04-08T09:10:00Z",
    }


def _write_exported_note(vault_dir: Path, row) -> None:
    note_path = build_bookmark_note_path(vault_dir, row)
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(f"bookmark note for {row['tweet_id']}\n")


def test_generate_weekly_synthesis_renders_weekly_note_and_alias(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "7101",
                text="OpenAI launch changes pricing for enterprise copilots.",
                created_at="2026-04-08T10:00:00Z",
                first_seen_at="2026-04-08T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "7101",
                summary="Vendor comparison after the OpenAI launch and pricing change.",
                tags=["pricing", "comparison"],
                topic="vendor landscape",
            ),
        )
        insert_bookmark(
            connection,
            _bookmark(
                "7102",
                text="Agent orchestration needs human-in-the-loop evaluation before rollout.",
                created_at="2026-04-09T11:00:00Z",
                first_seen_at="2026-04-09T11:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "7102",
                summary="Enterprise agents workflow evaluation and deployment guidance.",
                tags=["agent", "workflow"],
                topic="enterprise agents",
            ),
        )
        insert_bookmark(
            connection,
            _bookmark(
                "7103",
                text="Model controls and audit logs matter for regulated agent deployments.",
                created_at="2026-04-10T09:00:00Z",
                first_seen_at="2026-04-10T09:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "7103",
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
    result = generate_weekly_synthesis(
        period_key="2026-W15",
        db_path=db_path,
        vault_dir=vault_dir,
    )

    assert result.period_key == "2026-W15"
    weekly_note = (vault_dir / "synthesis" / "weekly" / "2026" / "2026-W15.md").read_text()
    alias_note = (vault_dir / "briefs" / "latest-weekly-signals.md").read_text()

    assert 'note_type: "leadership_synthesis"' in weekly_note
    assert 'period_key: "2026-W15"' in weekly_note
    assert "## This week's signals" in weekly_note
    assert "## Topic movement" in weekly_note
    assert "## Worth discussing" in weekly_note
    assert "## Source trail" in weekly_note
    assert "[Vendor Landscape](../../../topics/vendor-landscape.md)" in weekly_note
    assert "[Enterprise Agents](../../../topics/enterprise-agents.md)" in weekly_note
    assert "[AI Governance](../../../topics/ai-governance.md)" in weekly_note
    assert "Bookmark note: [Open note](../../../2026/04/openai-launch-changes-pricing-for-enterprise-copilots-7101.md)" in weekly_note
    assert "Source: [View on X](https://x.com/i/web/status/7101)" in weekly_note
    assert "Triage: Strategic · Now · Company Wide" in weekly_note
    assert "Leadership question: Does this change our vendor posture this quarter?" in weekly_note

    assert "# Latest Weekly Signals" in alias_note
    assert "[2026-W15](../synthesis/weekly/2026/2026-W15.md)" in alias_note


def test_generate_weekly_synthesis_handles_empty_weeks_and_refreshes_alias(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    empty_result = generate_weekly_synthesis(
        period_key="2026-W15",
        db_path=db_path,
        vault_dir=vault_dir,
    )

    assert empty_result.bookmark_count == 0
    empty_week_note = (vault_dir / "synthesis" / "weekly" / "2026" / "2026-W15.md").read_text()
    assert "explicit empty week" in empty_week_note
    assert "No Sprint 6 topics were active in this week." in empty_week_note

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "7201",
                text="Semantic layer observability improves data platform handoffs.",
                created_at="2026-04-14T10:00:00Z",
                first_seen_at="2026-04-14T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "7201",
                summary="Data platform note on semantic layer observability.",
                tags=["dbt", "observability"],
                topic="data platform",
            ),
        )
        row = connection.execute("SELECT * FROM bookmarks WHERE tweet_id = ?", ("7201",)).fetchone()

    _write_exported_note(vault_dir, row)
    generate_topic_notes(db_path=db_path, vault_dir=vault_dir)
    generate_weekly_synthesis(period_key="2026-W16", db_path=db_path, vault_dir=vault_dir)

    alias_note = (vault_dir / "briefs" / "latest-weekly-signals.md").read_text()
    assert '[2026-W16](../synthesis/weekly/2026/2026-W16.md)' in alias_note
    assert "2026-W15" not in alias_note


def test_generate_weekly_synthesis_fails_when_topic_note_or_bookmark_note_is_missing(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "7301",
                text="OpenAI launch changes pricing for enterprise copilots.",
                created_at="2026-04-08T10:00:00Z",
                first_seen_at="2026-04-08T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "7301",
                summary="Vendor comparison after the OpenAI launch and pricing change.",
                tags=["pricing", "comparison"],
                topic="vendor landscape",
            ),
        )
        row = connection.execute("SELECT * FROM bookmarks WHERE tweet_id = ?", ("7301",)).fetchone()

    _write_exported_note(vault_dir, row)

    try:
        generate_weekly_synthesis(period_key="2026-W15", db_path=db_path, vault_dir=vault_dir)
    except SynthesisError as exc:
        topic_message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("weekly synthesis should fail when active topic notes are missing")

    assert "Topic note does not exist" in topic_message

    generate_topic_notes(db_path=db_path, vault_dir=vault_dir)
    build_bookmark_note_path(vault_dir, row).unlink()

    try:
        generate_weekly_synthesis(period_key="2026-W15", db_path=db_path, vault_dir=vault_dir)
    except SynthesisError as exc:
        bookmark_message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("weekly synthesis should fail when bookmark notes are missing")

    assert "Bookmark note does not exist" in bookmark_message


def test_generate_weekly_synthesis_fails_when_active_topic_note_is_stale(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "7351",
                text="OpenAI launch changes pricing for enterprise copilots.",
                created_at="2026-04-08T10:00:00Z",
                first_seen_at="2026-04-08T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "7351",
                summary="Vendor comparison after the OpenAI launch and pricing change.",
                tags=["pricing", "comparison"],
                topic="vendor landscape",
            ),
        )
        row = connection.execute("SELECT * FROM bookmarks WHERE tweet_id = ?", ("7351",)).fetchone()

    _write_exported_note(vault_dir, row)
    generate_topic_notes(db_path=db_path, vault_dir=vault_dir)
    _write_exported_note(vault_dir, row)

    try:
        generate_weekly_synthesis(period_key="2026-W15", db_path=db_path, vault_dir=vault_dir)
    except SynthesisError as exc:
        stale_message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("weekly synthesis should fail when active topic notes are stale")

    assert "Topic note is stale" in stale_message


def test_synthesize_cli_runner_calls_generator(tmp_path, monkeypatch):
    calls: list[tuple[object, object, object]] = []

    def fake_generate_weekly_synthesis(**kwargs):
        calls.append((kwargs["period_key"], kwargs["db_path"], kwargs["vault_dir"]))
        return type(
            "SynthesisResult",
            (),
            {
                "period_key": kwargs["period_key"],
                "weekly_note_path": tmp_path / "vault" / "synthesis" / "weekly" / "2026" / "2026-W15.md",
                "latest_alias_path": tmp_path / "vault" / "briefs" / "latest-weekly-signals.md",
                "bookmark_count": 0,
                "cited_bookmark_count": 0,
                "topic_count": 0,
            },
        )()

    monkeypatch.setattr(cli, "generate_weekly_synthesis", fake_generate_weekly_synthesis)

    result = cli.run_synthesize(
        period="2026-W15",
        db_path=tmp_path / "state" / "app.db",
        vault_dir=tmp_path / "vault",
    )

    assert result.period_key == "2026-W15"
    assert calls == [(
        "2026-W15",
        tmp_path / "state" / "app.db",
        tmp_path / "vault",
    )]
