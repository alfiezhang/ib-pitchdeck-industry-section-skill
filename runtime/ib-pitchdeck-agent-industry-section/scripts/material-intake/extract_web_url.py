#!/usr/bin/env python3
"""Fetch and extract readable text from a URL."""

from __future__ import annotations

# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'configs').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted(_p for _p in (_IB_RUNTIME_ROOT / 'scripts').iterdir() if _p.is_dir())
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'scripts' / 'qc' / 'validators').glob('*'))
_IB_IMPORT_PATHS = [str(_IB_ROLE_SCRIPT_DIR)]
for _ib_dir in [*_IB_ROLE_SCRIPT_DIRS, *_IB_QC_VALIDATOR_DIRS]:
    _ib_text = str(_ib_dir)
    if _ib_text not in _IB_IMPORT_PATHS:
        _IB_IMPORT_PATHS.append(_ib_text)
_IB_IMPORT_PATHS.append(str(_IB_SHARED_SCRIPT_DIR))
for _ib_path in list(_IB_IMPORT_PATHS):
    if _ib_path in _ib_sys.path:
        _ib_sys.path.remove(_ib_path)
for _ib_path in reversed(_IB_IMPORT_PATHS):
    _ib_sys.path.insert(0, _ib_path)

import argparse
import html
import html.parser
import re
import urllib.error
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from material_intake_common import clean_text_block


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self._chunks.append(data)

    def text(self) -> str:
        return clean_text_block(html.unescape(" ".join(self._chunks)))


def _strip_scripts(html_text: str) -> str:
    html_text = re.sub(r"<script[\s\S]*?</script>", " ", html_text, flags=re.IGNORECASE)
    html_text = re.sub(r"<style[\s\S]*?</style>", " ", html_text, flags=re.IGNORECASE)
    return html_text


def extract_web_url(url: str, output_path: str | None = None, material_id: str = "") -> tuple[str, list[str], int]:
    req = Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; ib-pitchdeck-agent/1.0)"},
    )
    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read()
            mime = response.headers.get_content_charset() or "utf-8"
    except urllib.error.URLError as exc:
        return "", [f"url fetch failed: {exc}"], 1
    except Exception as exc:
        return "", [f"unexpected fetch error: {exc}"], 1

    text_content = ""
    html_text: str = ""
    try:
        html_text = raw.decode(mime, errors="replace")
    except Exception:
        html_text = raw.decode("utf-8", errors="replace")
    if "<html" in html_text.lower():
        parser = _TextExtractor()
        parser.feed(_strip_scripts(html_text))
        parser.close()
        text_content = parser.text()
    else:
        text_content = html_text

    if not text_content.strip():
        return "", ["url content empty or non-text"], 1

    cleaned = clean_text_block(text_content)
    if output_path:
        Path(output_path).write_text(cleaned, encoding="utf-8")
    return cleaned, [], 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--output-text", required=True)
    parser.add_argument("--material-id", default="")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()
    _, _ = args.timeout, 0
    text_value, warnings, status = extract_web_url(args.url, args.output_text, args.material_id)
    if status != 0:
        payload = {
            "schema_version": "url_extraction_v1",
            "status": "failed",
            "material_id": args.material_id,
            "source_path": args.url,
            "extracted_text_path": args.output_text,
            "text": "",
            "warnings": warnings,
        }
        print(payload)
        return 1
    payload = {
        "schema_version": "url_extraction_v1",
        "status": "complete",
        "material_id": args.material_id,
        "source_path": args.url,
        "extracted_text_path": args.output_text,
        "text_length": len(text_value),
        "text": text_value,
        "warnings": warnings,
    }
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
