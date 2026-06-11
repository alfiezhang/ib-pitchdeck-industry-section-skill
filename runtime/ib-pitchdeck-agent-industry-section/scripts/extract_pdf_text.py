#!/usr/bin/env python3
"""Extract plain text from a PDF file using optional in-repo parsers.

This module intentionally avoids heavy binary dependencies so it can run in a
minimal runtime environment. If a richer parser is available, it uses that
first; otherwise it falls back to a conservative text-stream heuristic.
"""

from __future__ import annotations

import argparse
import re
import zlib
from pathlib import Path
from typing import Any

from material_intake_common import clean_text_block


TET = re.compile(rb"\((.*?)\)")
STREAM_TEXT_RE = re.compile(rb"BT(.*?)ET", re.S)
STREAM_FILTER_RE = re.compile(rb"/Filter\s*/([A-Za-z0-9]+)")
ASCII_HEX_RE = re.compile(r"#[0-9A-Fa-f]{2}")


def _decode_hex(encoded: str) -> str:
    out_chars: list[str] = []
    for match in ASCII_HEX_RE.finditer(encoded):
        pass
    text = encoded.replace("\\", "")
    chunks = text.split("#")
    if len(chunks) == 1:
        return text
    decoded = [chunks[0]]
    for chunk in chunks[1:]:
        pair = chunk[:2]
        rest = chunk[2:]
        if len(pair) == 2 and re.fullmatch(r"[0-9A-Fa-f]{2}", pair):
            decoded.append(chr(int(pair, 16)))
            decoded.append(rest)
        else:
            decoded.append("#" + chunk)
    return "".join(decoded)


def _decode_pdf_text_bytes(raw: bytes) -> str:
    text_chunks: list[str] = []
    for segment in STREAM_TEXT_RE.finditer(raw):
        block = segment.group(0)
        data = block
        if b"/Filter" in data:
            # Handle simple literal text streams and FlateDecode fallback.
            filter_match = STREAM_FILTER_RE.search(data)
            if filter_match and filter_match.group(1).lower() == b"flatedecode":
                start = data.find(b"stream") + 6
                end = data.find(b"endstream")
                if start > 6 and end > start:
                    compressed = data[start:end]
                    compressed = compressed.strip(b"\r\n")
                    try:
                        data = zlib.decompress(compressed)
                    except Exception:
                        pass
        for raw_text in TET.finditer(data):
            raw_fragment = raw_text.group(1)
            try:
                text_chunks.append(raw_fragment.decode("latin1", errors="ignore"))
            except Exception:
                text_chunks.append(str(raw_fragment))
    if text_chunks:
        return clean_text_block("\n".join(text_chunks))

    # Conservative fallback: extract printable bytes sequence from whole file
    fallback = raw.decode("latin1", errors="ignore")
    return clean_text_block(fallback)


def extract_pdf_text(pdf_path: str, output_path: str | None = None) -> tuple[str, list[str], int]:
    warnings: list[str] = []
    source = Path(pdf_path)
    if not source.exists():
        return "", [f"source path not found: {source}"], 1

    # If pypdf is installed at runtime, use it; we do not require it.
    try:
        from PyPDF2 import PdfReader  # type: ignore

        reader = PdfReader(str(source))
        text = []
        for page in reader.pages:
            try:
                value = page.extract_text() or ""
            except Exception:
                continue
            if value:
                text.append(value)
        text_value = clean_text_block("\n".join(text))
        if not text_value:
            raise RuntimeError("PyPDF2 returned empty text")
        if output_path:
            Path(output_path).write_text(text_value, encoding="utf-8")
        return text_value, warnings, 0
    except Exception:
        pass

    raw = source.read_bytes()
    text_value = _decode_pdf_text_bytes(raw)
    if not text_value.strip():
        warnings.append("PDF text extraction fallback found no readable text stream; manual review required.")
        return "", warnings, 1
    if output_path:
        Path(output_path).write_text(text_value, encoding="utf-8")
    return text_value, warnings, 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-path", required=True)
    parser.add_argument("--output-text", required=True)
    parser.add_argument("--material-id", default="")
    args = parser.parse_args()
    text_value, warnings, status = extract_pdf_text(args.pdf_path, args.output_text)
    if status != 0:
        payload = {
            "schema_version": "pdf_extraction_v1",
            "status": "failed",
            "material_id": args.material_id,
            "source_path": args.pdf_path,
            "extracted_text_path": args.output_text,
            "text": "",
            "warnings": warnings,
        }
        print(payload)
        return 1
    payload = {
        "schema_version": "pdf_extraction_v1",
        "status": "complete",
        "material_id": args.material_id,
        "source_path": args.pdf_path,
        "extracted_text_path": args.output_text,
        "text_length": len(text_value),
        "text": text_value,
        "warnings": warnings,
    }
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
