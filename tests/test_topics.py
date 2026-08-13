from __future__ import annotations

from leeknowledge import cli
from leeknowledge.db import get_connection, initialize_database, insert_bookmark, insert_enrichment
from leeknowledge.exporter import build_bookmark_note_path
from leeknowledge.topics import TOPIC_DEFINITIONS, TopicGenerationError, assign_topics, generate_topic_notes


def _bookmark(tweet_id: str, *, text: str, first_seen_at: str) -> dict[str, object]:
    return {
        "tweet_id": tweet_id,
        "text": text,
        "author_username": f"user{tweet_id}",
        "author_display_name": f"User {tweet_id}",
        "created_at": None,
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


def test_assign_topics_uses_structured_and_fallback_signals():
    governance_row = {
        "tweet_id": "g1",
        "text": "Agent rollout needs stronger safety guardrails and audit policy",
        "summary": "Governance checklist for enterprise agent evaluation",
        "tags": '["policy", "risk"]',
        "topic": "AI governance",
        "raw_urls": '["https://t.co/example"]',
        "author_username": "lee",
        "author_display_name": "Lee",
        "created_at": None,
        "first_seen_at": "2026-04-08T09:00:00Z",
    }
    weak_agent_row = {
        "tweet_id": "a1",
        "text": "One agent mention should stay uncategorized",
        "summary": None,
        "tags": None,
        "topic": None,
        "raw_urls": '["https://t.co/example"]',
        "author_username": "lee",
        "author_display_name": "Lee",
        "created_at": None,
        "first_seen_at": "2026-04-08T09:00:00Z",
    }
    vendor_row = {
        "tweet_id": "v1",
        "text": "OpenAI launch changes pricing for enterprise buyers",
        "summary": "Vendor comparison after the OpenAI launch",
        "tags": '["pricing"]',
        "topic": None,
        "raw_urls": '["https://openai.com/blog/pricing"]',
        "author_username": "lee",
        "author_display_name": "Lee",
        "created_at": None,
        "first_seen_at": "2026-04-08T09:00:00Z",
    }

    governance_matches = assign_topics(governance_row)
    assert "ai-governance" in governance_matches
    assert "enterprise-agents" in governance_matches
    assert any("topic=AI governance" == signal for signal in governance_matches["ai-governance"])

    assert assign_topics(weak_agent_row) == {}

    vendor_matches = assign_topics(vendor_row)
    assert set(vendor_matches) == {"vendor-landscape"}
    assert any("url signals=openai" == signal for signal in vendor_matches["vendor-landscape"])

    evaluation_only_row = {
        "tweet_id": "e1",
        "text": "Workflow evaluation matters for enterprise rollout",
        "summary": "Evaluation checklist for agent deployment",
        "tags": None,
        "topic": None,
        "raw_urls": '[]',
        "author_username": "lee",
        "author_display_name": "Lee",
        "created_at": None,
        "first_seen_at": "2026-04-08T09:00:00Z",
    }
    assert "ai-governance" not in assign_topics(evaluation_only_row)

    enterprise_only_row = {
        "tweet_id": "e2",
        "text": "OpenAI pricing update for enterprise buyers",
        "summary": "OpenAI launch shifts enterprise buying conversations",
        "tags": '["pricing"]',
        "topic": None,
        "raw_urls": '["https://openai.com/pricing"]',
        "author_username": "lee",
        "author_display_name": "Lee",
        "created_at": None,
        "first_seen_at": "2026-04-08T09:00:00Z",
    }
    assert "enterprise-agents" not in assign_topics(enterprise_only_row)

    generic_vendor_market_row = {
        "tweet_id": "v2",
        "text": "Pricing pressure is reshaping the model-provider market this quarter.",
        "summary": "Vendor comparison of leading model providers after a pricing update.",
        "tags": '["comparison", "pricing"]',
        "topic": "vendor landscape",
        "raw_urls": '[]',
        "author_username": "lee",
        "author_display_name": "Lee",
        "created_at": None,
        "first_seen_at": "2026-04-08T09:00:00Z",
    }
    assert "vendor-landscape" in assign_topics(generic_vendor_market_row)


def test_generate_topic_notes_renders_required_sections_and_backlinks(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "100",
                text="OpenAI launch changes pricing for copilots",
                first_seen_at="2026-04-08T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "100",
                summary="Vendor comparison of the OpenAI launch and pricing shift",
                tags=["pricing", "comparison"],
                topic="vendor landscape",
            ),
        )
        insert_bookmark(
            connection,
            _bookmark(
                "200",
                text="Analytics engineering workflow for semantic layer observability",
                first_seen_at="2026-04-09T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "200",
                summary="Data platform note on semantic layer observability",
                tags=["dbt", "observability"],
                topic="data platform",
            ),
        )

    for tweet_id in ("100", "200"):
        with get_connection(db_path) as connection:
            row = connection.execute(
                "SELECT * FROM bookmarks WHERE tweet_id = ?",
                (tweet_id,),
            ).fetchone()
        note_path = build_bookmark_note_path(vault_dir, row)
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(f"note for {tweet_id}\n")

    result = generate_topic_notes(db_path=db_path, vault_dir=vault_dir)

    assert result.generated_note_count == len(TOPIC_DEFINITIONS)
    assert sorted(path.name for path in result.written_paths) == [
        "ai-governance.md",
        "data-platform.md",
        "enterprise-agents.md",
        "vendor-landscape.md",
    ]

    vendor_note = (vault_dir / "topics" / "vendor-landscape.md").read_text()
    assert 'note_type: "topic_index"' in vendor_note
    assert 'topic_key: "vendor-landscape"' in vendor_note
    assert "## Scope" in vendor_note
    assert "## Grouping hints" in vendor_note
    assert "## Recent bookmarks" in vendor_note
    assert "Bookmark note: [Open note](../2026/04/openai-launch-changes-pricing-for-copilots-100.md)" in vendor_note
    assert "Source: [View on X](https://x.com/i/web/status/100)" in vendor_note
    assert "Matched signals:" in vendor_note

    data_note = (vault_dir / "topics" / "data-platform.md").read_text()
    assert "2026-04-09 — @user200" in data_note
    assert "semantic layer observability" in data_note
    assert "## Generation notes" in data_note


