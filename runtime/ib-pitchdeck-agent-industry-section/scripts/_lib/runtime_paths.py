#!/usr/bin/env python3
"""Runtime path discovery helpers."""

from __future__ import annotations

from pathlib import Path


def find_runtime_root(start: str | Path) -> Path:
    """Locate the runtime root that owns configs/ and scripts/.

    Validators live at different nesting depths, so parent-count assumptions are
    fragile. The runtime root is the nearest ancestor with both directories.
    """

    path = Path(start).resolve()
    anchors = [path if path.is_dir() else path.parent, *path.parents]
    for parent in anchors:
        if (parent / "configs").is_dir() and (parent / "scripts").is_dir():
            return parent
    raise RuntimeError(f"Cannot locate runtime root from {start}")
