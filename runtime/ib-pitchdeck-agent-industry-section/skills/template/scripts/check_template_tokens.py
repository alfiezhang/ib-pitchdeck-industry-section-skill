#!/usr/bin/env python3
# Runtime scripts can be run directly. Shared helpers remain in runtime
# `scripts/`; production tools live under role scripts; validators live under QC.
import sys as _ib_sys
from pathlib import Path as _IbPath
_IB_ROLE_SCRIPT_DIR = _IbPath(__file__).resolve().parent
_IB_RUNTIME_ROOT = next(
    _p for _p in _IbPath(__file__).resolve().parents
    if (_p / 'templates').is_dir() and (_p / 'skills').is_dir() and (_p / 'scripts').is_dir()
)
_IB_SHARED_SCRIPT_DIR = _IB_RUNTIME_ROOT / "scripts"
_IB_ROLE_SCRIPT_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills').glob('*/scripts'))
_IB_QC_VALIDATOR_DIRS = sorted((_IB_RUNTIME_ROOT / 'skills' / 'qc' / 'scripts' / 'validators').glob('*'))
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
import re
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from json_utils import load_json_file


TOKEN_PATTERN = re.compile(r"\{\{[^{}]+\}\}")


def load_json(path: Path):
    return load_json_file(path)


def collect_template_tokens(pptx_path: Path):
    # This checker only validates text-placeholder tokens reconstructed from paragraph text
    # in slide XML. It does not inspect object names, notes pages, slide masters, or
    # other non-text OOXML locations.
    token_locations = defaultdict(list)
    try:
        archive = ZipFile(pptx_path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"PPTX template not found: {pptx_path}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to open PPTX template {pptx_path}: {exc}") from exc
    with archive:
        for name in archive.namelist():
            if not (name.startswith("ppt/slides/slide") and name.endswith(".xml")):
                continue
            xml_bytes = archive.read(name)
            root = ET.fromstring(xml_bytes)
            for elem in root.iter():
                if not elem.tag.endswith("}p"):
                    continue
                paragraph_text = "".join(
                    child.text for child in elem.iter() if child.tag.endswith("}t") and child.text
                )
                for token in TOKEN_PATTERN.findall(paragraph_text):
                    token_locations[token].append(name)
    return token_locations


def collect_mapping_tokens(mapping: dict):
    tokens = {}
    for slide in mapping.get("slides", []):
        slide_no = slide.get("slide_no")
        slide_key = slide.get("slide_key")

        if "tokens" in slide:
            for token in slide.get("tokens", []):
                tokens[token["placeholder"]] = {
                    "slide_no": slide_no,
                    "slide_key": slide_key,
                    "field_name": token.get("field_name", ""),
                    "selected_page_type": slide.get("selected_page_type", ""),
                    "variant_key": "",
                }
            continue

        for page_type, variant in slide.get("controlled_variants", {}).items():
            for token in variant.get("tokens", []):
                tokens[token["placeholder"]] = {
                    "slide_no": slide_no,
                    "slide_key": slide_key,
                    "field_name": token.get("field_name", ""),
                    "selected_page_type": page_type,
                    "variant_key": variant.get("variant_key", ""),
                }
    return tokens


def build_report(template_tokens: dict, mapping_tokens: dict):
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
            {
                "placeholder": token,
                "template_locations": template_tokens[token],
            }
            for token in missing_in_mapping
        ],
        "missing_in_template": [
            {
                "placeholder": token,
                "mapping_entry": mapping_tokens[token],
            }
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


def main():
    parser = argparse.ArgumentParser(
        description="Compare PPT template placeholders against templates/ppt_mapping.json."
    )
    parser.add_argument(
        "--template",
        default="assets/industry_section_template_master.pptx",
        help="Path to the PPTX template.",
    )
    parser.add_argument(
        "--ppt-mapping",
        default="templates/ppt_mapping.json",
        help="Path to the PPT placeholder mapping JSON file.",
    )
    parser.add_argument(
        "--output",
        default="template_token_check.json",
        help="Path to write the comparison report.",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit with code 1 if the template and mapping are inconsistent.",
    )
    args = parser.parse_args()

    try:
        template_tokens = collect_template_tokens(Path(args.template))
        mapping_tokens = collect_mapping_tokens(load_json(Path(args.ppt_mapping)))
    except Exception as exc:
        raise SystemExit(str(exc)) from exc
    report = build_report(template_tokens, mapping_tokens)

    with Path(args.output).open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    if args.fail_on_diff and not report["summary"]["is_consistent"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