def test_generate_topic_notes_filters_realistic_false_positives(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "6101",
                text="OpenAI launch changes pricing for enterprise copilots and shifts vendor comparisons this quarter.",
                first_seen_at="2026-04-08T09:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "6101",
                summary="Vendor comparison of the OpenAI launch and pricing move for enterprise buyers.",
                tags=["pricing", "comparison", "vendors"],
                topic="vendor landscape",
            ),
        )
        insert_bookmark(
            connection,
            _bookmark(
                "6102",
                text="Enterprise agent orchestration needs human-in-the-loop workflow evaluation before deployment.",
                first_seen_at="2026-04-09T07:30:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "6102",
                summary="Enterprise agents workflow evaluation with human-in-the-loop deployment guidance.",
                tags=["agent", "workflow", "automation"],
                topic="enterprise agents",
            ),
        )
        insert_bookmark(
            connection,
            _bookmark(
                "6104",
                text="Agent deployments in regulated industries need stronger model controls, audit logs, and safety policy checks.",
                first_seen_at="2026-04-11T06:45:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "6104",
                summary="AI governance checklist for regulated agent deployments with auditability and model controls.",
                tags=["policy", "risk", "auditability"],
                topic="AI governance",
            ),
        )

    for tweet_id in ("6101", "6102", "6104"):
        with get_connection(db_path) as connection:
            row = connection.execute(
                "SELECT * FROM bookmarks WHERE tweet_id = ?",
                (tweet_id,),
            ).fetchone()
        note_path = build_bookmark_note_path(vault_dir, row)
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(f"note for {tweet_id}\n")

    generate_topic_notes(db_path=db_path, vault_dir=vault_dir)

    governance_note = (vault_dir / "topics" / "ai-governance.md").read_text()
    assert "6102" not in governance_note
    assert "6104" in governance_note

    enterprise_note = (vault_dir / "topics" / "enterprise-agents.md").read_text()
    assert "6102" in enterprise_note
    assert "6101" not in enterprise_note
    assert "6104" not in enterprise_note

    vendor_note = (vault_dir / "topics" / "vendor-landscape.md").read_text()
    assert "6101" in vendor_note
    assert "6102" not in vendor_note


