"""Shared JSON loading helpers with smart-quote diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SMART_QUOTES = {
    "\u201c": "left double smart quote",
    "\u201d": "right double smart quote",
    "\u2018": "left single smart quote",
    "\u2019": "right single smart quote",
    "\uff02": "fullwidth double quote",
    "\uff07": "fullwidth single quote",
}


def smart_quote_locations(text: str) -> list[dict[str, Any]]:
    locations: list[dict[str, Any]] = []
    line = 1
    col = 1
    for idx, char in enumerate(text):
        if char in SMART_QUOTES:
            locations.append(
                {
                    "char": char,
                    "name": SMART_QUOTES[char],
                    "line": line,
                    "column": col,
                    "offset": idx,
                }
            )
        if char == "\n":
            line += 1
            col = 1
        else:
            col += 1
    return locations


def json_error_message(path: Path, exc: json.JSONDecodeError, text: str) -> str:
    locations = smart_quote_locations(text)
    message = f"Invalid JSON in {path}: {exc}"
    if locations:
        first = locations[0]
        message += (
            f"; detected smart/Chinese quote {first['char']!r} "
            f"({first['name']}) at line {first['line']}, column {first['column']}. "
            'JSON keys and string delimiters must use ASCII double quotes: ".'
        )
    return message


def load_json_file(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"JSON file not found: {path}") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(json_error_message(path, exc, text)) from exc
