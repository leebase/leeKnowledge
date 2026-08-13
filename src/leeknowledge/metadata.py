"""
Leadership-oriented metadata generation for weekly triage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from leeknowledge.db import APP_DB_PATH, get_connection, initialize_database, upsert_leadership_metadata
from leeknowledge.topics import assign_topics

REQUIRED_BOOKMARK_COLUMNS = {
    "tweet_id",
    "text",
    "author_username",
    "author_display_name",
    "created_at",
    "conversation_id",
    "in_reply_to_id",
    "media_urls",
    "raw_urls",
    "first_seen_at",
}
REQUIRED_ENRICHMENT_COLUMNS = {
    "tweet_id",
    "summary",
    "tags",
    "entities",
    "topic",
    "model",
    "prompt_version",
    "schema_version",
    "validation_status",
    "enriched_at",
}
REQUIRED_LEADERSHIP_METADATA_COLUMNS = {
    "tweet_id",
    "strategic_relevance",
    "time_horizon",
    "organizational_impact",
    "leadership_question",
    "model",
    "prompt_version",
    "schema_version",
    "validation_status",
    "generated_at",
}

PROMPT_VERSION = "1"
SCHEMA_VERSION = "1"
MODEL_NAME = "deterministic-metadata-v1"

STRATEGIC_RELEVANCE_VALUES = {"monitor", "important", "strategic"}
TIME_HORIZON_VALUES = {"now", "next-quarter", "longer-term"}
ORGANIZATIONAL_IMPACT_VALUES = {"team", "cross-functional", "company-wide"}

NOW_KEYWORDS = (
    "launch",
    "pricing",
    "rollout",
    "budget",
    "regulation",
    "policy",
    "compliance",
    "risk",
    "security",
    "deadline",
    "hiring",
    "migration",
)
LONG_TERM_KEYWORDS = (
    "research",
    "vision",
    "long-term",
    "long term",
    "future",
    "emerging",
    "watch",
)
CROSS_FUNCTIONAL_KEYWORDS = (
    "enterprise",
    "platform",
    "workflow",
    "operations",
    "rollout",
    "company",
    "leadership",
)
COMPANY_WIDE_KEYWORDS = (
    "policy",
    "compliance",
    "risk",
    "pricing",
    "vendor",
    "governance",
    "security",
)


class MetadataError(RuntimeError):
    """Raised when metadata generation cannot complete safely."""


@dataclass(frozen=True)
class MetadataRunResult:
    """Summary of a completed leadership metadata run."""

    processed_bookmark_count: int
    inserted_metadata_count: int
    skipped_existing_count: int
    placeholder_count: int
    failed_bookmark_count: int
    prompt_version: str = PROMPT_VERSION
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class LeadershipMetadataRecord:
    tweet_id: str
    strategic_relevance: str | None
    time_horizon: str | None
    organizational_impact: str | None
    leadership_question: str | None
    model: str
    prompt_version: str
    schema_version: str
    validation_status: str
    generated_at: str


def generate_leadership_metadata(
    db_path: Path | str = APP_DB_PATH,
) -> MetadataRunResult:
    """Generate deterministic leadership metadata for enriched bookmarks."""

    resolved_db_path = Path(db_path)
    if not resolved_db_path.exists():
        raise MetadataError(f"SQLite database does not exist: {resolved_db_path}")

    resolved_db_path = initialize_database(resolved_db_path)
    _validate_metadata_database(resolved_db_path)
    processed_count = 0
    inserted_count = 0
    skipped_existing_count = 0
    placeholder_count = 0
    failed_count = 0

    with get_connection(resolved_db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                b.tweet_id,
                b.text,
                b.author_username,
                b.author_display_name,
                b.created_at,
                b.conversation_id,
                b.in_reply_to_id,
                b.media_urls,
                b.raw_urls,
                b.first_seen_at,
                e.summary,
                e.tags,
                e.entities,
                e.topic,
                e.model AS enrichment_model,
                e.prompt_version AS enrichment_prompt_version,
                e.schema_version AS enrichment_schema_version,
                e.validation_status AS enrichment_validation_status,
                e.enriched_at,
                m.tweet_id AS metadata_tweet_id,
                m.prompt_version AS metadata_prompt_version,
                m.schema_version AS metadata_schema_version,
                m.validation_status AS metadata_validation_status
            FROM bookmarks AS b
            INNER JOIN enrichments AS e ON e.tweet_id = b.tweet_id
            LEFT JOIN leadership_metadata AS m ON m.tweet_id = b.tweet_id
            ORDER BY b.first_seen_at, b.tweet_id
            """
        ).fetchall()

        for row in rows:
            if _has_current_valid_metadata(row):
                skipped_existing_count += 1
                continue

            processed_count += 1
            try:
                if row["enrichment_validation_status"] != "valid":
                    record = _build_placeholder_record(
                        tweet_id=str(row["tweet_id"]),
                        validation_status="blocked_enrichment_invalid",
                    )
                else:
                    record = _build_metadata_record(row)
            except Exception as exc:
                failed_count += 1
                record = _build_placeholder_record(
                    tweet_id=str(row["tweet_id"]),
                    validation_status=f"error:{type(exc).__name__}",
                )
                placeholder_count += 1
            else:
                if record.validation_status != "valid":
                    placeholder_count += 1

            upsert_leadership_metadata(connection, record.__dict__)
            inserted_count += 1

    return MetadataRunResult(
        processed_bookmark_count=processed_count,
        inserted_metadata_count=inserted_count,
        skipped_existing_count=skipped_existing_count,
        placeholder_count=placeholder_count,
        failed_bookmark_count=failed_count,
    )