def test_generate_topic_notes_is_rerun_safe_and_newest_first(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "300",
                text="Agent orchestration workflow for evaluation",
                first_seen_at="2026-04-07T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "300",
                summary="Enterprise agents pattern for workflow evaluation",
                tags=["agent", "workflow"],
                topic="enterprise agents",
            ),
        )
        insert_bookmark(
            connection,
            _bookmark(
                "301",
                text="Human-in-the-loop agent orchestration for enterprise automation",
                first_seen_at="2026-04-09T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "301",
                summary="Enterprise agents rollout with human-in-the-loop evaluation",
                tags=["agent", "automation"],
                topic="enterprise agents",
            ),
        )

    for tweet_id in ("300", "301"):
        with get_connection(db_path) as connection:
            row = connection.execute(
                "SELECT * FROM bookmarks WHERE tweet_id = ?",
                (tweet_id,),
            ).fetchone()
        note_path = build_bookmark_note_path(vault_dir, row)
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(f"note for {tweet_id}\n")

    first_result = generate_topic_notes(db_path=db_path, vault_dir=vault_dir)
    second_result = generate_topic_notes(db_path=db_path, vault_dir=vault_dir)

    assert first_result.written_paths == second_result.written_paths
    assert len(list((vault_dir / "topics").glob("*.md"))) == len(TOPIC_DEFINITIONS)

    note_text = (vault_dir / "topics" / "enterprise-agents.md").read_text()
    first_index = note_text.index("2026-04-09 — @user301")
    second_index = note_text.index("2026-04-07 — @user300")
    assert first_index < second_index


def test_topics_cli_runner_calls_generator(tmp_path, monkeypatch):
    calls: list[tuple[object, object]] = []

    def fake_generate_topic_notes(**kwargs):
        calls.append((kwargs["db_path"], kwargs["vault_dir"]))
        return type(
            "TopicResult",
            (),
            {
                "generated_note_count": 4,
                "written_paths": tuple(tmp_path / "vault" / f"topic-{index}.md" for index in range(4)),
            },
        )()

    monkeypatch.setattr(cli, "generate_topic_notes", fake_generate_topic_notes)

    result = cli.run_topics(
        db_path=tmp_path / "state" / "app.db",
        vault_dir=tmp_path / "vault",
    )

    assert result.generated_note_count == 4
    assert calls == [(tmp_path / "state" / "app.db", tmp_path / "vault")]


def test_generate_topic_notes_fails_when_database_is_missing(tmp_path):
    db_path = tmp_path / "state" / "missing.db"

    try:
        generate_topic_notes(db_path=db_path, vault_dir=tmp_path / "vault")
    except TopicGenerationError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("generate_topic_notes() should fail for a missing database")

    assert "SQLite database does not exist" in message


def test_generate_topic_notes_fails_when_bookmark_note_is_missing(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    initialize_database(db_path)

    with get_connection(db_path) as connection:
        insert_bookmark(
            connection,
            _bookmark(
                "9901",
                text="OpenAI launch changes pricing for copilots",
                first_seen_at="2026-04-08T10:00:00Z",
            ),
        )
        insert_enrichment(
            connection,
            _enrichment(
                "9901",
                summary="Vendor comparison of the OpenAI launch and pricing shift",
                tags=["pricing", "comparison"],
                topic="vendor landscape",
            ),
        )

    try:
        generate_topic_notes(db_path=db_path, vault_dir=vault_dir)
    except TopicGenerationError as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive
        raise AssertionError("generate_topic_notes() should fail when export notes are missing")

    assert "Bookmark note does not exist" in message
    assert not (vault_dir / "topics").exists()


def test_generate_topic_notes_schema_failure_does_not_create_output_dirs(tmp_path):
    db_path = tmp_path / "state" / "app.db"
    vault_dir = tmp_path / "vault"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("not a sqlite database")

    try:
        generate_topic_notes(db_path=db_path, vault_dir=vault_dir)
    except Exception:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("generate_topic_notes() should fail for an invalid database")

    assert not vault_dir.exists()
