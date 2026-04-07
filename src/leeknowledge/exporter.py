"""
Export stage placeholder.
"""

from __future__ import annotations

from pathlib import Path


def export_markdown(db_path: Path, vault_dir: Path) -> int:
    """Export bookmarks from SQLite into Markdown notes."""
    raise NotImplementedError("Markdown export is planned for Phase 4.")
