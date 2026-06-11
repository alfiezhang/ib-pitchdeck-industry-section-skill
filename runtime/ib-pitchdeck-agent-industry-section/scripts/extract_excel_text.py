#!/usr/bin/env python3
"""Extract readable text from Excel spreadsheets (CSV / XLS / XLSX).

This module keeps dependencies minimal and supports CSV + XLSX via built-in zip/xml
parsing. XLS format is unsupported and reported explicitly for manual follow-up.
"""

from __future__ import annotations

import argparse
import csv
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from material_intake_common import read_text_file


def _read_csv_text(path: Path) -> str:
    lines: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh)
        for row in reader:
            if row:
                line = " | ".join([cell.strip() for cell in row if str(cell).strip()])
                if line:
                    lines.append(line)
    return "\n".join(lines)


def _read_xlsx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            shared_strings = []
            if "xl/sharedStrings.xml" in names:
                shared_xml = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                for item in shared_xml.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"):
                    shared_strings.append("".join(item.itertext()).strip())

            ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            sheets = [name for name in names if name.startswith("xl/worksheets/") and name.endswith(".xml")]
            if not sheets:
                return ""
            rows: list[str] = []
            for sheet_name in sorted(sheets):
                sheet = ET.fromstring(zf.read(sheet_name))
                for row in sheet.findall(".//ns:sheetData/ns:row", ns):
                    values: list[str] = []
                    for cell in row.findall("ns:c", ns):
                        type_attr = cell.attrib.get("t", "")
                        if type_attr == "inlineStr":
                            inline_text = " ".join(
                                "".join(node.itertext()).strip()
                                for node in cell.findall(".//ns:is//ns:t", ns)
                                if "".join(node.itertext()).strip()
                            )
                            if inline_text:
                                values.append(inline_text.strip())
                            continue

                        value_node = cell.find("ns:v", ns)
                        if value_node is None:
                            continue
                        value = value_node.text or ""
                        if type_attr == "s":
                            try:
                                index = int(value)
                                value = shared_strings[index]
                            except Exception:
                                value = value
                        values.append(str(value).strip())
                    line = " | ".join([item for item in values if item])
                    if line:
                        rows.append(line)
            return "\n".join(rows)
    except Exception:
        return ""


def extract_excel_text(excel_path: str, output_path: str | None = None, material_id: str = "") -> tuple[str, list[str], int]:
    source = Path(excel_path)
    if not source.exists():
        return "", [f"source path not found: {source}"], 1
    suffix = source.suffix.lower()
    if suffix == ".csv":
        text_value = _read_csv_text(source)
    elif suffix in {".xls", ".xlsx"}:
        if suffix == ".xls":
            return "", ["xls binary format is unsupported without external dependencies"], 1
        text_value = _read_xlsx_text(source)
    else:
        # Best-effort: attempt to decode as text if a misnamed CSV/xls-style file lands here.
        text_value = read_text_file(source)
        if not text_value.strip():
            return "", [f"unsupported file extension for structured extract: {suffix}"], 1

    if not text_value.strip():
        return "", ["no readable table rows extracted from file"], 1

    if output_path:
        Path(output_path).write_text(text_value, encoding="utf-8")
    return text_value, [], 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel-path", required=True)
    parser.add_argument("--output-text", required=True)
    parser.add_argument("--material-id", default="")
    args = parser.parse_args()
    text_value, warnings, status = extract_excel_text(args.excel_path, args.output_text, args.material_id)
    if status != 0:
        payload = {
            "schema_version": "excel_extraction_v1",
            "status": "failed",
            "material_id": args.material_id,
            "source_path": args.excel_path,
            "extracted_text_path": args.output_text,
            "text": "",
            "warnings": warnings,
        }
        print(payload)
        return 1
    payload = {
        "schema_version": "excel_extraction_v1",
        "status": "complete",
        "material_id": args.material_id,
        "source_path": args.excel_path,
        "extracted_text_path": args.output_text,
        "text_length": len(text_value),
        "text": text_value,
        "warnings": warnings,
    }
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
