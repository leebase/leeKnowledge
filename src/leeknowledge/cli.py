"""
CLI scaffold for the leeKnowledge pipeline.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from leeknowledge import __version__
from leeknowledge.db import APP_DB_PATH, initialize_database
from leeknowledge.enricher import EnrichmentError, EnrichmentRunResult, enrich_bookmarks
from leeknowledge.exporter import (
    ExportError,
    ExportRunResult,
    export_markdown,
    export_story_markdown,
)
from leeknowledge.topics import (
    TopicGenerationError,
    TopicRunResult,
    generate_topic_notes,
)
from leeknowledge.metadata import (
    MetadataError,
    MetadataRunResult,
    generate_leadership_metadata,
)
from leeknowledge.synthesis import (
    SynthesisError,
    SynthesisRunResult,
    generate_weekly_synthesis,
)
from leeknowledge.collections import (
    CollectionGenerationError,
    CollectionRunResult,
    DEFAULT_DEFINITIONS_PATH,
    generate_collection_notes,
)
from leeknowledge.extractor import (
    EmptyCaptureError,
    ExtractionError,
    ExtractionRunResult,
    extract_bookmarks,
    DEFAULT_BOOKMARKS_URL,
)
from leeknowledge.intake import (
    IntakeError,
    IntakeRunResult,
    import_research_artifact,
    import_safari_bookmarks,
    import_urls,
)

APP_NAME = "leeknowledge"
APP_DESCRIPTION = (
    "Local-first X bookmark pipeline: extract, enrich, and export to Markdown."
)


def run_extract(
    raw_output_dir: Path,
    db_path: Path,
    chrome_profile_dir: Path | None,
    headless: bool,
    bookmarks_url: str = DEFAULT_BOOKMARKS_URL,
    cdp_endpoint: str | None = None,
) -> ExtractionRunResult:
    return extract_bookmarks(
        raw_output_dir=raw_output_dir,
        db_path=db_path,
        chrome_profile_dir=chrome_profile_dir,
        headless=headless,
        bookmarks_url=bookmarks_url,
        cdp_endpoint=cdp_endpoint,
    )


def run_enrich(db_path: Path, config_path: Path) -> EnrichmentRunResult:
    return enrich_bookmarks(db_path=db_path, config_path=config_path)


def run_import_url(urls: list[str], raw_output_dir: Path, db_path: Path) -> IntakeRunResult:
    return import_urls(urls=urls, raw_output_dir=raw_output_dir, db_path=db_path)


def run_import_safari_folder(input_path: Path, raw_output_dir: Path, db_path: Path) -> IntakeRunResult:
    return import_safari_bookmarks(input_path=input_path, raw_output_dir=raw_output_dir, db_path=db_path)


def run_import_research(input_path: Path, raw_output_dir: Path, db_path: Path) -> IntakeRunResult:
    return import_research_artifact(input_path=input_path, raw_output_dir=raw_output_dir, db_path=db_path)


def run_export(db_path: Path, vault_dir: Path) -> ExportRunResult:
    return export_markdown(db_path=db_path, vault_dir=vault_dir)


def run_export_stories(db_path: Path, vault_dir: Path) -> ExportRunResult:
    return export_story_markdown(db_path=db_path, vault_dir=vault_dir)


def run_topics(db_path: Path, vault_dir: Path) -> TopicRunResult:
    return generate_topic_notes(db_path=db_path, vault_dir=vault_dir)


def run_metadata(db_path: Path) -> MetadataRunResult:
    return generate_leadership_metadata(db_path=db_path)


def run_synthesize(period: str, db_path: Path, vault_dir: Path) -> SynthesisRunResult:
    return generate_weekly_synthesis(period_key=period, db_path=db_path, vault_dir=vault_dir)


def run_collections(
    db_path: Path,
    vault_dir: Path,
    definitions_path: Path,
) -> CollectionRunResult:
    return generate_collection_notes(
        db_path=db_path,
        vault_dir=vault_dir,
        definitions_path=definitions_path,
    )


def run_sync(
    raw_output_dir: Path,
    db_path: Path,
    chrome_profile_dir: Path | None,
    headless: bool,
    config_path: Path,
    vault_dir: Path,
    bookmarks_url: str = DEFAULT_BOOKMARKS_URL,
    cdp_endpoint: str | None = None,
) -> tuple[ExtractionRunResult, EnrichmentRunResult, ExportRunResult]:
    extract_result = run_extract(
        raw_output_dir=raw_output_dir,
        db_path=db_path,
        chrome_profile_dir=chrome_profile_dir,
        headless=headless,
        bookmarks_url=bookmarks_url,
        cdp_endpoint=cdp_endpoint,
    )
    enrich_result = run_enrich(db_path=db_path, config_path=config_path)
    export_result = run_export(db_path=db_path, vault_dir=vault_dir)
    return extract_result, enrich_result, export_result


try:
    import typer
except ImportError:  # pragma: no cover - exercised by local CLI fallback.
    typer = None


if typer is not None:
    app = typer.Typer(
        add_completion=False,
        help=APP_DESCRIPTION,
        no_args_is_help=True,
    )

    def _init_state(db_path: Path = APP_DB_PATH) -> Path:
        db_path = initialize_database(db_path)
        typer.echo(f"Database ready at {db_path}")
        return db_path

    def _run_extract(
        raw_output_dir: Path,
        db_path: Path,
        chrome_profile_dir: Path | None,
        headless: bool,
        bookmarks_url: str = DEFAULT_BOOKMARKS_URL,
        cdp_endpoint: str | None = None,
    ) -> ExtractionRunResult:
        result = extract_bookmarks(
            raw_output_dir=raw_output_dir,
            db_path=db_path,
            chrome_profile_dir=chrome_profile_dir,
            headless=headless,
            bookmarks_url=bookmarks_url,
            cdp_endpoint=cdp_endpoint,
        )
        typer.echo(
            f"Captured {result.captured_payload_count} raw payloads, "
            f"normalized {result.normalized_record_count} records, "
            f"inserted {result.inserted_record_count} new rows."
        )
        typer.echo(f"Raw archive written to {result.archive_path}")
        if result.skipped_issues:
            typer.echo(f"Skipped {len(result.skipped_issues)} malformed raw payloads.")
        return result

    @app.command()
    def extract(
        raw_output_dir: Path = typer.Option(
            Path("data/raw"),
            "--raw-output-dir",
            envvar="LEEKNOWLEDGE_RAW_DIR",
            help="Directory for immutable raw bookmark archives.",
        ),
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
        chrome_profile_dir: Path | None = typer.Option(
            None,
            "--chrome-profile-dir",
            envvar="LEEKNOWLEDGE_CHROME_PROFILE_DIR",
            help="Chrome user data directory or profile path.",
        ),
        headless: bool = typer.Option(
            False,
            "--headless/--no-headless",
            envvar="LEEKNOWLEDGE_HEADLESS",
            help="Run Chrome headlessly.",
        ),
        bookmarks_url: str = typer.Option(
            DEFAULT_BOOKMARKS_URL,
            "--bookmarks-url",
            envvar="LEEKNOWLEDGE_BOOKMARKS_URL",
            help=(
                "Bookmarks page URL to open. Use a folder URL for folder-scoped "
                "scans."
            ),
        ),
        cdp_endpoint: str | None = typer.Option(
            None,
            "--cdp-endpoint",
            envvar="LEEKNOWLEDGE_CHROME_CDP_ENDPOINT",
            help=(
                "Optional Chrome DevTools endpoint (for example "
                "http://127.0.0.1:9222) to use a running Chrome session."
            ),
        ),
    ) -> None:
        """Extract bookmarks from X and normalize them into SQLite."""

        try:
            _run_extract(
                raw_output_dir=raw_output_dir,
                db_path=db_path,
                chrome_profile_dir=chrome_profile_dir,
                headless=headless,
                cdp_endpoint=cdp_endpoint,
                bookmarks_url=bookmarks_url,
            )
        except EmptyCaptureError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        except ExtractionError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    def _echo_intake_result(result: IntakeRunResult) -> None:
        typer.echo(
            f"Imported {result.imported_record_count} records, inserted {result.inserted_record_count} new rows, quarantined {result.quarantined_record_count} records."
        )
        typer.echo(f"Raw archive written to {result.archive_path}")
        if result.quarantine_path is not None:
            typer.echo(f"Quarantine written to {result.quarantine_path}")

    @app.command("import-url")
    def import_url(
        urls: list[str] = typer.Argument(..., help="One or more absolute URLs to import."),
        raw_output_dir: Path = typer.Option(
            Path("data/raw"),
            "--raw-output-dir",
            envvar="LEEKNOWLEDGE_RAW_DIR",
            help="Directory for immutable raw import archives.",
        ),
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
    ) -> None:
        """Import one or more explicit URLs into the canonical source table."""

        try:
            _echo_intake_result(import_urls(urls=urls, raw_output_dir=raw_output_dir, db_path=db_path))
        except IntakeError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    @app.command("import-safari-folder")
    def import_safari_folder(
        input_path: Path = typer.Option(..., "--input", help="Safari Bookmarks.plist path."),
        raw_output_dir: Path = typer.Option(
            Path("data/raw"),
            "--raw-output-dir",
            envvar="LEEKNOWLEDGE_RAW_DIR",
            help="Directory for immutable raw import archives.",
        ),
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
    ) -> None:
        """Import Safari bookmark exports through the shared source intake contract."""

        try:
            _echo_intake_result(import_safari_bookmarks(input_path=input_path, raw_output_dir=raw_output_dir, db_path=db_path))
        except IntakeError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    @app.command("import-research")
    def import_research(
        input_path: Path = typer.Argument(..., help="Research artifact path (JSON, JSONL, CSV, Markdown, or text)."),
        raw_output_dir: Path = typer.Option(
            Path("data/raw"),
            "--raw-output-dir",
            envvar="LEEKNOWLEDGE_RAW_DIR",
            help="Directory for immutable raw import archives.",
        ),
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
    ) -> None:
        """Import research artifacts through the shared source intake contract."""

        try:
            _echo_intake_result(import_research_artifact(input_path=input_path, raw_output_dir=raw_output_dir, db_path=db_path))
        except IntakeError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    @app.command()
    def enrich(
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
        config_path: Path = typer.Option(
            Path("config/llm.yaml"),
            "--config-path",
            envvar="LEEKNOWLEDGE_LLM_CONFIG_PATH",
            help="Local LLM config path.",
        ),
    ) -> None:
        """Enrich unprocessed bookmarks via the local LLM router."""

        try:
            result: EnrichmentRunResult = enrich_bookmarks(
                db_path=db_path,
                config_path=config_path,
            )
        except EnrichmentError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

        typer.echo(
            f"Processed {result.processed_bookmark_count} bookmarks, "
            f"inserted {result.inserted_enrichment_count} enrichment rows, "
            f"skipped {result.skipped_existing_count} existing rows."
        )
        typer.echo(
            f"Cached {result.cached_url_count} URLs; "
            f"placeholders written for {result.placeholder_count} bookmarks."
        )

    def _run_export(db_path: Path, vault_dir: Path) -> ExportRunResult:
        result = export_markdown(db_path=db_path, vault_dir=vault_dir)
        typer.echo(
            f"Exported {result.exported_note_count} Markdown notes to {vault_dir}."
        )
        for path in result.written_paths[:5]:
            typer.echo(f"- {path}")
        if len(result.written_paths) > 5:
            typer.echo(f"- ... and {len(result.written_paths) - 5} more")
        return result

    def _run_export_stories(db_path: Path, vault_dir: Path) -> ExportRunResult:
        result = export_story_markdown(db_path=db_path, vault_dir=vault_dir)
        typer.echo(
            f"Exported {result.exported_note_count} story Markdown files to {vault_dir / 'stories'}."
        )
        for path in result.written_paths[:5]:
            typer.echo(f"- {path}")
        if len(result.written_paths) > 5:
            typer.echo(f"- ... and {len(result.written_paths) - 5} more")
        return result

    def _run_topics(db_path: Path, vault_dir: Path) -> TopicRunResult:
        result = generate_topic_notes(db_path=db_path, vault_dir=vault_dir)
        typer.echo(
            f"Generated {result.generated_note_count} topic notes in {vault_dir / 'topics'}."
        )
        for path in result.written_paths:
            typer.echo(f"- {path}")
        return result

    def _run_metadata(db_path: Path) -> MetadataRunResult:
        result = generate_leadership_metadata(db_path=db_path)
        typer.echo(
            f"Processed {result.processed_bookmark_count} bookmarks, "
            f"updated {result.inserted_metadata_count} leadership metadata rows, "
            f"skipped {result.skipped_existing_count} current rows."
        )
        if result.placeholder_count:
            typer.echo(
                f"Placeholder metadata written for {result.placeholder_count} bookmarks."
            )
        return result

    def _run_synthesize(period: str, db_path: Path, vault_dir: Path) -> SynthesisRunResult:
        result = generate_weekly_synthesis(
            period_key=period,
            db_path=db_path,
            vault_dir=vault_dir,
        )
        typer.echo(f"Generated weekly synthesis for {result.period_key}.")
        typer.echo(f"- {result.weekly_note_path}")
        typer.echo(f"- {result.latest_alias_path}")
        return result

    def _run_collections(
        db_path: Path,
        vault_dir: Path,
        definitions_path: Path,
    ) -> CollectionRunResult:
        result = generate_collection_notes(
            db_path=db_path,
            vault_dir=vault_dir,
            definitions_path=definitions_path,
        )
        typer.echo(
            f"Generated {result.generated_note_count} curated collection notes in {vault_dir / 'collections'}."
        )
        for path in result.written_paths:
            typer.echo(f"- {path}")
        return result

    def _run_sync(
        raw_output_dir: Path,
        db_path: Path,
        chrome_profile_dir: Path | None,
        headless: bool,
        config_path: Path,
        vault_dir: Path,
        bookmarks_url: str = DEFAULT_BOOKMARKS_URL,
        cdp_endpoint: str | None = None,
    ) -> tuple[ExtractionRunResult, EnrichmentRunResult, ExportRunResult]:
        extract_result = _run_extract(
            raw_output_dir=raw_output_dir,
            db_path=db_path,
            chrome_profile_dir=chrome_profile_dir,
            headless=headless,
            bookmarks_url=bookmarks_url,
            cdp_endpoint=cdp_endpoint,
        )
        enrich_result = enrich_bookmarks(db_path=db_path, config_path=config_path)
        typer.echo(
            f"Processed {enrich_result.processed_bookmark_count} bookmarks, "
            f"inserted {enrich_result.inserted_enrichment_count} enrichment rows, "
            f"skipped {enrich_result.skipped_existing_count} existing rows."
        )
        typer.echo(
            f"Cached {enrich_result.cached_url_count} URLs; "
            f"placeholders written for {enrich_result.placeholder_count} bookmarks."
        )
        export_result = _run_export(db_path=db_path, vault_dir=vault_dir)
        return extract_result, enrich_result, export_result

    @app.command()
    def export(
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
        vault_dir: Path = typer.Option(
            Path("vault"),
            "--vault-dir",
            envvar="LEEKNOWLEDGE_VAULT_DIR",
            help="Directory for rendered Markdown notes.",
        ),
    ) -> None:
        """Export bookmarks from SQLite into Markdown notes."""

        try:
            _run_export(db_path=db_path, vault_dir=vault_dir)
        except ExportError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    @app.command("export-stories")
    def export_stories(
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
        vault_dir: Path = typer.Option(
            Path("vault"),
            "--vault-dir",
            envvar="LEEKNOWLEDGE_VAULT_DIR",
            help="Directory for rendered Markdown notes.",
        ),
    ) -> None:
        """Export full story/article text per bookmark into Markdown files."""

        try:
            _run_export_stories(db_path=db_path, vault_dir=vault_dir)
        except ExportError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    @app.command()
    def topics(
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
        vault_dir: Path = typer.Option(
            Path("vault"),
            "--vault-dir",
            envvar="LEEKNOWLEDGE_VAULT_DIR",
            help="Directory for rendered Markdown notes.",
        ),
    ) -> None:
        """Generate deterministic topic index notes from existing local state."""

        try:
            _run_topics(db_path=db_path, vault_dir=vault_dir)
        except TopicGenerationError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    @app.command()
    def metadata(
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
    ) -> None:
        """Generate leadership metadata for existing enriched bookmarks."""

        try:
            _run_metadata(db_path=db_path)
        except MetadataError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    @app.command("synthesize")
    def synthesize(
        cadence: str = typer.Option(
            "weekly",
            "--cadence",
            help="Synthesis cadence. Only 'weekly' is currently supported.",
        ),
        period: str = typer.Option(
            ...,
            "--period",
            help="ISO weekly period key like 2026-W15.",
        ),
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
        vault_dir: Path = typer.Option(
            Path("vault"),
            "--vault-dir",
            envvar="LEEKNOWLEDGE_VAULT_DIR",
            help="Directory for rendered Markdown notes.",
        ),
    ) -> None:
        """Generate a weekly leadership synthesis note from existing local state."""

        if cadence != "weekly":
            typer.echo("Only weekly synthesis is currently supported.", err=True)
            raise typer.Exit(code=1)

        try:
            _run_synthesize(period=period, db_path=db_path, vault_dir=vault_dir)
        except (SynthesisError, ExportError) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    @app.command()
    def collections(
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
        vault_dir: Path = typer.Option(
            Path("vault"),
            "--vault-dir",
            envvar="LEEKNOWLEDGE_VAULT_DIR",
            help="Directory for rendered Markdown notes.",
        ),
        definitions_path: Path = typer.Option(
            DEFAULT_DEFINITIONS_PATH,
            "--definitions-path",
            help="Checked-in curated collection definitions.",
        ),
    ) -> None:
        """Generate curated collection notes from existing local state."""

        try:
            _run_collections(
                db_path=db_path,
                vault_dir=vault_dir,
                definitions_path=definitions_path,
            )
        except CollectionGenerationError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    @app.command()
    def sync(
        raw_output_dir: Path = typer.Option(
            Path("data/raw"),
            "--raw-output-dir",
            envvar="LEEKNOWLEDGE_RAW_DIR",
            help="Directory for immutable raw bookmark archives.",
        ),
        db_path: Path = typer.Option(
            APP_DB_PATH,
            "--db-path",
            envvar="LEEKNOWLEDGE_DB_PATH",
            help="SQLite database path.",
        ),
        chrome_profile_dir: Path | None = typer.Option(
            None,
            "--chrome-profile-dir",
            envvar="LEEKNOWLEDGE_CHROME_PROFILE_DIR",
            help="Chrome user data directory or profile path.",
        ),
        headless: bool = typer.Option(
            False,
            "--headless/--no-headless",
            envvar="LEEKNOWLEDGE_HEADLESS",
            help="Run Chrome headlessly.",
        ),
        cdp_endpoint: str | None = typer.Option(
            None,
            "--cdp-endpoint",
            envvar="LEEKNOWLEDGE_CHROME_CDP_ENDPOINT",
            help=(
                "Optional Chrome DevTools endpoint (for example "
                "http://127.0.0.1:9222) to use a running Chrome session."
            ),
        ),
        bookmarks_url: str = typer.Option(
            DEFAULT_BOOKMARKS_URL,
            "--bookmarks-url",
            envvar="LEEKNOWLEDGE_BOOKMARKS_URL",
            help=(
                "Bookmarks page URL to open. Use a folder URL for folder-scoped "
                "scans."
            ),
        ),
        config_path: Path = typer.Option(
            Path("config/llm.yaml"),
            "--config-path",
            envvar="LEEKNOWLEDGE_LLM_CONFIG_PATH",
            help="Local LLM config path.",
        ),
        vault_dir: Path = typer.Option(
            Path("vault"),
            "--vault-dir",
            envvar="LEEKNOWLEDGE_VAULT_DIR",
            help="Directory for rendered Markdown notes.",
        ),
    ) -> None:
        """Run extract, enrich, and export in sequence."""

        try:
            _run_sync(
                raw_output_dir=raw_output_dir,
                db_path=db_path,
                chrome_profile_dir=chrome_profile_dir,
                headless=headless,
                bookmarks_url=bookmarks_url,
                cdp_endpoint=cdp_endpoint,
                config_path=config_path,
                vault_dir=vault_dir,
            )
        except (
            EmptyCaptureError,
            ExtractionError,
            EnrichmentError,
            ExportError,
        ) as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    @app.command()
    def db() -> None:
        """Initialize the local SQLite database and exit."""
        _init_state()

    def main() -> None:
        app()

else:

    def main() -> None:
        parser = argparse.ArgumentParser(
            prog=APP_NAME,
            description=APP_DESCRIPTION,
        )
        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {__version__}",
        )
        subparsers = parser.add_subparsers(dest="command")

        extract_parser = subparsers.add_parser(
            "extract",
            help="Extract bookmarks from X into SQLite.",
        )
        extract_parser.add_argument(
            "--raw-output-dir",
            type=Path,
            default=Path("data/raw"),
        )
        extract_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )
        extract_parser.add_argument(
            "--bookmarks-url",
            default=DEFAULT_BOOKMARKS_URL,
        )
        extract_parser.add_argument("--chrome-profile-dir", type=Path)
        extract_parser.add_argument("--headless", action="store_true")
        extract_parser.add_argument(
            "--cdp-endpoint",
            default=os.environ.get("LEEKNOWLEDGE_CHROME_CDP_ENDPOINT"),
        )

        import_url_parser = subparsers.add_parser(
            "import-url",
            help="Import one or more explicit URLs.",
        )
        import_url_parser.add_argument("urls", nargs="+")
        import_url_parser.add_argument(
            "--raw-output-dir",
            type=Path,
            default=Path("data/raw"),
        )
        import_url_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )

        safari_parser = subparsers.add_parser(
            "import-safari-folder",
            help="Import Safari bookmarks from a plist export.",
        )
        safari_parser.add_argument("--input", required=True, type=Path)
        safari_parser.add_argument(
            "--raw-output-dir",
            type=Path,
            default=Path("data/raw"),
        )
        safari_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )

        research_parser = subparsers.add_parser(
            "import-research",
            help="Import a research artifact.",
        )
        research_parser.add_argument("input_path", type=Path)
        research_parser.add_argument(
            "--raw-output-dir",
            type=Path,
            default=Path("data/raw"),
        )
        research_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )

        enrich_parser = subparsers.add_parser(
            "enrich",
            help="Enrich bookmarks via the local LLM router.",
        )
        enrich_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )
        enrich_parser.add_argument(
            "--config-path",
            type=Path,
            default=Path("config/llm.yaml"),
        )

        export_parser = subparsers.add_parser(
            "export",
            help="Export bookmarks to Markdown.",
        )
        export_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )
        export_parser.add_argument(
            "--vault-dir",
            type=Path,
            default=Path("vault"),
        )

        topics_parser = subparsers.add_parser(
            "topics",
            help="Generate deterministic topic index notes.",
        )
        topics_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )
        topics_parser.add_argument(
            "--vault-dir",
            type=Path,
            default=Path("vault"),
        )

        metadata_parser = subparsers.add_parser(
            "metadata",
            help="Generate leadership metadata for enriched bookmarks.",
        )
        metadata_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )

        synthesize_parser = subparsers.add_parser(
            "synthesize",
            help="Generate a weekly leadership synthesis note.",
        )
        synthesize_parser.add_argument(
            "--cadence",
            default="weekly",
        )
        synthesize_parser.add_argument(
            "--period",
            required=True,
        )
        synthesize_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )
        synthesize_parser.add_argument(
            "--vault-dir",
            type=Path,
            default=Path("vault"),
        )

        collections_parser = subparsers.add_parser(
            "collections",
            help="Generate curated collection notes.",
        )
        collections_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )
        collections_parser.add_argument(
            "--vault-dir",
            type=Path,
            default=Path("vault"),
        )
        collections_parser.add_argument(
            "--definitions-path",
            type=Path,
            default=DEFAULT_DEFINITIONS_PATH,
        )

        export_stories_parser = subparsers.add_parser(
            "export-stories",
            help="Export full story/article text from bookmarks into Markdown.",
        )
        export_stories_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )
        export_stories_parser.add_argument(
            "--vault-dir",
            type=Path,
            default=Path("vault"),
        )

        sync_parser = subparsers.add_parser(
            "sync",
            help="Run extract, enrich, and export in sequence.",
        )
        sync_parser.add_argument(
            "--raw-output-dir",
            type=Path,
            default=Path("data/raw"),
        )
        sync_parser.add_argument(
            "--db-path",
            type=Path,
            default=APP_DB_PATH,
        )
        sync_parser.add_argument("--chrome-profile-dir", type=Path)
        sync_parser.add_argument(
            "--cdp-endpoint",
            default=os.environ.get("LEEKNOWLEDGE_CHROME_CDP_ENDPOINT"),
        )
        sync_parser.add_argument("--headless", action="store_true")
        sync_parser.add_argument(
            "--bookmarks-url",
            default=DEFAULT_BOOKMARKS_URL,
        )
        sync_parser.add_argument(
            "--config-path",
            type=Path,
            default=Path("config/llm.yaml"),
        )
        sync_parser.add_argument(
            "--vault-dir",
            type=Path,
            default=Path("vault"),
        )

        subparsers.add_parser(
            "db",
            help="Initialize the local SQLite database and exit.",
        )

        args = parser.parse_args()
        if args.command is None:
            parser.print_help()
            return

        if args.command == "db":
            db_path = initialize_database(APP_DB_PATH)
            print(f"Database ready at {db_path}")
            return

        if args.command == "extract":
            try:
                result = extract_bookmarks(
                    raw_output_dir=args.raw_output_dir,
                    db_path=args.db_path,
                    chrome_profile_dir=args.chrome_profile_dir,
                    headless=args.headless,
                    bookmarks_url=args.bookmarks_url,
                    cdp_endpoint=getattr(args, "cdp_endpoint", None),
                )
            except EmptyCaptureError as exc:
                print(str(exc))
                raise SystemExit(1) from exc
            except ExtractionError as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(
                f"Captured {result.captured_payload_count} raw payloads, "
                f"normalized {result.normalized_record_count} records, "
                f"inserted {result.inserted_record_count} new rows."
            )
            print(f"Raw archive written to {result.archive_path}")
            if result.skipped_issues:
                print(f"Skipped {len(result.skipped_issues)} malformed raw payloads.")
            return

        if args.command == "import-url":
            try:
                result = import_urls(
                    urls=args.urls,
                    raw_output_dir=args.raw_output_dir,
                    db_path=args.db_path,
                )
            except IntakeError as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(
                f"Imported {result.imported_record_count} records, inserted {result.inserted_record_count} new rows, quarantined {result.quarantined_record_count} records."
            )
            print(f"Raw archive written to {result.archive_path}")
            if result.quarantine_path is not None:
                print(f"Quarantine written to {result.quarantine_path}")
            return

        if args.command == "import-safari-folder":
            try:
                result = import_safari_bookmarks(
                    input_path=args.input,
                    raw_output_dir=args.raw_output_dir,
                    db_path=args.db_path,
                )
            except IntakeError as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(
                f"Imported {result.imported_record_count} records, inserted {result.inserted_record_count} new rows, quarantined {result.quarantined_record_count} records."
            )
            print(f"Raw archive written to {result.archive_path}")
            if result.quarantine_path is not None:
                print(f"Quarantine written to {result.quarantine_path}")
            return

        if args.command == "import-research":
            try:
                result = import_research_artifact(
                    input_path=args.input_path,
                    raw_output_dir=args.raw_output_dir,
                    db_path=args.db_path,
                )
            except IntakeError as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(
                f"Imported {result.imported_record_count} records, inserted {result.inserted_record_count} new rows, quarantined {result.quarantined_record_count} records."
            )
            print(f"Raw archive written to {result.archive_path}")
            if result.quarantine_path is not None:
                print(f"Quarantine written to {result.quarantine_path}")
            return

        if args.command == "enrich":
            try:
                result = enrich_bookmarks(
                    db_path=args.db_path,
                    config_path=args.config_path,
                )
            except EnrichmentError as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(
                f"Processed {result.processed_bookmark_count} bookmarks, "
                f"inserted {result.inserted_enrichment_count} enrichment rows, "
                f"skipped {result.skipped_existing_count} existing rows."
            )
            print(
                f"Cached {result.cached_url_count} URLs; "
                f"placeholders written for {result.placeholder_count} bookmarks."
            )
            return

        if args.command == "export":
            try:
                result = export_markdown(
                    db_path=args.db_path,
                    vault_dir=args.vault_dir,
                )
            except ExportError as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(
                f"Exported {result.exported_note_count} Markdown notes to {args.vault_dir}."
            )
            for path in result.written_paths[:5]:
                print(f"- {path}")
            if len(result.written_paths) > 5:
                print(f"- ... and {len(result.written_paths) - 5} more")
            return

        if args.command == "topics":
            try:
                result = generate_topic_notes(
                    db_path=args.db_path,
                    vault_dir=args.vault_dir,
                )
            except TopicGenerationError as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(
                f"Generated {result.generated_note_count} topic notes in {args.vault_dir / 'topics'}."
            )
            for path in result.written_paths:
                print(f"- {path}")
            return

        if args.command == "metadata":
            try:
                result = generate_leadership_metadata(db_path=args.db_path)
            except MetadataError as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(
                f"Processed {result.processed_bookmark_count} bookmarks, "
                f"updated {result.inserted_metadata_count} leadership metadata rows, "
                f"skipped {result.skipped_existing_count} current rows."
            )
            if result.placeholder_count:
                print(
                    f"Placeholder metadata written for {result.placeholder_count} bookmarks."
                )
            return

        if args.command == "synthesize":
            if args.cadence != "weekly":
                print("Only weekly synthesis is currently supported.")
                raise SystemExit(1)
            try:
                result = generate_weekly_synthesis(
                    period_key=args.period,
                    db_path=args.db_path,
                    vault_dir=args.vault_dir,
                )
            except (SynthesisError, ExportError) as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(f"Generated weekly synthesis for {result.period_key}.")
            print(f"- {result.weekly_note_path}")
            print(f"- {result.latest_alias_path}")
            return

        if args.command == "collections":
            try:
                result = generate_collection_notes(
                    db_path=args.db_path,
                    vault_dir=args.vault_dir,
                    definitions_path=args.definitions_path,
                )
            except CollectionGenerationError as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(
                f"Generated {result.generated_note_count} curated collection notes in {args.vault_dir / 'collections'}."
            )
            for path in result.written_paths:
                print(f"- {path}")
            return

        if args.command == "export-stories":
            try:
                result = export_story_markdown(
                    db_path=args.db_path,
                    vault_dir=args.vault_dir,
                )
            except ExportError as exc:
                print(str(exc))
                raise SystemExit(1) from exc

            print(
                f"Exported {result.exported_note_count} story Markdown files to {args.vault_dir / 'stories'}."
            )
            for path in result.written_paths[:5]:
                print(f"- {path}")
            if len(result.written_paths) > 5:
                print(f"- ... and {len(result.written_paths) - 5} more")
            return

        if args.command == "sync":
            try:
                extract_result = extract_bookmarks(
                    raw_output_dir=args.raw_output_dir,
                    db_path=args.db_path,
                    chrome_profile_dir=args.chrome_profile_dir,
                    headless=args.headless,
                    bookmarks_url=args.bookmarks_url,
                    cdp_endpoint=getattr(args, "cdp_endpoint", None),
                )
                print(
                    f"Captured {extract_result.captured_payload_count} raw payloads, "
                    f"normalized {extract_result.normalized_record_count} records, "
                    f"inserted {extract_result.inserted_record_count} new rows."
                )
                print(f"Raw archive written to {extract_result.archive_path}")
                if extract_result.skipped_issues:
                    print(
                        f"Skipped {len(extract_result.skipped_issues)} malformed raw payloads."
                    )

                enrich_result = enrich_bookmarks(
                    db_path=args.db_path,
                    config_path=args.config_path,
                )
                print(
                    f"Processed {enrich_result.processed_bookmark_count} bookmarks, "
                    f"inserted {enrich_result.inserted_enrichment_count} enrichment rows, "
                    f"skipped {enrich_result.skipped_existing_count} existing rows."
                )
                print(
                    f"Cached {enrich_result.cached_url_count} URLs; "
                    f"placeholders written for {enrich_result.placeholder_count} bookmarks."
                )

                export_result = export_markdown(
                    db_path=args.db_path,
                    vault_dir=args.vault_dir,
                )
                print(
                    f"Exported {export_result.exported_note_count} Markdown notes to {args.vault_dir}."
                )
                for path in export_result.written_paths[:5]:
                    print(f"- {path}")
                if len(export_result.written_paths) > 5:
                    print(f"- ... and {len(export_result.written_paths) - 5} more")
            except (
                EmptyCaptureError,
                ExtractionError,
                EnrichmentError,
                ExportError,
            ) as exc:
                print(str(exc))
                raise SystemExit(1) from exc
            return

        raise SystemExit(1)