def _has_current_valid_metadata(row: Mapping[str, Any]) -> bool:
    return (
        row["metadata_tweet_id"] is not None
        and row["metadata_validation_status"] == "valid"
        and row["metadata_prompt_version"] == PROMPT_VERSION
        and row["metadata_schema_version"] == SCHEMA_VERSION
    )


def _build_metadata_record(row: Mapping[str, Any]) -> LeadershipMetadataRecord:
    topic_matches = assign_topics(row)
    topic_keys = tuple(topic_matches.keys())
    signal_text = _signal_text(row, topic_keys)

    if not signal_text.strip():
        return _build_placeholder_record(
            tweet_id=str(row["tweet_id"]),
            validation_status="insufficient_signal",
        )

    time_horizon = _derive_time_horizon(signal_text, topic_keys)
    organizational_impact = _derive_organizational_impact(signal_text, topic_keys)
    strategic_relevance = _derive_strategic_relevance(
        signal_text=signal_text,
        topic_keys=topic_keys,
        time_horizon=time_horizon,
        organizational_impact=organizational_impact,
    )
    leadership_question = _derive_leadership_question(
        topic_keys=topic_keys,
        strategic_relevance=strategic_relevance,
        time_horizon=time_horizon,
    )

    record = LeadershipMetadataRecord(
        tweet_id=str(row["tweet_id"]),
        strategic_relevance=strategic_relevance,
        time_horizon=time_horizon,
        organizational_impact=organizational_impact,
        leadership_question=leadership_question,
        model=MODEL_NAME,
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        validation_status="valid",
        generated_at=_utc_now(),
    )
    _validate_record(record)
    return record


def _signal_text(row: Mapping[str, Any], topic_keys: tuple[str, ...]) -> str:
    parts = [
        str(row["topic"] or ""),
        str(row["summary"] or ""),
        str(row["text"] or ""),
        " ".join(topic_keys),
        str(row["tags"] or ""),
    ]
    return " ".join(part.strip().lower() for part in parts if isinstance(part, str))


def _derive_time_horizon(signal_text: str, topic_keys: tuple[str, ...]) -> str:
    if any(keyword in signal_text for keyword in NOW_KEYWORDS):
        return "now"
    if "vendor-landscape" in topic_keys or "ai-governance" in topic_keys:
        return "now"
    if any(keyword in signal_text for keyword in LONG_TERM_KEYWORDS):
        return "longer-term"
    if topic_keys:
        return "next-quarter"
    return "longer-term"


