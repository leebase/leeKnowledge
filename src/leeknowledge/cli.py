"""
CLI scaffold for the leeKnowledge pipeline.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from leeknowledge import __version__
from leeknowledge.db import APP_DB_PATH, initialize_database
from leeknowledge.enricher import EnrichmentError, EnrichmentRunResult, enrich_bookmarks
from leeknowledge.exporter import ExportError, ExportRunResult, export_markdown
from leeknowledge.extractor import (
    EmptyCaptureError,
    ExtractionError,
    ExtractionRunResult,
    extract_bookmarks,
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
) -> ExtractionRunResult:
    return extract_bookmarks(
        raw_output_dir=raw_output_dir,
        db_path=db_path,
        chrome_profile_dir=chrome_profile_dir,
        headless=headless,
    )


def run_enrich(db_path: Path, config_path: Path) -> EnrichmentRunResult:
    return enrich_bookmarks(db_path=db_path, config_path=config_path)


def run_export(db_path: Path, vault_dir: Path) -> ExportRunResult:
    return export_markdown(db_path=db_path, vault_dir=vault_dir)


def run_sync(
    raw_output_dir: Path,
    db_path: Path,
    chrome_profile_dir: Path | None,
    headless: bool,
    config_path: Path,
    vault_dir: Path,
) -> tuple[ExtractionRunResult, EnrichmentRunResult, ExportRunResult]:
    extract_result = run_extract(
        raw_output_dir=raw_output_dir,
        db_path=db_path,
        chrome_profile_dir=chrome_profile_dir,
        headless=headless,
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
    ) -> ExtractionRunResult:
        result = extract_bookmarks(
            raw_output_dir=raw_output_dir,
            db_path=db_path,
            chrome_profile_dir=chrome_profile_dir,
            headless=headless,
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
    ) -> None:
        """Extract bookmarks from X and normalize them into SQLite."""

        try:
            _run_extract(raw_output_dir, db_path, chrome_profile_dir, headless)
        except EmptyCaptureError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc
        except ExtractionError as exc:
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

    def _run_sync(
        raw_output_dir: Path,
        db_path: Path,
        chrome_profile_dir: Path | None,
        headless: bool,
        config_path: Path,
        vault_dir: Path,
    ) -> tuple[ExtractionRunResult, EnrichmentRunResult, ExportRunResult]:
        extract_result = _run_extract(
            raw_output_dir=raw_output_dir,
            db_path=db_path,
            chrome_profile_dir=chrome_profile_dir,
            headless=headless,
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
                config_path=config_path,
                vault_dir=vault_dir,
            )
        except (EmptyCaptureError, ExtractionError, EnrichmentError, ExportError) as exc:
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
        extract_parser.add_argument("--chrome-profile-dir", type=Path)
        extract_parser.add_argument("--headless", action="store_true")

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
        sync_parser.add_argument("--headless", action="store_true")
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

        if args.command == "sync":
            try:
                extract_result = extract_bookmarks(
                    raw_output_dir=args.raw_output_dir,
                    db_path=args.db_path,
                    chrome_profile_dir=args.chrome_profile_dir,
                    headless=args.headless,
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
            except (EmptyCaptureError, ExtractionError, EnrichmentError, ExportError) as exc:
                print(str(exc))
                raise SystemExit(1) from exc
            return

        raise SystemExit(1)
