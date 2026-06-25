#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path
from typing import Any
import sys
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "runtime" / "ib-pitchdeck-agent-industry-section" / "scripts"
ROLE_DIR = SCRIPT_DIR / "material-intake"
LIB_DIR = SCRIPT_DIR / "_lib"
for path in (SCRIPT_DIR, ROLE_DIR, LIB_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import ingest_materials as ingest_module  # noqa: E402
from ingest_materials import ingest_materials  # noqa: E402


def _write_minimal_pdf(path: Path) -> None:
    payload = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 595 842] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT (PDF extraction smoke) Tj ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000010 00000 n 
0000000062 00000 n 
0000000121 00000 n 
0000000218 00000 n 
trailer
<< /Root 1 0 R /Size 5 >>
startxref
333
%%EOF"""
    path.write_bytes(payload)


def _write_minimal_xlsx(path: Path) -> None:
    sheet_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>Industry</t></is></c><c r="B1" t="inlineStr"><is><t>DataX</t></is></c></row>
    <row r="2"><c r="A2" t="inlineStr"><is><t>Revenue</t></is></c><c r="B2"><v>100</v></c></row>
  </sheetData>
</worksheet>"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>"""
    content_types_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("xl/workbook.xml", "<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\"/>")
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", rels_xml)


def _write_minimal_pptx(path: Path) -> None:
    slide_xml = """<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
       xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:txBody>
          <a:bodyPr/>
          <a:lstStyle/>
          <a:p>
            <a:r>
              <a:t>PPTX extraction smoke</a:t>
            </a:r>
          </a:p>
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("ppt/slides/slide1.xml", slide_xml)


class _MockResponse:
    class _MockHeaders:
        def get_content_charset(self, _fallback: str = "utf-8") -> str:
            return "utf-8"

    def __init__(self, body: bytes):
        self.body = body
        self.headers = self._MockHeaders()

    def __enter__(self):
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def read(self) -> bytes:
        return self.body

    def get_content_charset(self, fallback: str = "utf-8") -> str:
        return "utf-8"


def test_ingest_materials_end_to_end_from_multiple_sources(tmp_path: Path) -> None:
    manifest_path = tmp_path / "artifacts" / "material_manifest.json"
    extracts_path = tmp_path / "artifacts" / "material_extracts.json"
    classification_path = tmp_path / "artifacts" / "source_classification.json"

    _write_minimal_pdf(tmp_path / "sample.pdf")
    _write_minimal_pptx(tmp_path / "sample.pptx")
    _write_minimal_xlsx(tmp_path / "sample.xlsx")
    html_body = (
        "<html><body><h1>URL Source</h1><p>This is URL extraction smoke.</p></body></html>"
    ).encode("utf-8")

    with patch.object(ingest_module, "urlopen", return_value=_MockResponse(html_body)):
        manifest, extracts, source_classification = ingest_materials(
            brief_text="Industry brief includes customer segment and geography context.",
            files=[str(tmp_path / "sample.pdf"), str(tmp_path / "sample.pptx"), str(tmp_path / "sample.xlsx")],
            urls=["https://example.local/source/index.html"],
            default_file_source_type="project_specific_material",
            default_url_source_type="manual_url_ingestion",
            output_material_manifest=manifest_path,
            output_material_extracts=extracts_path,
            output_source_classification=classification_path,
            dry_run=False,
        )

    assert manifest_path.exists()
    assert extracts_path.exists()
    assert classification_path.exists()

    materials = manifest["materials"]
    extract_entries = extracts["extracts"]
    assert len(materials) == 5
    assert len(extract_entries) == 5

    by_id = {m["material_id"]: m for m in materials}
    inline_brief = next(m for m in materials if m["file_path_or_url"] == "inline_user_text")
    assert inline_brief["source_type"] == "project_specific_material"
    for material in materials:
        assert material["source_type"] in {
            "project_specific_material",
            "manual_url_ingestion",
            "user_curated_industry_report",
        }
        assert material["material_kind"] in {"text", "url", "file"}
        assert material["file_path_or_url"]
        assert material["material_id"] in by_id

    for entry in extract_entries:
        assert entry["material_id"] in by_id
        assert Path(entry["extracted_text_path"]).exists()
        assert entry["extracted_text_path"].startswith(str(tmp_path))
        assert entry["extraction_status"] == "complete"
        assert isinstance(entry["can_be_used_as_evidence"], bool)
        assert entry["extraction_limitations"] == "none"

    source_classification_payload = source_classification["materials"]
    assert len(source_classification_payload) == len(materials)
    assert all(item.get("source_hash") is not None for item in source_classification_payload)
    assert all(item.get("file_path_or_url") for item in source_classification_payload)

    assert {m["material_id"] for m in materials} == {e["material_id"] for e in extract_entries}

    previews = [entry.get("evidence_snapshot", "") for entry in extract_entries]
    assert any("PDF extraction smoke" in value for value in previews)
    assert any("PPTX extraction smoke" in value for value in previews)
    assert any("Industry" in value for value in previews)
    assert any("URL extraction smoke" in value for value in previews)


def test_ingest_materials_start_brief_runs_from_arbitrary_cwd_without_pythonpath(tmp_path: Path) -> None:
    script = SCRIPT_DIR / "material-intake" / "ingest_materials.py"
    run_dir = tmp_path / "work" / "runs" / "sample_case"
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "start-brief",
            "--case-name",
            "sample_case",
            "--run-dir",
            str(run_dir),
            "--brief-text",
            "A short Chinese base makeup brand control-sale brief.",
            "--industry",
            "base makeup",
            "--geography",
            "China",
        ],
        cwd=str(tmp_path),
        text=True,
        capture_output=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["run_dir"] == str(run_dir.resolve())
    assert (run_dir / "input_card.json").exists()
    assert (run_dir / "artifacts" / "material_manifest.json").exists()
    assert (run_dir / "artifacts" / "material_extracts.json").exists()
