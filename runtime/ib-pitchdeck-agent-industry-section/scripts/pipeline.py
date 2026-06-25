#!/usr/bin/env python3
"""Python orchestrator for deterministic IB industry-section run steps.

This CLI operates on one existing run directory. It does not perform research,
does not write page judgments, and does not create a new attempt unless the
caller explicitly creates one outside this script. Its purpose is to keep
attempt management, validation orchestration, PPT rendering, final delivery,
and quality summary in one predictable Python entrypoint.
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from zipfile import ZipFile
from xml.sax.saxutils import escape

SCRIPT_DIR = Path(__file__).resolve().parent
LIB_DIR = SCRIPT_DIR / "_lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))
QC_DIR = SCRIPT_DIR / "qc"
if str(QC_DIR) not in sys.path:
    sys.path.insert(0, str(QC_DIR))

from renderer_compile_utils import build_token_source, compile_banker_page_pack
from validate_artifact import (
    ARTIFACT_PATHS,
    VALIDATION_OUTPUTS,
    banker_page_pack_template_diagnostics,
    validate_artifact as run_artifact_validation,
)
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _layout_config_paths(path: Path | str | None = None) -> dict[str, Path]:
    config_path = Path(path or ROOT_DIR / "configs" / "layout_config.json")
    if not config_path.is_absolute():
        candidate = Path.cwd() / config_path
        config_path = candidate if candidate.exists() else ROOT_DIR / config_path
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "layout_config_v1":
        raise ValueError(f"{config_path} must use schema_version layout_config_v1")
    files = config.get("files")
    if not isinstance(files, dict):
        raise ValueError(f"{config_path} must define object field 'files'")
    resolved: dict[str, Path] = {}
    for key, raw in files.items():
        candidate = Path(str(raw))
        resolved[key] = candidate if candidate.is_absolute() else ROOT_DIR / candidate
    return resolved


def _internal_script(relative_path: str) -> Path:
    return ROOT_DIR / "scripts" / relative_path

# --- Tool integrity: do not modify this file during a run ---
_TOOL_SOURCE_REPO = ROOT_DIR.parent.parent  # expected: <repo>/runtime/ib-pitchdeck-agent-industry-section
_INTEGRITY_SENTINEL = "pipeline.py is a read-only tool file; repair upstream artifacts, not this script."  # noqa: E501
TEMPLATE = ROOT_DIR / "assets" / "industry_section_template_master.pptx"
LAYOUT_PATHS = _layout_config_paths()
PPT_MAPPING = LAYOUT_PATHS["ppt_mapping"]
RENDER_LAYOUTS = LAYOUT_PATHS["render_layouts"]
TEMPLATE_PROFILE = LAYOUT_PATHS["template_profile"]

FILLED_PPT = "industry_section_filled.pptx"
CLEAN_PPT = "industry_section_filled_clean.pptx"
FAILURE_MEMORY = "artifacts/failure_memory.jsonl"
TOKEN_PATTERN = re.compile(r"\{\{[^{}]+\}\}")
PYTHON_COMMAND_TEMPLATE = "$PYTHON_CMD"
PPT_PRESENTATION_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
PPT_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PPT_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DRAWINGML_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
ET.register_namespace("r", PPT_REL_NS)
ET.register_namespace("p", PPT_PRESENTATION_NS)
ET.register_namespace("", PPT_PACKAGE_REL_NS)
REPLACEMENT_TOP_LEVEL_FIELDS = {
    "selected_page_type",
    "slide_title",
    "main_takeaway",
    "chart_title",
    "source_footer",
    "speaker_note",
}
BULLET_PREFIX = "• "
PARAGRAPH_XML_RE = re.compile(r"(<a:p\b.*?</a:p>)", re.DOTALL)
TEXT_RUN_RE = re.compile(r"(<a:t>)(.*?)(</a:t>)", re.DOTALL)
RICH_TEXT_TAG_RE = re.compile(r"\[\[(\/?)(b|hl)\]\]")
HIGHLIGHT_COLOR = "E85D04"
REQUIRED_IMPORTS = [
    {"module": "pptx", "package": "python-pptx"},
    {"module": "lxml.etree", "package": "lxml"},
]
SEARCH_MODULE_GROUPS = {
    "tavily": ["tavily"],
    "duckduckgo": ["ddgs", "duckduckgo_search"],
    "searxng": [],
}
SEARXNG_ENV_VARS = ("SEARXNG_BASE_URL", "SEARXNG_URL", "SEARXNG_ENDPOINT")
PDF_EXTRACTION_MODULES = {"pdfplumber": "pdfplumber", "pypdf": "pypdf"}
PDF_EXTRACTION_COMMANDS = ("pdftotext",)
MAIN_STATUS_PATH = [
    "input_card",
    "material_extracts",
    "industry_scope_pack",
    "formal_search_plan",
    "executable_search_batch",
    "formal_research_execution",
    "source_archive",
    "research_evidence_db",
    "research_pack",
    "template_registry",
    "banker_page_pack",
    "deck_blueprint",
    "page_evidence_contract",
    "renderer_spec",
    "pre_ppt",
    "replacement_dict",
    "filled_ppt",
    "final_delivery",
]
BUILD_HINTS = {
    "material_extracts": "scripts/pipeline.py start-brief",
    "formal_search_plan": "scripts/pipeline.py research-prepare",
    "executable_search_batch": "LLM Query Author edits artifacts/executable_search_batch.json",
    "formal_research_execution": "scripts/pipeline.py research-compile",
    "source_archive": "scripts/pipeline.py research-compile",
    "research_evidence_db": "scripts/pipeline.py evidence-build, then Knowledge LLM authoring",
    "research_pack": "scripts/pipeline.py evidence-export",
    "template_registry": "scripts/pipeline.py template-registry",
    "banker_page_pack": "Generation LLM authors banker_page_pack.json",
    "deck_blueprint": "scripts/pipeline.py compile",
    "page_evidence_contract": "scripts/pipeline.py compile",
    "renderer_spec": "scripts/pipeline.py compile",
    "replacement_dict": "scripts/pipeline.py render",
    "filled_ppt": "scripts/pipeline.py render",
    "final_delivery": "scripts/pipeline.py validate --artifact final_delivery",
}


class PipelineError(RuntimeError):
    pass


def _json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise PipelineError(f"Failed to decode JSON file as UTF-8: {path}. {exc}") from exc
    except OSError as exc:
        raise PipelineError(f"Failed to read JSON file: {path}. {exc}") from exc
    except JSONDecodeError as exc:
        raise PipelineError(f"Invalid JSON in file: {path}. {exc}") from exc


def _load_json_lenient(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def artifact_path(run_dir: Path, artifact: str) -> Path:
    return run_dir / ARTIFACT_PATHS[artifact]


def validation_path(run_dir: Path, artifact: str) -> Path:
    return run_dir / VALIDATION_OUTPUTS.get(artifact, f"artifacts/{artifact}_validation.json")


def validate_command(run_dir: Path, artifact: str) -> str:
    return (
        f"{PYTHON_COMMAND_TEMPLATE} scripts/pipeline.py validate "
        f"--artifact {artifact} --run-dir {run_dir} --output {validation_path(run_dir, artifact)}"
    )


def artifact_status(run_dir: Path, artifact: str) -> dict[str, Any]:
    path = artifact_path(run_dir, artifact)
    validation = validation_path(run_dir, artifact)
    exists = path.exists()
    validation_payload = _load_json_lenient(validation) if validation.exists() else {}
    is_valid = validation_payload.get("is_valid")
    if not exists:
        state = "missing"
    elif is_valid is False:
        state = "invalid"
    elif is_valid is True:
        state = "valid"
    else:
        state = "unvalidated"
    return {
        "artifact": artifact,
        "path": str(path),
        "exists": exists,
        "validation": str(validation),
        "validation_exists": validation.exists(),
        "state": state,
        "error_count": validation_payload.get("error_count", 0),
        "errors": validation_payload.get("errors", []),
        "validate_command": validate_command(run_dir, artifact),
        "builder_or_owner_action": BUILD_HINTS.get(artifact, ""),
    }


def build_run_status(run_dir: Path) -> dict[str, Any]:
    rows = [artifact_status(run_dir, artifact) for artifact in MAIN_STATUS_PATH]
    current = next((row for row in rows if row["state"] in {"missing", "invalid", "unvalidated"}), rows[-1] if rows else {})
    commands: list[str] = []
    if current:
        artifact = str(current.get("artifact") or "")
        hint = str(current.get("builder_or_owner_action") or "")
        if hint and hint.endswith(".py"):
            commands.append(f"{PYTHON_COMMAND_TEMPLATE} {hint} --run-dir {run_dir}")
        commands.append(str(current.get("validate_command") or ""))
    return {
        "schema_version": "status_report_v1",
        "run_dir": str(run_dir),
        "status": "complete" if all(row["state"] == "valid" for row in rows) else "needs_work",
        "current_stage": current.get("artifact", ""),
        "current_state": current.get("state", ""),
        "current_owner_action": current.get("builder_or_owner_action", ""),
        "recommended_next_commands": [command for command in commands if command],
        "artifacts": rows,
        "policy": "mechanical_status_only_llm_owns_content_quality",
    }


def write_status_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# Status Report",
        "",
        f"- Run: `{report.get('run_dir')}`",
        f"- Status: `{report.get('status')}`",
        f"- Current stage: `{report.get('current_stage')}`",
        "",
        "## Artifact States",
        "",
    ]
    for row in report.get("artifacts", []):
        lines.append(f"- `{row['artifact']}`: {row['state']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_status_json(report: dict[str, Any], path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _collect_template_tokens(pptx_path: Path) -> dict[str, list[str]]:
    token_locations: dict[str, list[str]] = defaultdict(list)
    try:
        archive = ZipFile(pptx_path)
    except FileNotFoundError as exc:
        raise PipelineError(f"PPTX template not found: {pptx_path}") from exc
    except Exception as exc:
        raise PipelineError(f"Failed to open PPTX template {pptx_path}: {exc}") from exc
    with archive:
        for name in archive.namelist():
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            root = ET.fromstring(archive.read(name))
            for elem in root.iter():
                if not elem.tag.endswith("}p"):
                    continue
                paragraph_text = "".join(
                    child.text for child in elem.iter() if child.tag.endswith("}t") and child.text
                )
                for token in TOKEN_PATTERN.findall(paragraph_text):
                    token_locations[token].append(name)
    return dict(token_locations)


def _collect_mapping_tokens(mapping: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tokens: dict[str, dict[str, Any]] = {}
    for slide in mapping.get("slides", []):
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        slide_key = slide.get("slide_key")
        if "tokens" in slide:
            for token in slide.get("tokens", []):
                if not isinstance(token, dict):
                    continue
                placeholder = str(token.get("placeholder") or "").strip()
                if placeholder:
                    tokens[placeholder] = {
                        "slide_no": slide_no,
                        "slide_key": slide_key,
                        "field_name": token.get("field_name", ""),
                        "selected_page_type": slide.get("selected_page_type", ""),
                        "variant_key": "",
                    }
            continue
        variants = slide.get("controlled_variants") if isinstance(slide.get("controlled_variants"), dict) else {}
        for page_type, variant in variants.items():
            if not isinstance(variant, dict):
                continue
            for token in variant.get("tokens", []):
                if not isinstance(token, dict):
                    continue
                placeholder = str(token.get("placeholder") or "").strip()
                if placeholder:
                    tokens[placeholder] = {
                        "slide_no": slide_no,
                        "slide_key": slide_key,
                        "field_name": token.get("field_name", ""),
                        "selected_page_type": page_type,
                        "variant_key": variant.get("variant_key", ""),
                    }
    return tokens


def _normalize_replacement_value(value: Any) -> str:
    return html.unescape(str(value))


def _ensure_paragraph_properties(paragraph: ET.Element) -> ET.Element:
    properties = paragraph.find(f"{{{DRAWINGML_NS}}}pPr")
    if properties is None:
        properties = ET.Element(f"{{{DRAWINGML_NS}}}pPr")
        paragraph.insert(0, properties)
    return properties


def _apply_bullet_properties(paragraph: ET.Element) -> None:
    properties = _ensure_paragraph_properties(paragraph)
    properties.set("marL", "228600")
    properties.set("indent", "-152400")
    for tag in ("buNone", "buAutoNum", "buBlip", "buChar"):
        for child in list(properties.findall(f"{{{DRAWINGML_NS}}}{tag}")):
            properties.remove(child)
    ET.SubElement(properties, f"{{{DRAWINGML_NS}}}buChar", {"char": "•"})


def _parse_rich_text_segments(text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    state = {"b": 0, "hl": 0}
    cursor = 0
    for match in RICH_TEXT_TAG_RE.finditer(text):
        if match.start() > cursor:
            segments.append(
                {
                    "text": text[cursor:match.start()],
                    "bold": state["b"] > 0,
                    "highlight": state["hl"] > 0,
                }
            )
        closing, tag = match.groups()
        state[tag] = max(0, state[tag] - 1) if closing else state[tag] + 1
        cursor = match.end()
    if cursor < len(text):
        segments.append(
            {
                "text": text[cursor:],
                "bold": state["b"] > 0,
                "highlight": state["hl"] > 0,
            }
        )

    merged: list[dict[str, Any]] = []
    for segment in segments:
        if not segment["text"]:
            continue
        if merged and merged[-1]["bold"] == segment["bold"] and merged[-1]["highlight"] == segment["highlight"]:
            merged[-1]["text"] += segment["text"]
        else:
            merged.append(segment)
    return merged


def _strip_rich_text_markup(text: str) -> str:
    return RICH_TEXT_TAG_RE.sub("", text)


def _has_rich_text_markup(text: str) -> bool:
    return bool(RICH_TEXT_TAG_RE.search(text))


def _ensure_text_space(node: ET.Element, text: str) -> None:
    if text[:1].isspace() or text[-1:].isspace():
        node.set(f"{{{XML_NS}}}space", "preserve")


def _build_styled_runs(paragraph_xml: str, updated: str) -> str:
    wrapper = f'<root xmlns:a="{DRAWINGML_NS}">{paragraph_xml}</root>'
    root = ET.fromstring(wrapper)
    paragraph = root[0]
    bullet_paragraph = updated.startswith(BULLET_PREFIX)
    if bullet_paragraph:
        updated = updated[len(BULLET_PREFIX):].lstrip()
        _apply_bullet_properties(paragraph)

    text_containers: list[ET.Element] = []
    first_run_template: ET.Element | None = None
    first_run_properties: ET.Element | None = None
    for child in list(paragraph):
        if child.tag == f"{{{DRAWINGML_NS}}}r":
            text_containers.append(child)
            if first_run_template is None:
                first_run_template = child
            if first_run_properties is None:
                first_run_properties = child.find(f"{{{DRAWINGML_NS}}}rPr")
        elif child.tag == f"{{{DRAWINGML_NS}}}fld":
            text_containers.append(child)
            if first_run_properties is None:
                first_run_properties = child.find(f"{{{DRAWINGML_NS}}}rPr")

    if first_run_properties is None:
        first_run_properties = ET.Element(f"{{{DRAWINGML_NS}}}rPr")

    for child in text_containers:
        paragraph.remove(child)

    end_para = paragraph.find(f"{{{DRAWINGML_NS}}}endParaRPr")
    children = list(paragraph)
    insert_at = children.index(end_para) if end_para is not None and end_para in children else len(children)

    new_nodes: list[ET.Element] = []
    segments = (
        _parse_rich_text_segments(updated)
        if _has_rich_text_markup(updated)
        else [{"text": updated, "bold": False, "highlight": False}]
    )
    for segment in segments:
        parts = str(segment["text"]).split("\n")
        for idx, part in enumerate(parts):
            if idx > 0:
                new_nodes.append(ET.Element(f"{{{DRAWINGML_NS}}}br"))
            if first_run_template is not None:
                run = copy.deepcopy(first_run_template)
                for child in list(run):
                    if child.tag != f"{{{DRAWINGML_NS}}}rPr":
                        run.remove(child)
                run_properties = run.find(f"{{{DRAWINGML_NS}}}rPr")
                if run_properties is None:
                    run_properties = ET.Element(f"{{{DRAWINGML_NS}}}rPr")
                    run.insert(0, run_properties)
            else:
                run = ET.Element(f"{{{DRAWINGML_NS}}}r")
                run_properties = copy.deepcopy(first_run_properties)
                run.append(run_properties)
            if segment["bold"] or segment["highlight"]:
                run_properties.set("b", "1")
            if segment["highlight"]:
                for fill in list(run_properties.findall(f"{{{DRAWINGML_NS}}}solidFill")):
                    run_properties.remove(fill)
                solid_fill = ET.SubElement(run_properties, f"{{{DRAWINGML_NS}}}solidFill")
                ET.SubElement(solid_fill, f"{{{DRAWINGML_NS}}}srgbClr", {"val": HIGHLIGHT_COLOR})
            text_node = ET.SubElement(run, f"{{{DRAWINGML_NS}}}t")
            text_node.text = _strip_rich_text_markup(part)
            _ensure_text_space(text_node, text_node.text or "")
            new_nodes.append(run)

    for offset, node in enumerate(new_nodes):
        paragraph.insert(insert_at + offset, node)
    return ET.tostring(paragraph, encoding="unicode")


def _rewrite_paragraph(paragraph_xml: str, replacements: dict[str, str]) -> tuple[str, int]:
    matches = list(TEXT_RUN_RE.finditer(paragraph_xml))
    if not matches:
        return paragraph_xml, 0

    original = "".join(match.group(2) for match in matches)
    updated = original
    replacement_count = 0
    for placeholder, value in replacements.items():
        occurrences = updated.count(placeholder)
        if occurrences:
            updated = updated.replace(placeholder, value)
            replacement_count += occurrences
    if updated == original:
        return paragraph_xml, 0

    if updated.startswith(BULLET_PREFIX) or _has_rich_text_markup(updated) or "\n" in updated:
        return _build_styled_runs(paragraph_xml, updated), replacement_count

    escaped_updated = escape(updated)
    new_parts = [escaped_updated] + [""] * (len(matches) - 1)
    rebuilt: list[str] = []
    last_end = 0
    for match, new_text in zip(matches, new_parts):
        rebuilt.append(paragraph_xml[last_end:match.start(2)])
        rebuilt.append(new_text)
        last_end = match.end(2)
    rebuilt.append(paragraph_xml[last_end:])
    return "".join(rebuilt), replacement_count


def _replace_tokens_in_slide(xml_bytes: bytes, replacements: dict[str, str]) -> tuple[bytes, int, int]:
    text = xml_bytes.decode("utf-8")
    updated_text = text
    replaced_paragraphs = 0
    replacement_count = 0

    if PARAGRAPH_XML_RE.findall(text):
        rebuilt: list[str] = []
        last_end = 0
        for match in PARAGRAPH_XML_RE.finditer(text):
            rewritten, count = _rewrite_paragraph(match.group(1), replacements)
            rebuilt.append(text[last_end:match.start(1)])
            rebuilt.append(rewritten)
            last_end = match.end(1)
            if count:
                replaced_paragraphs += 1
                replacement_count += count
        rebuilt.append(text[last_end:])
        updated_text = "".join(rebuilt)
    else:
        for placeholder, value in replacements.items():
            occurrences = updated_text.count(placeholder)
            if occurrences:
                updated_text = updated_text.replace(placeholder, escape(value))
                replacement_count += occurrences
        replaced_paragraphs = 1 if updated_text != text else 0
    return updated_text.encode("utf-8"), replaced_paragraphs, replacement_count


def fill_ppt(template: Path, replacement_dict: Path, output: Path) -> dict[str, Any]:
    replacements = {
        str(key): _normalize_replacement_value(value)
        for key, value in _json(replacement_dict).items()
    }
    replaced_files = 0
    replaced_paragraphs = 0
    replaced_tokens = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        try:
            with ZipFile(template, "r") as zin:
                zin.extractall(tmpdir_path)
        except FileNotFoundError as exc:
            raise PipelineError(f"PPTX template not found: {template}") from exc
        except Exception as exc:
            raise PipelineError(f"Failed to open PPTX template {template}: {exc}") from exc

        for slide_xml in sorted((tmpdir_path / "ppt" / "slides").glob("slide*.xml")):
            updated_bytes, paragraph_count, token_count = _replace_tokens_in_slide(slide_xml.read_bytes(), replacements)
            if paragraph_count:
                slide_xml.write_bytes(updated_bytes)
                replaced_files += 1
                replaced_paragraphs += paragraph_count
                replaced_tokens += token_count

        with ZipFile(output, "w") as zout:
            for file_path in sorted(tmpdir_path.rglob("*")):
                if file_path.is_file():
                    zout.write(file_path, file_path.relative_to(tmpdir_path))

    return {
        "template": str(template),
        "replacement_dict": str(replacement_dict),
        "output": str(output),
        "replaced_files": replaced_files,
        "replaced_paragraphs": replaced_paragraphs,
        "replaced_tokens": replaced_tokens,
        "replacement_key_count": len(replacements),
    }


def _load_slide_layout_library(path: Path | None = None) -> dict[int, dict[str, Any]]:
    payload = _json(path or ROOT_DIR / "configs" / "slide_layout_library.json")
    slides = payload.get("slides")
    if not isinstance(slides, list):
        raise PipelineError("slide_layout_library.json must contain list field 'slides'")

    library: dict[int, dict[str, Any]] = {}
    for item in slides:
        if not isinstance(item, dict):
            continue
        slide_no = item.get("slide_no")
        slide_key = item.get("slide_key")
        page_type_to_slide = item.get("page_type_to_slide")
        if not isinstance(slide_no, int) or not slide_key or not isinstance(page_type_to_slide, dict):
            raise PipelineError(
                "invalid slide layout library entry: "
                f"slide_no={slide_no}, slide_key={slide_key}, page_type_to_slide={page_type_to_slide}"
            )
        library[slide_no] = {
            "slide_key": slide_key,
            "page_type_to_slide": page_type_to_slide,
        }
    return library


def _renderer_slides(control_data: dict[str, Any], control_file_path: Path) -> list[dict[str, Any]]:
    slides = control_data.get("slides")
    if isinstance(slides, list) and slides:
        return [slide for slide in slides if isinstance(slide, dict)]
    raise PipelineError(f"{control_file_path} must contain non-empty slides array")


def _selected_slide_files(control_data: dict[str, Any], control_file_path: Path) -> set[str]:
    keep: set[str] = set()
    by_no = {int(slide["slide_no"]): slide for slide in _renderer_slides(control_data, control_file_path) if slide.get("slide_no")}
    for slide_no, config in _load_slide_layout_library().items():
        page = by_no.get(slide_no)
        if not page:
            raise PipelineError(f"renderer_spec missing slide_no={slide_no} for {config['slide_key']}")
        selected_page_type = str(page.get("selected_page_type") or "").strip()
        slide_name = config["page_type_to_slide"].get(selected_page_type)
        if not slide_name:
            allowed = ", ".join(config["page_type_to_slide"].keys())
            raise PipelineError(
                f"invalid selected_page_type for slide_no={slide_no}, slide_key={config['slide_key']}: "
                f"{selected_page_type!r}; allowed={allowed}"
            )
        keep.add(str(slide_name))
    return keep


def clean_presentation(pptx_path: Path, control_file_path: Path, output_path: Path) -> dict[str, Any]:
    keep_slides = _selected_slide_files(_json(control_file_path), control_file_path)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        try:
            with ZipFile(pptx_path, "r") as zin:
                zin.extractall(tmpdir_path)
        except FileNotFoundError as exc:
            raise PipelineError(f"filled PPTX not found: {pptx_path}") from exc
        except Exception as exc:
            raise PipelineError(f"failed to open filled PPTX {pptx_path}: {exc}") from exc

        presentation_xml = tmpdir_path / "ppt" / "presentation.xml"
        rels_xml = tmpdir_path / "ppt" / "_rels" / "presentation.xml.rels"
        presentation_tree = ET.parse(presentation_xml)
        presentation_root = presentation_tree.getroot()
        rels_tree = ET.parse(rels_xml)
        rels_root = rels_tree.getroot()

        rel_targets = {
            rel.attrib["Id"]: rel.attrib["Target"].split("/")[-1]
            for rel in rels_root.findall(f"{{{PPT_PACKAGE_REL_NS}}}Relationship")
            if rel.attrib.get("Type", "").endswith("/slide")
        }
        slide_id_list = presentation_root.find(f"{{{PPT_PRESENTATION_NS}}}sldIdLst")
        if slide_id_list is None:
            raise PipelineError(f"presentation.xml is missing p:sldIdLst in {pptx_path}")

        kept_rids: set[str] = set()
        for slide_id in list(slide_id_list):
            rid = slide_id.attrib.get(f"{{{PPT_REL_NS}}}id")
            target_name = rel_targets.get(rid, "")
            if target_name not in keep_slides:
                slide_id_list.remove(slide_id)
            elif rid:
                kept_rids.add(rid)

        for rel in list(rels_root.findall(f"{{{PPT_PACKAGE_REL_NS}}}Relationship")):
            if rel.attrib.get("Type", "").endswith("/slide") and rel.attrib.get("Id") not in kept_rids:
                rels_root.remove(rel)

        presentation_tree.write(presentation_xml, encoding="UTF-8", xml_declaration=True)
        rels_tree.write(rels_xml, encoding="UTF-8", xml_declaration=True)
        with ZipFile(output_path, "w") as zout:
            for file_path in sorted(tmpdir_path.rglob("*")):
                if file_path.is_file():
                    zout.write(file_path, file_path.relative_to(tmpdir_path))

    return {
        "input_pptx": str(pptx_path),
        "control_file": str(control_file_path),
        "output_pptx": str(output_path),
        "kept_slide_files": sorted(keep_slides),
        "kept_slide_count": len(keep_slides),
    }


def build_template_token_report(template_path: Path, ppt_mapping_path: Path) -> dict[str, Any]:
    template_tokens = _collect_template_tokens(template_path)
    mapping_tokens = _collect_mapping_tokens(_json(ppt_mapping_path))
    template_set = set(template_tokens)
    mapping_set = set(mapping_tokens)
    missing_in_mapping = sorted(template_set - mapping_set)
    missing_in_template = sorted(mapping_set - template_set)
    matched = sorted(template_set & mapping_set)
    return {
        "summary": {
            "template_token_count": len(template_set),
            "mapping_token_count": len(mapping_set),
            "matched_token_count": len(matched),
            "missing_in_mapping_count": len(missing_in_mapping),
            "missing_in_template_count": len(missing_in_template),
            "is_consistent": not missing_in_mapping and not missing_in_template,
        },
        "missing_in_mapping": [
            {"placeholder": token, "template_locations": template_tokens[token]}
            for token in missing_in_mapping
        ],
        "missing_in_template": [
            {"placeholder": token, "mapping_entry": mapping_tokens[token]}
            for token in missing_in_template
        ],
        "matched_tokens": [
            {
                "placeholder": token,
                "template_locations": template_tokens[token],
                "mapping_entry": mapping_tokens[token],
            }
            for token in matched
        ],
    }


def _write_template_token_report(template_path: Path, ppt_mapping_path: Path, output_path: Path) -> None:
    report = build_template_token_report(template_path, ppt_mapping_path)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not report.get("summary", {}).get("is_consistent"):
        raise PipelineError("template tokens and ppt_mapping.json are inconsistent")


def should_prefix_bullet(field_name: str) -> bool:
    lowered = field_name.lower()
    if lowered in REPLACEMENT_TOP_LEVEL_FIELDS:
        return False
    if any(key in lowered for key in ("table_", "matrix_label", "matrix_title", "chart_", "source")):
        return False
    return True


def ensure_bullet_prefix(value: str, field_name: str) -> str:
    text_value = value.strip()
    if not text_value or not should_prefix_bullet(field_name):
        return value
    if text_value.startswith(("•", "-", "–", "—")):
        return text_value
    return BULLET_PREFIX + text_value


def get_slide_lookup(token_source: dict[str, Any]) -> dict[int, dict[str, Any]]:
    lookup: dict[int, dict[str, Any]] = {}
    for slide in token_source.get("slides", []):
        if not isinstance(slide, dict):
            continue
        slide_no = slide.get("slide_no")
        if slide_no is not None:
            lookup[int(slide_no)] = slide
    return lookup


def resolve_replacement_field(slide: dict[str, Any] | None, field_name: str) -> Any:
    if not slide:
        return ""
    if field_name in REPLACEMENT_TOP_LEVEL_FIELDS:
        return slide.get(field_name, "")
    content = slide.get("content") if isinstance(slide.get("content"), dict) else {}
    return content.get(field_name, "")


def stringify_replacement_value(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item not in (None, ""))
    if isinstance(value, dict):
        return "; ".join(
            f"{key}: {item}" for key, item in value.items() if item not in (None, "", [], {})
        )
    if value is None:
        return ""
    return str(value)


def determine_selected_page_type(slide: dict[str, Any] | None) -> str:
    if slide and slide.get("selected_page_type"):
        return str(slide["selected_page_type"])
    return ""


def add_tokens_for_variant(
    replacements: dict[str, str],
    tokens: list[dict[str, Any]],
    slide: dict[str, Any] | None,
    keep_unmapped_empty: bool,
    *,
    force_include: bool = False,
) -> None:
    for token in tokens:
        placeholder = str(token["placeholder"])
        field_name = str(token["field_name"])
        value = stringify_replacement_value(resolve_replacement_field(slide, field_name))
        value = ensure_bullet_prefix(value, field_name)
        if force_include or value or keep_unmapped_empty:
            replacements[placeholder] = value


def build_replacement_dict(
    token_source: dict[str, Any],
    ppt_mapping: dict[str, Any],
    keep_unmapped_empty: bool,
    *,
    renderer_spec_path: Path,
    ppt_mapping_path: Path,
) -> dict[str, str]:
    slide_lookup = get_slide_lookup(token_source)
    replacements: dict[str, str] = {}

    for mapping_slide in ppt_mapping.get("slides", []):
        slide_no = int(mapping_slide["slide_no"])
        slide = slide_lookup.get(slide_no)

        if "tokens" in mapping_slide:
            add_tokens_for_variant(
                replacements,
                mapping_slide["tokens"],
                slide,
                keep_unmapped_empty,
                force_include=True,
            )
            continue

        controlled_variants = mapping_slide.get("controlled_variants", {})
        selected_page_type = determine_selected_page_type(slide)

        if controlled_variants and not selected_page_type:
            raise ValueError(
                f"Missing selected_page_type for slide_no={slide_no}, slide_key={mapping_slide.get('slide_key', '')}. "
                f"Expected one of: {', '.join(controlled_variants.keys())}. "
                f"Checked renderer_spec={renderer_spec_path}."
            )
        if selected_page_type and selected_page_type not in controlled_variants:
            allowed = ", ".join(controlled_variants.keys())
            raise ValueError(
                f"Invalid selected_page_type in slide_no={slide_no}, slide_key={mapping_slide.get('slide_key', '')}. "
                f"Found '{selected_page_type}' in renderer-spec-derived token source={renderer_spec_path}. "
                f"Allowed values: {allowed}. Mapping file: {ppt_mapping_path}."
            )

        for page_type, variant in controlled_variants.items():
            is_active = page_type == selected_page_type
            if is_active:
                add_tokens_for_variant(
                    replacements,
                    variant.get("tokens", []),
                    slide,
                    keep_unmapped_empty,
                    force_include=True,
                )
            else:
                for token in variant.get("tokens", []):
                    replacements[str(token["placeholder"])] = ""

    return replacements


def build_token_source_from_renderer_spec(renderer_spec: dict[str, Any]) -> dict[str, Any]:
    result = build_token_source(renderer_spec)
    warnings = result.get("warnings") or []
    blocking = [
        warning for warning in warnings
        if "missing active body_copy fields" in warning
        or "empty active body_copy fields" in warning
        or "extra body_copy fields ignored" in warning
    ]
    if blocking:
        raise ValueError("renderer_spec cannot be converted into token source: " + "; ".join(blocking))
    return result["token_source"]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    printable = " ".join(str(part) for part in cmd)
    print(f"[pipeline] {printable}")
    subprocess.run([str(part) for part in cmd], cwd=str(cwd or ROOT_DIR), env=env, check=True)


def _run_returncode(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> int:
    printable = " ".join(str(part) for part in cmd)
    print(f"[pipeline] {printable}")
    completed = subprocess.run([str(part) for part in cmd], cwd=str(cwd or ROOT_DIR), env=env, check=False)
    return completed.returncode


def _append_failure_memory(run_dir: Path, event: str, *, outcome: str, command: str = "", details: dict[str, Any] | None = None) -> None:
    if not run_dir:
        return
    path = run_dir / FAILURE_MEMORY
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir),
        "event": event,
        "outcome": outcome,
        "command": command,
    }
    if details:
        payload["details"] = details
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _ensure_run_dir(run_dir: Path) -> Path:
    run_dir = run_dir.resolve()
    if not run_dir.exists() or not run_dir.is_dir():
        raise PipelineError(f"run directory not found: {run_dir}")
    if run_dir.name == "runs":
        raise PipelineError("run-dir points to a runs/ directory; pass the concrete attempt directory")
    return run_dir


def _preflight(run_dir: Path) -> None:
    required = [
        "banker_page_pack.json",
        "template_registry.json",
        "deck_blueprint.json",
        "page_evidence_contract.json",
        "renderer_spec.json",
    ]
    missing = [rel for rel in required if not (run_dir / rel).exists()]
    if missing:
        state = build_run_status(run_dir)
        raise PipelineError(
            "run is not ready for deterministic PPT rendering. "
            f"missing={missing}. current_stage={state.get('current_stage')} status={state.get('status')}. "
            "Run scripts/pipeline.py next --run-dir <run_dir> and repair the upstream artifact first."
        )


def _python_import_check(python_cmd: str, module_name: str) -> dict[str, Any]:
    code = (
        "import importlib, json\n"
        f"module_name = {module_name!r}\n"
        "try:\n"
        "    module = importlib.import_module(module_name)\n"
        "    print(json.dumps({'module': module_name, 'available': True, 'version': str(getattr(module, '__version__', '')), 'error': ''}))\n"
        "except Exception as exc:\n"
        "    print(json.dumps({'module': module_name, 'available': False, 'version': '', 'error': type(exc).__name__ + ': ' + str(exc)}))\n"
    )
    completed = subprocess.run([str(python_cmd), "-c", code], cwd=str(ROOT_DIR), text=True, capture_output=True, check=False)
    try:
        payload = json.loads(completed.stdout or "{}")
    except JSONDecodeError:
        payload = {"module": module_name, "available": False, "version": "", "error": completed.stderr.strip() or completed.stdout.strip()}
    if completed.returncode != 0 and not payload.get("error"):
        payload["error"] = completed.stderr.strip() or f"{python_cmd} returned {completed.returncode}"
    return payload


def _searxng_config() -> tuple[bool, str]:
    for env_var in SEARXNG_ENV_VARS:
        value = str(os.environ.get(env_var, "")).strip()
        if value:
            return True, value
    registry = _json(ROOT_DIR / "configs" / "source_registry.json")
    connectors = registry.get("search_connectors") if isinstance(registry.get("search_connectors"), dict) else {}
    searxng = connectors.get("searxng") if isinstance(connectors, dict) else {}
    configured_url = str(searxng.get("default_url") or "").strip() if isinstance(searxng, dict) else ""
    return bool(configured_url), configured_url


def _runtime_dependency_payload(python_cmd: str) -> tuple[dict[str, Any], list[str]]:
    required_checks: dict[str, Any] = {}
    missing_required: list[str] = []
    for item in REQUIRED_IMPORTS:
        result = _python_import_check(python_cmd, item["module"])
        required_checks[item["package"]] = result
        if not result.get("available"):
            missing_required.append(item["package"])

    search_providers: dict[str, bool] = {}
    search_provider_details: dict[str, Any] = {}
    searxng_configured, searxng_url = _searxng_config()
    for provider, module_names in SEARCH_MODULE_GROUPS.items():
        checks = [_python_import_check(python_cmd, module_name) for module_name in module_names]
        search_provider_details[provider] = checks
        search_providers[provider] = any(item.get("available") for item in checks)
    search_provider_details["searxng"] = {
        "configured": searxng_configured,
        "url": searxng_url,
        "module_checks": [],
        "env_ready": searxng_configured,
    }
    search_providers["searxng"] = searxng_configured

    pdf_module_checks = {
        name: _python_import_check(python_cmd, module_name)
        for name, module_name in PDF_EXTRACTION_MODULES.items()
    }
    pdf_command_checks = {
        name: {"command": name, "available": bool(shutil.which(name)), "path": shutil.which(name) or ""}
        for name in PDF_EXTRACTION_COMMANDS
    }
    has_pdf_extraction = any(item.get("available") for item in pdf_module_checks.values()) or any(
        item.get("available") for item in pdf_command_checks.values()
    )
    has_search_provider = any(search_providers.values())
    is_ready_for_ppt_pipeline = not missing_required
    payload = {
        "python": python_cmd,
        "required": required_checks,
        "search_providers": search_providers,
        "search_provider_details": search_provider_details,
        "pdf_extraction": {
            "modules": pdf_module_checks,
            "commands": pdf_command_checks,
        },
        "has_pdf_extraction": has_pdf_extraction,
        "manual_source_mode_supported": True,
        "manual_source_mode_is_fallback": False,
        "paid_search_optional": True,
        "paid_search_available": search_providers.get("tavily", False) or search_providers.get("duckduckgo", False),
        "is_ready_for_ppt_pipeline": is_ready_for_ppt_pipeline,
        "is_ready_for_e2e_research": is_ready_for_ppt_pipeline and has_search_provider and has_pdf_extraction,
        "has_search_provider": has_search_provider,
        "has_fallback_search": has_search_provider,
    }
    return payload, missing_required


def _runtime_readiness_stderr(payload: dict[str, Any], missing_required: list[str]) -> str:
    lines: list[str] = []
    if missing_required:
        lines.append("ERROR: Required import(s) failed: " + ", ".join(missing_required))
    if not payload.get("has_search_provider"):
        lines.append(
            "ERROR: No configured web-search provider is available for formal E2E research. "
            "Manual source intake remains available for user-provided URLs/files, but it is not a substitute for required public-search execution."
        )
        search_providers = payload.get("search_providers") if isinstance(payload.get("search_providers"), dict) else {}
        if not search_providers.get("searxng"):
            lines.append("Set SEARXNG_BASE_URL or source_registry search_connectors.searxng.default_url to enable formal search execution.")
    if not payload.get("has_pdf_extraction"):
        lines.append(
            "ERROR: No PDF extraction capability found. Install pdfplumber or pypdf, or provide pdftotext, "
            "before relying on public filings/prospectuses/annual reports in formal E2E research."
        )
    return "\n".join(lines)


def _check_runtime_readiness(run_dir: Path, python_cmd: str, *, strict: bool = False) -> bool:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    payload, missing_required = _runtime_dependency_payload(str(python_cmd))
    stderr = _runtime_readiness_stderr(payload, missing_required)
    (artifacts / "runtime_dependencies.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if stderr:
        (artifacts / "runtime_dependencies.stderr.txt").write_text(stderr + "\n", encoding="utf-8")
    else:
        (artifacts / "runtime_dependencies.stderr.txt").unlink(missing_ok=True)
    if not payload.get("is_ready_for_e2e_research"):
        message = (
            "runtime readiness diagnostics found missing formal E2E research capabilities. "
            f"See {artifacts / 'runtime_dependencies.json'} and {artifacts / 'runtime_dependencies.stderr.txt'}."
        )
        if strict:
            raise PipelineError(message)
        print(f"[pipeline] WARNING: {message}")
        return False
    return True


def validate_artifact_entry(
    run_dir: Path,
    artifact: str,
    *,
    path: Path | None = None,
    output: Path | None = None,
) -> dict[str, Any]:
    run_dir = _ensure_run_dir(run_dir)
    errors, warnings = run_artifact_validation(artifact, run_dir, path)
    result = {
        "is_valid": not errors,
        "artifact": artifact,
        "run_dir": str(run_dir),
        "path": str(path or run_dir / ARTIFACT_PATHS[artifact]),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
        "validation_policy": "mechanical_only",
    }
    if artifact == "banker_page_pack":
        diagnostics = banker_page_pack_template_diagnostics(run_dir, path)
        result["template_diagnostics"] = diagnostics
        diagnostics_path = run_dir / "artifacts" / "banker_page_pack_template_diagnostics.json"
        diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
        diagnostics_path.write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_path = output or run_dir / VALIDATION_OUTPUTS.get(artifact, f"artifacts/{artifact}_validation.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _validate_artifact(run_dir: Path, python_cmd: str, artifact: str, output: Path | None = None) -> None:
    result = validate_artifact_entry(run_dir, artifact, output=output)
    if not result["is_valid"]:
        raise PipelineError(f"{artifact} validation failed")


def _mark_not_client_ready(run_dir: Path) -> None:
    for name in (CLEAN_PPT, FILLED_PPT):
        source = run_dir / name
        dest = run_dir / f"NOT_CLIENT_READY_{name}"
        if source.exists() and not dest.exists():
            source.rename(dest)
    marker = run_dir / "NOT_CLIENT_READY_OUTPUT.txt"
    if not marker.exists():
        marker.write_text(
            "Formal PPT pipeline failed before client-ready final delivery.\n"
            "Any generated PPT was renamed with NOT_CLIENT_READY_ and must not be described as a final deliverable.\n"
            "Fix the current upstream blocker and rerun scripts/pipeline.py render.\n",
            encoding="utf-8",
        )


def _clear_not_client_ready(run_dir: Path) -> None:
    for name in (CLEAN_PPT, FILLED_PPT):
        not_ready = run_dir / f"NOT_CLIENT_READY_{name}"
        if not_ready.exists():
            not_ready.unlink()
    marker = run_dir / "NOT_CLIENT_READY_OUTPUT.txt"
    if marker.exists():
        marker.unlink()


def _clear_draft_state(run_dir: Path) -> None:
    """Remove draft-only markers before a formal render attempt.

    Draft output is an internal preview path, not a permanent run mode. Once the
    upstream package is repaired, a formal render in the same attempt should be
    able to replace draft flags with formal run flags. Explicit debug markers
    are intentionally not cleared here.
    """

    run_flags_path = run_dir / "artifacts" / "run_flags.json"
    existing = _json(run_flags_path)
    if existing.get("draft_output_only") is True and existing.get("debug_output_only") is True:
        run_flags_path.unlink(missing_ok=True)
    for rel in (
        "DRAFT_NOT_CLIENT_READY.txt",
        "artifacts/draft_delivery_manifest.json",
    ):
        path = run_dir / rel
        if path.exists():
            path.unlink()


def _write_run_flags(run_dir: Path, *, entrypoint: str, preflight_skipped: bool = False) -> None:
    """Record formal pipeline mode for final delivery.

    The Python pipeline is the formal controller, so it writes the
    package-of-record flags itself. Existing debug flags are preserved so a
    debug run cannot be accidentally promoted by calling finalize.
    """

    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    path = artifacts / "run_flags.json"
    existing = _json(path)
    if (run_dir / "DEBUG_OUTPUT_ONLY.txt").exists():
        return
    if existing.get("debug_output_only") is True and existing.get("draft_output_only") is not True:
        return
    payload = {
        "schema_version": "run_flags_v1",
        "research_gate": 1,
        "banker_page_pack_layer": 1,
        "quality_gate": 1,
        "source_run_dir": str(run_dir),
        "output_run_dir": str(run_dir),
        "package_of_record": str(run_dir),
        "debug_output_only": False,
        "debug_reason": "",
        "pipeline_entrypoint": entrypoint,
        "preflight_skipped": preflight_skipped,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_template_path(path_text: str, run_dir: Path) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    candidate = (run_dir / path).resolve()
    if candidate.exists():
        return candidate
    if path.exists():
        return path.resolve()
    return (ROOT_DIR / path).resolve()


def _registered_template_material(run_dir: Path) -> tuple[Path | None, str]:
    manifest = _json(run_dir / "artifacts/material_manifest.json")
    for item in manifest.get("materials") or []:
        if not isinstance(item, dict):
            continue
        source_type = str(item.get("source_type") or "").strip().lower()
        material_kind = str(item.get("material_kind") or "").strip().lower()
        path_text = str(item.get("file_path_or_url") or "").strip()
        if not path_text.lower().endswith((".pptx", ".potx", ".ppt")):
            continue
        if source_type == "ppt_template" or material_kind == "ppt_template":
            path = _resolve_template_path(path_text, run_dir)
            if path.exists():
                return path, str(item.get("material_id") or "")
    return None, ""


def _select_template_for_run(run_dir: Path, python_cmd: str, explicit_template: Path | None = None) -> Path:
    """Resolve the effective PPT template for this run.

    This is deterministic bookkeeping inside the render controller, not a
    separate role step.
    """

    del python_cmd
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    selection_path = artifacts / "template_selection.json"
    selected_material_id = ""
    if explicit_template is not None:
        selected = explicit_template.expanduser().resolve()
        source = "explicit_user_template"
        reason = "explicit --template value provided"
    else:
        registered, selected_material_id = _registered_template_material(run_dir)
        if registered is not None:
            selected = registered.resolve()
            source = "user_provided_template_material"
            reason = "first registered ppt_template material"
        else:
            selected = TEMPLATE.resolve()
            source = "bundled_default"
            reason = "no user-provided PPT template was registered"
    payload = {
        "schema_version": "template_selection_v1",
        "selected_template_path": str(selected),
        "selection_source": source,
        "selected_material_id": selected_material_id,
        "bundled_template_path": str(TEMPLATE.resolve()),
        "selection_rule": "explicit_user_template > registered ppt_template material > bundled_default",
        "reason": reason,
        "selected_template_exists": selected.exists(),
        "created_by": "scripts/pipeline.py",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    selection_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not selected.exists():
        raise PipelineError(f"selected template does not exist: {selected}")
    return selected


def validate_pre_ppt(run_dir: Path, python_cmd: str, *, template_path: Path | None = None) -> None:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    template_path = _select_template_for_run(run_dir, python_cmd, template_path)
    template_profile_path = artifacts / "template_profile.json"
    _run(
        [
            python_cmd,
            _internal_script("template/template_analyzer.py"),
            "--template",
            template_path,
            "--layout-config",
            ROOT_DIR / "configs" / "layout_config.json",
            "--output",
            template_profile_path,
        ]
    )
    _run(
        [
            python_cmd,
            _internal_script("template/template_analyzer.py"),
            "fit",
            "--renderer-spec",
            run_dir / "renderer_spec.json",
            "--template-profile",
            template_profile_path,
            "--output",
            artifacts / "template_fit_validation.json",
            "--fit-plan-output",
            artifacts / "template_fit_plan.json",
        ]
    )
    _validate_artifact(run_dir, python_cmd, "pre_ppt", artifacts / "stage_gate_pre_ppt_validation.json")


def render(
    run_dir: Path,
    python_cmd: str,
    *,
    skip_preflight: bool = False,
    template_path: Path | None = None,
    strict_runtime_readiness: bool = False,
) -> None:
    run_dir = _ensure_run_dir(run_dir)
    template_path = _select_template_for_run(run_dir, python_cmd, template_path)
    _append_failure_memory(
        run_dir,
        "pipeline_render",
        outcome="start",
        command=f"{python_cmd} {Path('scripts/pipeline.py')} render --run-dir {run_dir} --template {template_path}",
    )
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    _clear_draft_state(run_dir)
    _check_runtime_readiness(run_dir, python_cmd, strict=strict_runtime_readiness)
    if (run_dir / "banker_page_pack.json").exists():
        build_template_registry(run_dir, python_cmd, template_path=template_path)
        compile_page_pack(run_dir, python_cmd)
    if not skip_preflight:
        _preflight(run_dir)
    _write_run_flags(run_dir, entrypoint="scripts/pipeline.py render", preflight_skipped=skip_preflight)

    try:
        validate_pre_ppt(run_dir, python_cmd, template_path=template_path)
        _write_template_token_report(template_path, PPT_MAPPING, artifacts / "template_token_check.json")
        replacements = build_replacement_dict(
            build_token_source_from_renderer_spec(_json(run_dir / "renderer_spec.json")),
            _json(PPT_MAPPING),
            False,
            renderer_spec_path=run_dir / "renderer_spec.json",
            ppt_mapping_path=PPT_MAPPING,
        )
        _write_json(run_dir / "replacement_dict.json", replacements)
        _validate_artifact(run_dir, python_cmd, "replacement_dict", artifacts / "replacement_dict_validation.json")
        _write_json(
            artifacts / "fill_ppt_tokens.log.json",
            fill_ppt(template_path, run_dir / "replacement_dict.json", run_dir / FILLED_PPT),
        )
        _write_json(
            artifacts / "clean_filled_ppt.log.json",
            clean_presentation(run_dir / FILLED_PPT, run_dir / "renderer_spec.json", run_dir / CLEAN_PPT),
        )
        _run(
            [
                python_cmd,
                _internal_script("output/postprocess_ppt_visuals.py"),
                "--input-ppt",
                run_dir / CLEAN_PPT,
                "--renderer-spec",
                run_dir / "renderer_spec.json",
                "--output",
                run_dir / CLEAN_PPT,
                "--template-profile",
                artifacts / "template_profile.json",
                "--render-layouts",
                RENDER_LAYOUTS,
                "--log",
                artifacts / "postprocess_ppt_visuals.log.json",
                "--fail-on-unrendered",
            ]
        )
        _validate_artifact(run_dir, python_cmd, "filled_ppt", run_dir / "filled_ppt_validation.json")
        finalize(run_dir, python_cmd, require_client_ready=True)
        _clear_not_client_ready(run_dir)
    except Exception:
        _append_failure_memory(
            run_dir,
            "pipeline_render",
            outcome="failure",
            command=f"{python_cmd} {Path('scripts/pipeline.py')} render --run-dir {run_dir} --template {template_path}",
            details={"skip_preflight": skip_preflight, "template": str(template_path)},
        )
        _mark_not_client_ready(run_dir)
        raise
    else:
        _append_failure_memory(
            run_dir,
            "pipeline_render",
            outcome="success",
            command=f"{python_cmd} {Path('scripts/pipeline.py')} render --run-dir {run_dir} --template {template_path}",
            details={"skip_preflight": skip_preflight, "template": str(template_path)},
        )


def finalize(run_dir: Path, python_cmd: str, *, require_client_ready: bool) -> None:
    run_dir = _ensure_run_dir(run_dir)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    _write_run_flags(run_dir, entrypoint="scripts/pipeline.py finalize")
    command_text = f"{python_cmd} {Path('scripts/pipeline.py')} validate --artifact final_delivery --run-dir {run_dir}"
    result = validate_artifact_entry(
        run_dir,
        "final_delivery",
        output=artifacts / "final_delivery_validation.json",
    )
    if not result["is_valid"]:
        _append_failure_memory(
            run_dir,
            "pipeline_finalize",
            outcome="failure",
            command=command_text,
            details={"require_client_ready": require_client_ready, "return_code": 1},
        )
        _mark_not_client_ready(run_dir)
        raise PipelineError(
            "final delivery gate failed; see artifacts/final_delivery_validation.json "
            "and artifacts/run_quality_summary.json for repair targets"
        )
    _append_failure_memory(
        run_dir,
        "pipeline_finalize",
        outcome="success",
        command=command_text,
        details={"require_client_ready": require_client_ready, "return_code": 0},
    )
    summary = build_run_status(run_dir)
    summary["view"] = "summary"
    write_status_json(summary, artifacts / "status_report.json")
    if run_dir.name.startswith("attempt_"):
        runs_dir = run_dir.parent
        (runs_dir / "ACTIVE_ATTEMPT.txt").write_text(run_dir.name + "\n", encoding="utf-8")


def _run_if_inputs_exist(run_dir: Path, required: list[str]) -> tuple[bool, list[str]]:
    missing = [rel for rel in required if not (run_dir / rel).exists()]
    return not missing, missing


def start_brief(
    run_dir: Path,
    python_cmd: str,
    *,
    case_name: str,
    brief_text: str | None = None,
    brief_file: Path | None = None,
    files: list[str] | None = None,
    urls: list[str] | None = None,
    template_files: list[str] | None = None,
    target_company: str = "",
    transaction_type: str = "",
    industry: str = "",
    subsector: str = "",
    geography: str = "",
) -> None:
    args: list[Any] = [
        python_cmd,
        _internal_script("material-intake/ingest_materials.py"),
        "start-brief",
        "--case-name",
        case_name,
        "--run-dir",
        run_dir,
    ]
    if brief_text:
        args.extend(["--brief-text", brief_text])
    if brief_file:
        args.extend(["--brief-file", brief_file])
    for item in files or []:
        args.extend(["--file", item])
    for item in urls or []:
        args.extend(["--url", item])
    for item in template_files or []:
        args.extend(["--template-file", item])
    for flag, value in (
        ("--target-company", target_company),
        ("--transaction-type", transaction_type),
        ("--industry", industry),
        ("--subsector", subsector),
        ("--geography", geography),
    ):
        if value:
            args.extend([flag, value])
    _run(args)
    _validate_artifact(run_dir, python_cmd, "input_card", run_dir / "artifacts/input_card_validation.json")
    _validate_artifact(run_dir, python_cmd, "material_extracts", run_dir / "artifacts/material_extracts_validation.json")


def research_prepare(
    run_dir: Path,
    python_cmd: str,
    *,
    allow_missing_scope_bootstrap: bool = False,
    worker_backend: str = "manual_or_external",
) -> None:
    args: list[Any] = [
        python_cmd,
        _internal_script("research-external-evidence/ib_research_graph.py"),
        "prepare",
        "--run-dir",
        run_dir,
        "--worker-backend",
        worker_backend,
    ]
    if allow_missing_scope_bootstrap:
        args.append("--allow-missing-scope-bootstrap")
    _run(args)
    _validate_artifact(run_dir, python_cmd, "formal_search_plan", run_dir / "artifacts/formal_search_plan_validation.json")


def research_compile(run_dir: Path, python_cmd: str) -> None:
    _run(
        [
            python_cmd,
            _internal_script("research-external-evidence/ib_research_graph.py"),
            "compile",
            "--state",
            run_dir / "artifacts/research_graph_state.json",
            "--formal-search-plan",
            run_dir / "artifacts/formal_search_plan.json",
            "--run-dir",
            run_dir,
        ]
    )
    _validate_artifact(run_dir, python_cmd, "formal_research_execution", run_dir / "artifacts/formal_research_execution_validation.json")
    _validate_artifact(run_dir, python_cmd, "source_archive", run_dir / "artifacts/source_archive_validation.json")
    _validate_artifact(run_dir, python_cmd, "pre_research_pack", run_dir / "artifacts/stage_gate_pre_research_pack_validation.json")


def _compile_research_graph_for_archive(run_dir: Path, python_cmd: str) -> None:
    _run(
        [
            python_cmd,
            _internal_script("research-external-evidence/ib_research_graph.py"),
            "compile",
            "--state",
            run_dir / "artifacts/research_graph_state.json",
            "--formal-search-plan",
            run_dir / "artifacts/formal_search_plan.json",
            "--run-dir",
            run_dir,
        ]
    )
    _validate_artifact(run_dir, python_cmd, "source_archive", run_dir / "artifacts/source_archive_validation.json")


def _rebuild_execution_report(run_dir: Path, python_cmd: str) -> None:
    _run(
        [
            python_cmd,
            _internal_script("research-external-evidence/ib_research_graph.py"),
            "compile",
            "--state",
            run_dir / "artifacts/research_graph_state.json",
            "--formal-search-plan",
            run_dir / "artifacts/formal_search_plan.json",
            "--run-dir",
            run_dir,
        ]
    )
    _validate_artifact(run_dir, python_cmd, "formal_research_execution", run_dir / "artifacts/formal_research_execution_validation.json")


def _rebuild_pre_research_gate(run_dir: Path, python_cmd: str) -> None:
    _validate_artifact(run_dir, python_cmd, "pre_research_pack", run_dir / "artifacts/stage_gate_pre_research_pack_validation.json")


def _rebuild_research_pack_export(run_dir: Path, python_cmd: str) -> None:
    evidence_export(run_dir, python_cmd)


def evidence_build(run_dir: Path, python_cmd: str) -> None:
    _run(
        [
            python_cmd,
            _internal_script("knowledge-repository/research_evidence_db.py"),
            "build",
            "--input-card",
            run_dir / "input_card.json",
            "--scope-pack",
            run_dir / "artifacts/industry_scope_pack.json",
            "--formal-search-plan",
            run_dir / "artifacts/formal_search_plan.json",
            "--formal-research-execution-report",
            run_dir / "artifacts/formal_research_execution_report.json",
            "--source-archive-index",
            run_dir / "artifacts/source_archive/source_archive_index.json",
            "--research-graph-state",
            run_dir / "artifacts/research_graph_state.json",
            "--material-manifest",
            run_dir / "artifacts/material_manifest.json",
            "--material-extracts",
            run_dir / "artifacts/material_extracts.json",
            "--output",
            run_dir / "artifacts/research_evidence_db.json",
        ]
    )


def evidence_export(run_dir: Path, python_cmd: str) -> None:
    _run(
        [
            python_cmd,
            _internal_script("knowledge-repository/research_evidence_db.py"),
            "export",
            "--research-evidence-db",
            run_dir / "artifacts/research_evidence_db.json",
            "--output",
            run_dir / "industry_research_pack.md",
        ]
    )
    _validate_artifact(run_dir, python_cmd, "research_pack", run_dir / "artifacts/research_pack_validation.json")


def _rebuild_compiled_deck(run_dir: Path, python_cmd: str) -> None:
    compile_page_pack(run_dir, python_cmd)


def compile_page_pack(run_dir: Path, python_cmd: str) -> None:
    run_dir = _ensure_run_dir(run_dir)
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    missing = [
        rel
        for rel in ("banker_page_pack.json", "template_registry.json")
        if not (run_dir / rel).exists()
    ]
    if missing:
        raise PipelineError(f"cannot compile page pack: missing {', '.join(missing)}")
    _validate_artifact(run_dir, python_cmd, "banker_page_pack", artifacts / "banker_page_pack_validation.json")
    _validate_artifact(run_dir, python_cmd, "template_registry", artifacts / "template_registry_validation.json")
    print(f"[pipeline] compile banker_page_pack.json -> deck_blueprint/page_evidence_contract/renderer_spec")
    deck_blueprint, page_contract, renderer_spec = compile_banker_page_pack(
        _json(run_dir / "banker_page_pack.json"),
        _json(run_dir / "template_registry.json"),
    )
    _write_json(run_dir / "deck_blueprint.json", deck_blueprint)
    _write_json(run_dir / "page_evidence_contract.json", page_contract)
    _write_json(run_dir / "renderer_spec.json", renderer_spec)
    _validate_artifact(run_dir, python_cmd, "deck_blueprint", run_dir / "artifacts/deck_blueprint_validation.json")
    _validate_artifact(run_dir, python_cmd, "page_evidence_contract", run_dir / "artifacts/page_evidence_contract_validation.json")
    _validate_artifact(run_dir, python_cmd, "renderer_spec", run_dir / "artifacts/renderer_spec_validation.json")


def build_template_registry(run_dir: Path, python_cmd: str, *, template_path: Path | None = None) -> None:
    run_dir = _ensure_run_dir(run_dir)
    template_path = _select_template_for_run(run_dir, python_cmd, template_path)
    _run(
        [
            python_cmd,
            _internal_script("template/template_analyzer.py"),
            "registry",
            "--template",
            template_path,
            "--output",
            run_dir / "template_registry.json",
        ]
    )
    _validate_artifact(run_dir, python_cmd, "template_registry", run_dir / "artifacts/template_registry_validation.json")


def rebuild_stale(run_dir: Path, python_cmd: str, *, template_path: Path | None = None) -> None:
    """Rebuild the shortest deterministic stale chain without authoring content."""

    run_dir = _ensure_run_dir(run_dir)
    template_path = _select_template_for_run(run_dir, python_cmd, template_path)
    state = build_run_status(run_dir)
    stage = str(state.get("current_stage") or "")
    status_value = str(state.get("status") or "")
    _append_failure_memory(
        run_dir,
        "pipeline_rebuild_stale",
        outcome="start",
        command=f"{python_cmd} {Path('scripts/pipeline.py')} rebuild-stale --run-dir {run_dir}",
        details={"stage": stage, "status": status_value},
    )

    deterministic_requirements: dict[str, list[str]] = {
        "source_archive": [
            "artifacts/formal_search_plan.json",
            "artifacts/research_graph_state.json",
        ],
        "formal_research_execution": [
            "artifacts/formal_search_plan.json",
            "artifacts/research_graph_state.json",
        ],
        "pre_research_pack": [
            "artifacts/formal_research_execution_report.json",
            "artifacts/source_archive/source_archive_index.json",
        ],
        "research_pack": ["artifacts/research_evidence_db.json"],
        "deck_blueprint": [
            "banker_page_pack.json",
            "template_registry.json",
        ],
        "page_evidence_contract": [
            "banker_page_pack.json",
            "template_registry.json",
        ],
        "renderer_spec": [
            "banker_page_pack.json",
            "template_registry.json",
        ],
        "pre_ppt": ["renderer_spec.json", "page_evidence_contract.json"],
    }
    ok, missing = _run_if_inputs_exist(run_dir, deterministic_requirements.get(stage, []))
    if not ok:
        raise PipelineError(
            f"cannot rebuild {stage}: missing required upstream artifact(s): {', '.join(missing)}"
        )

    try:
        if stage == "source_archive":
            _compile_research_graph_for_archive(run_dir, python_cmd)
        elif stage == "formal_research_execution":
            _rebuild_execution_report(run_dir, python_cmd)
        elif stage == "pre_research_pack":
            _rebuild_pre_research_gate(run_dir, python_cmd)
        elif stage == "research_pack":
            _rebuild_research_pack_export(run_dir, python_cmd)
        elif stage in {"deck_blueprint", "page_evidence_contract", "renderer_spec"}:
            _rebuild_compiled_deck(run_dir, python_cmd)
        elif stage == "template_profile":
            _run(
                [
                    python_cmd,
                    _internal_script("template/template_analyzer.py"),
                    "--template",
                    template_path,
                    "--layout-config",
                    ROOT_DIR / "configs" / "layout_config.json",
                    "--output",
                    run_dir / "artifacts/template_profile.json",
                ]
            )
        elif stage == "template_fit_validation":
            _run(
                [
                    python_cmd,
                    _internal_script("template/template_analyzer.py"),
                    "fit",
                    "--renderer-spec",
                    run_dir / "renderer_spec.json",
                    "--template-profile",
                    run_dir / "artifacts/template_profile.json",
                    "--output",
                    run_dir / "artifacts/template_fit_validation.json",
                    "--fit-plan-output",
                    run_dir / "artifacts/template_fit_plan.json",
                ]
            )
        elif stage == "pre_ppt":
            validate_pre_ppt(run_dir, python_cmd, template_path=template_path)
        else:
            raise PipelineError(
                f"rebuild-stale does not auto-rebuild stage {stage}. "
                "This stage likely needs LLM judgment or authoring repair; run pipeline.py next and follow owner guidance."
            )
    except Exception:
        _append_failure_memory(
            run_dir,
            "pipeline_rebuild_stale",
            outcome="failure",
            command=f"{python_cmd} {Path('scripts/pipeline.py')} rebuild-stale --run-dir {run_dir}",
            details={"stage": stage, "status": status_value},
        )
        raise

    new_state = build_run_status(run_dir)
    _append_failure_memory(
        run_dir,
        "pipeline_rebuild_stale",
        outcome="success",
        command=f"{python_cmd} {Path('scripts/pipeline.py')} rebuild-stale --run-dir {run_dir}",
        details={"before_stage": stage, "after_stage": new_state.get("current_stage")},
    )
    print(json.dumps({"is_valid": True, "before_stage": stage, "after_stage": new_state.get("current_stage")}, ensure_ascii=False, indent=2))


def status_view(run_dir: Path, view: str, output: Path | None = None, markdown_output: Path | None = None) -> None:
    run_dir = _ensure_run_dir(run_dir)
    report = build_run_status(run_dir)
    if view in {"gate", "route", "summary", "status"}:
        report["view"] = view
    if output is None and view == "next":
        output = run_dir / "artifacts/status_report.json"
    write_status_json(report, output)
    if markdown_output:
        write_status_markdown(report, markdown_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _check_tool_integrity() -> None:
    """Verify critical pipeline functions have not been patched at runtime.

    This is a lightweight behavioral check: it inspects the source of key
    functions for markers that would be lost if an agent replaced them with
    stubs (e.g., forcing is_valid=True, swallowing exceptions). If tampering
    is detected, the pipeline refuses to run.
    """
    import inspect

    checks = {
        "_preflight": "PipelineError",
        "finalize": "PipelineError",
        "validate_pre_ppt": "_run(",
        "render": "_mark_not_client_ready",
    }
    for func_name, marker in checks.items():
        func = globals().get(func_name)
        if func is None:
            raise PipelineError(f"tool integrity: {func_name} is missing; do not modify pipeline.py")
        src = inspect.getsource(func)
        if marker not in src:
            raise PipelineError(
                f"tool integrity: {func_name} appears to have been modified "
                f"(expected marker '{marker}' not found). "
                "Do not patch pipeline.py to bypass gates. "
                "Repair the upstream artifact instead."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python interpreter used for child scripts.")
    sub = parser.add_subparsers(dest="command", required=True)
    start_brief_parser = None
    research_prepare_parser = None
    validate_pre_ppt_parser = None
    validate_parser = None
    template_registry_parser = None
    render_parser = None
    rebuild_stale_parser = None
    finalize_parser = None
    status_parsers = []
    for name in (
        "status",
        "next",
        "gate",
        "route",
        "summary",
        "start-brief",
        "research-prepare",
        "research-compile",
        "evidence-build",
        "evidence-export",
        "compile",
        "validate",
        "template-registry",
        "validate-pre-ppt",
        "rebuild-stale",
        "render",
        "finalize",
    ):
        p = sub.add_parser(name)
        p.add_argument("--run-dir", required=True)
        if name in {"status", "next", "gate", "route", "summary"}:
            status_parsers.append(p)
        elif name == "start-brief":
            start_brief_parser = p
        elif name == "research-prepare":
            research_prepare_parser = p
        elif name == "validate":
            validate_parser = p
        elif name == "template-registry":
            template_registry_parser = p
        elif name == "validate-pre-ppt":
            validate_pre_ppt_parser = p
        elif name == "rebuild-stale":
            rebuild_stale_parser = p
        elif name == "render":
            render_parser = p
        elif name == "finalize":
            finalize_parser = p

    if (
        start_brief_parser is None
        or research_prepare_parser is None
        or validate_parser is None
        or template_registry_parser is None
        or validate_pre_ppt_parser is None
        or rebuild_stale_parser is None
        or render_parser is None
        or finalize_parser is None
    ):
        raise RuntimeError("failed to construct parser for pipeline commands")

    for template_parser in (template_registry_parser, validate_pre_ppt_parser, rebuild_stale_parser, render_parser):
        template_parser.add_argument(
            "--template",
            default="",
            help="Optional explicit user PPTX/POTX template. If omitted, pipeline selects a registered ppt_template material or the bundled template.",
        )
    for status_parser in status_parsers:
        status_parser.add_argument("--output")
        status_parser.add_argument("--markdown-output")
    start_brief_parser.add_argument("--case-name", required=True)
    start_brief_parser.add_argument("--brief-text")
    start_brief_parser.add_argument("--brief-file")
    start_brief_parser.add_argument("--file", action="append", default=[])
    start_brief_parser.add_argument("--url", action="append", default=[])
    start_brief_parser.add_argument("--template-file", action="append", default=[])
    start_brief_parser.add_argument("--target-company", default="")
    start_brief_parser.add_argument("--transaction-type", default="")
    start_brief_parser.add_argument("--industry", default="")
    start_brief_parser.add_argument("--subsector", default="")
    start_brief_parser.add_argument("--geography", default="")
    research_prepare_parser.add_argument("--worker-backend", default="manual_or_external")
    research_prepare_parser.add_argument(
        "--allow-missing-scope-bootstrap",
        action="store_true",
        help="Diagnostic/bootstrap mode only: allow prepare without industry_scope_pack_boundary_card and boundary QC pass.",
    )
    validate_parser.add_argument("--artifact", required=True, choices=sorted(ARTIFACT_PATHS))
    validate_parser.add_argument("--path", help="Optional explicit artifact path.")
    validate_parser.add_argument("--output")
    render_parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Only for repairing a run whose state report is stale but the operator has verified pre-PPT readiness.",
    )
    render_parser.add_argument(
        "--strict-runtime-readiness",
        action="store_true",
        help="Fail render when search/PDF runtime diagnostics are missing instead of recording an advisory warning.",
    )
    finalize_parser.add_argument("--require-client-ready", action="store_true")
    args = parser.parse_args()

    try:
        _check_tool_integrity()
        run_dir = Path(args.run_dir)
        if args.command in {"status", "next", "gate", "route", "summary"}:
            status_view(
                run_dir,
                args.command,
                output=Path(args.output) if args.output else None,
                markdown_output=Path(args.markdown_output) if args.markdown_output else None,
            )
        elif args.command == "start-brief":
            start_brief(
                run_dir,
                args.python,
                case_name=args.case_name,
                brief_text=args.brief_text,
                brief_file=Path(args.brief_file) if args.brief_file else None,
                files=args.file,
                urls=args.url,
                template_files=args.template_file,
                target_company=args.target_company,
                transaction_type=args.transaction_type,
                industry=args.industry,
                subsector=args.subsector,
                geography=args.geography,
            )
        elif args.command == "research-prepare":
            research_prepare(
                _ensure_run_dir(run_dir),
                args.python,
                allow_missing_scope_bootstrap=args.allow_missing_scope_bootstrap,
                worker_backend=args.worker_backend,
            )
        elif args.command == "research-compile":
            research_compile(_ensure_run_dir(run_dir), args.python)
        elif args.command == "evidence-build":
            evidence_build(_ensure_run_dir(run_dir), args.python)
        elif args.command == "evidence-export":
            evidence_export(_ensure_run_dir(run_dir), args.python)
        elif args.command == "compile":
            compile_page_pack(_ensure_run_dir(run_dir), args.python)
        elif args.command == "template-registry":
            build_template_registry(_ensure_run_dir(run_dir), args.python, template_path=Path(args.template) if args.template else None)
        elif args.command == "validate":
            result = validate_artifact_entry(
                _ensure_run_dir(run_dir),
                args.artifact,
                path=Path(args.path) if args.path else None,
                output=Path(args.output) if args.output else None,
            )
            if not result["is_valid"]:
                return 1
        elif args.command == "validate-pre-ppt":
            validate_pre_ppt(_ensure_run_dir(run_dir), args.python, template_path=Path(args.template) if args.template else None)
        elif args.command == "rebuild-stale":
            rebuild_stale(_ensure_run_dir(run_dir), args.python, template_path=Path(args.template) if args.template else None)
        elif args.command == "render":
            render(
                _ensure_run_dir(run_dir),
                args.python,
                skip_preflight=args.skip_preflight,
                template_path=Path(args.template) if args.template else None,
                strict_runtime_readiness=args.strict_runtime_readiness,
            )
        elif args.command == "finalize":
            finalize(_ensure_run_dir(run_dir), args.python, require_client_ready=args.require_client_ready)
    except subprocess.CalledProcessError as exc:
        return exc.returncode or 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
