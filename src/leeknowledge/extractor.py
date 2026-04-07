"""
Extraction stage placeholder.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_bookmarks(raw_output_dir: Path) -> list[dict[str, Any]]:
    """Extract bookmarks from X and persist the raw payload."""
    raise NotImplementedError("Bookmark extraction is planned for Phase 2.")