def _derive_organizational_impact(signal_text: str, topic_keys: tuple[str, ...]) -> str:
    if "ai-governance" in topic_keys:
        return "company-wide"
    if any(keyword in signal_text for keyword in COMPANY_WIDE_KEYWORDS) and (
        "vendor-landscape" in topic_keys or "ai-governance" in topic_keys
    ):
        return "company-wide"
    if len(topic_keys) > 1 or any(keyword in signal_text for keyword in CROSS_FUNCTIONAL_KEYWORDS):
        return "cross-functional"
    if topic_keys:
        return "cross-functional"
    return "team"


def _derive_strategic_relevance(
    *,
    signal_text: str,
    topic_keys: tuple[str, ...],
    time_horizon: str,
    organizational_impact: str,
) -> str:
    if organizational_impact == "company-wide" and time_horizon in {"now", "next-quarter"}:
        return "strategic"
    if len(topic_keys) > 1 and time_horizon != "longer-term":
        return "strategic"
    if organizational_impact == "cross-functional" or time_horizon == "now":
        return "important"
    if any(keyword in signal_text for keyword in ("decision", "priority", "budget", "roadmap")):
        return "important"
    return "monitor"


def _derive_leadership_question(
    *,
    topic_keys: tuple[str, ...],
    strategic_relevance: str,
    time_horizon: str,
) -> str | None:
    should_render = strategic_relevance == "strategic" or (
        strategic_relevance == "important" and time_horizon == "now"
    )
    if not should_render:
        return None

    primary_topic = topic_keys[0] if topic_keys else None
    prompts = {
        "ai-governance": "What guardrails or controls should we tighten now?",
        "enterprise-agents": "Which workflow is ready for broader rollout next?",
        "data-platform": "Which platform investment should move up the queue?",
        "vendor-landscape": "Does this change our vendor posture this quarter?",
    }
    return prompts.get(primary_topic, "What decision does this signal change right now?")


def _validate_record(record: LeadershipMetadataRecord) -> None:
    if record.strategic_relevance not in STRATEGIC_RELEVANCE_VALUES:
        raise MetadataError("Invalid strategic_relevance value.")
    if record.time_horizon not in TIME_HORIZON_VALUES:
        raise MetadataError("Invalid time_horizon value.")
    if record.organizational_impact not in ORGANIZATIONAL_IMPACT_VALUES:
        raise MetadataError("Invalid organizational_impact value.")
    if record.leadership_question is not None and len(record.leadership_question) > 120:
        raise MetadataError("leadership_question must stay short.")


def _build_placeholder_record(
    *,
    tweet_id: str,
    validation_status: str,
) -> LeadershipMetadataRecord:
    return LeadershipMetadataRecord(
        tweet_id=tweet_id,
        strategic_relevance=None,
        time_horizon=None,
        organizational_impact=None,
        leadership_question=None,
        model=MODEL_NAME,
        prompt_version=PROMPT_VERSION,
        schema_version=SCHEMA_VERSION,
        validation_status=validation_status,
        generated_at=_utc_now(),
    )


def _validate_metadata_database(db_path: Path) -> None:
    with get_connection(db_path) as connection:
        _validate_table(connection, "bookmarks", REQUIRED_BOOKMARK_COLUMNS, db_path)
        _validate_table(connection, "enrichments", REQUIRED_ENRICHMENT_COLUMNS, db_path)
        _validate_table(
            connection,
            "leadership_metadata",
            REQUIRED_LEADERSHIP_METADATA_COLUMNS,
            db_path,
        )


def _validate_table(connection, table_name: str, required_columns: set[str], db_path: Path) -> None:
    table_row = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    if table_row is None:
        raise MetadataError(
            f"SQLite database is missing required table '{table_name}': {db_path}"
        )

    column_rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    available_columns = {str(row["name"]) for row in column_rows}
    missing_columns = sorted(required_columns - available_columns)
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise MetadataError(
            f"SQLite database table '{table_name}' is missing required columns "
            f"({missing_text}): {db_path}"
        )


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
