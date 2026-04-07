"""
Normalization stage placeholder.
"""

from __future__ import annotations

from typing import Any, Iterable


def normalize_payloads(payloads: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize raw bookmark payloads into canonical records."""
    raise NotImplementedError("Bookmark normalization is planned for Phase 2.")
