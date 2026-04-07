"""
CLI scaffold for the leeKnowledge pipeline.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from leeknowledge import __version__
from leeknowledge.db import initialize_database

APP_NAME = "leeknowledge"
APP_DESCRIPTION = (
    "Local-first X bookmark pipeline: extract, enrich, and export to Markdown."
)


def _not_implemented(command: str) -> str:
    return (
        f"`{command}` is scaffolded but not implemented yet. "
        "Phase 2+ will replace this placeholder with the real pipeline stage."
    )


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

    def _init_state() -> Path:
        db_path = initialize_database()
        typer.echo(f"Database ready at {db_path}")
        return db_path

    @app.command()
    def extract() -> None:
        """Extract bookmarks from X and normalize them into SQLite."""
        _init_state()
        typer.echo(_not_implemented("extract"))
        raise typer.Exit(code=1)

    @app.command()
    def enrich() -> None:
        """Enrich unprocessed bookmarks via the local LLM router."""
        _init_state()
        typer.echo(_not_implemented("enrich"))
        raise typer.Exit(code=1)

    @app.command()
    def export() -> None:
        """Export bookmarks from SQLite into Markdown notes."""
        _init_state()
        typer.echo(_not_implemented("export"))
        raise typer.Exit(code=1)

    @app.command()
    def sync() -> None:
        """Run extract, enrich, and export in sequence."""
        _init_state()
        typer.echo(_not_implemented("sync"))
        raise typer.Exit(code=1)

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
        for name, help_text in {
            "extract": "Extract bookmarks from X into SQLite.",
            "enrich": "Enrich bookmarks via the local LLM router.",
            "export": "Export bookmarks to Markdown.",
            "sync": "Run extract, enrich, and export in sequence.",
            "db": "Initialize the local SQLite database and exit.",
        }.items():
            subparsers.add_parser(name, help=help_text)

        args = parser.parse_args()
        if args.command is None:
            parser.print_help()
            return

        db_path = initialize_database()
        print(f"Database ready at {db_path}")
        if args.command == "db":
            return

        print(_not_implemented(args.command))
        raise SystemExit(1)
