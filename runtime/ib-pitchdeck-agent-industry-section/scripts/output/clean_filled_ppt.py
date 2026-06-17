#!/usr/bin/env python3
# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'configs').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts" / "_lib"
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
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

from gate_guard import require_debug_output_name, require_pre_ppt_gate
from json_utils import load_json_file


P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

ET.register_namespace("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
ET.register_namespace("r", R_NS)
ET.register_namespace("p", P_NS)
ET.register_namespace("", PKG_NS)
SLIDE_LAYOUT_LIBRARY_PATH = _IB_RUNTIME_ROOT / "configs" / "slide_layout_library.json"


def load_json(path: Path):
    try:
        return load_json_file(path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"JSON file not found: {path}") from exc


def load_slide_layout_library(path: Path = SLIDE_LAYOUT_LIBRARY_PATH) -> dict[int, dict]:
    data = load_json(path)
    slides = data.get("slides")
    if not isinstance(slides, list):
        raise ValueError(f"Invalid slide layout library in {path}: missing list field 'slides'.")

    library = {}
    for item in slides:
        slide_no = item.get("slide_no")
        slide_key = item.get("slide_key")
        page_type_to_slide = item.get("page_type_to_slide")
        if not isinstance(slide_no, int) or not slide_key or not isinstance(page_type_to_slide, dict):
            raise ValueError(
                f"Invalid slide layout entry in {path}: "
                f"slide_no={slide_no}, slide_key={slide_key}, page_type_to_slide={page_type_to_slide}."
            )
        library[slide_no] = {
            "slide_key": slide_key,
            "page_type_to_slide": page_type_to_slide,
        }
    return library


def _extract_slides(data: dict, source_path: Optional[Path] = None) -> list[dict]:
    """Extract slide list from the canonical renderer spec control file."""
    slides = data.get("slides")
    if isinstance(slides, list) and slides:
        return slides
    raise ValueError(
        f"Cannot find slide data in {source_path or 'input'}: "
        f"expected 'slides' key with a non-empty array."
    )


def build_keep_set(control_data: dict, control_file_path: Optional[Path] = None) -> set[str]:
    slide_layout_library = load_slide_layout_library()
    keep = set()
    slides = _extract_slides(control_data, control_file_path)
    by_no = {int(page["slide_no"]): page for page in slides}

    for slide_no, config in slide_layout_library.items():
        page = by_no.get(slide_no)
        if not page:
            raise ValueError(
                f"Missing slide in control_file={control_file_path or 'renderer_spec.json'}: "
                f"slide_no={slide_no}, slide_key={config['slide_key']}."
            )
        selected_page_type = page.get("selected_page_type")
        slide_name = config["page_type_to_slide"].get(selected_page_type)
        if not slide_name:
            allowed = ", ".join(config["page_type_to_slide"].keys())
            raise ValueError(
                f"Invalid selected_page_type in control_file={control_file_path or 'renderer_spec.json'}: "
                f"slide_no={slide_no}, slide_key={config['slide_key']}, found='{selected_page_type}', allowed={allowed}."
            )
        keep.add(slide_name)

    return keep


def clean_presentation(pptx_path: Path, control_file_path: Path, output_path: Path) -> dict:
    control_data = load_json(control_file_path)
    keep_slides = build_keep_set(control_data, control_file_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        try:
            with ZipFile(pptx_path, "r") as zin:
                zin.extractall(tmpdir_path)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Filled PPTX not found: {pptx_path}") from exc
        except Exception as exc:
            raise ValueError(f"Failed to open filled PPTX {pptx_path}: {exc}") from exc

        presentation_xml = tmpdir_path / "ppt" / "presentation.xml"
        rels_xml = tmpdir_path / "ppt" / "_rels" / "presentation.xml.rels"

        presentation_tree = ET.parse(presentation_xml)
        presentation_root = presentation_tree.getroot()
        rels_tree = ET.parse(rels_xml)
        rels_root = rels_tree.getroot()

        rel_targets = {
            rel.attrib["Id"]: rel.attrib["Target"].split("/")[-1]
            for rel in rels_root.findall(f"{{{PKG_NS}}}Relationship")
            if rel.attrib.get("Type", "").endswith("/slide")
        }

        sld_id_lst = presentation_root.find(f"{{{P_NS}}}sldIdLst")
        if sld_id_lst is None:
            raise ValueError(f"presentation.xml is missing p:sldIdLst in {pptx_path}.")

        kept_rids = set()
        for sld_id in list(sld_id_lst):
            rid = sld_id.attrib.get(f"{{{R_NS}}}id")
            target_name = rel_targets.get(rid, "")
            if target_name not in keep_slides:
                sld_id_lst.remove(sld_id)
            else:
                kept_rids.add(rid)

        for rel in list(rels_root.findall(f"{{{PKG_NS}}}Relationship")):
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


def main():
    parser = argparse.ArgumentParser(description="Remove inactive layout-variant slides from a filled PPTX.")
    parser.add_argument("--input", default="industry_section_filled.pptx", help="Input filled PPTX.")
    parser.add_argument("--control-file", default="renderer_spec.json", help="Path to renderer_spec.json.")
    parser.add_argument("--output", default="industry_section_filled_clean.pptx", help="Output cleaned PPTX.")
    parser.add_argument("--log", default="", help="Optional JSON log output path.")
    parser.add_argument(
        "--allow-ungated-debug",
        action="store_true",
        help="Bypass the pre-PPT stage gate. Use only for local diagnostics, never delivery.",
    )
    args = parser.parse_args()

    try:
        output_path = Path(args.output)
        if args.allow_ungated_debug:
            require_debug_output_name(output_path)
        require_pre_ppt_gate(output_path.parent, allow_ungated_debug=args.allow_ungated_debug)
        result = clean_presentation(Path(args.input), Path(args.control_file), output_path)
    except Exception as exc:
        raise SystemExit(str(exc)) from exc
    if args.log:
        with Path(args.log).open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")


if __name__ == "__main__":
    main()
