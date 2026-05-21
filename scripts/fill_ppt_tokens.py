#!/usr/bin/env python3

import argparse
import copy
import json
import re
import tempfile
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


def load_json(path: Path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


PARAGRAPH_RE = re.compile(r"(<a:p\b.*?</a:p>)", re.DOTALL)
TEXT_RE = re.compile(r"(<a:t>)(.*?)(</a:t>)", re.DOTALL)
RICH_TEXT_TAG_RE = re.compile(r"\[\[(\/?)(b|hl)\]\]")
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
HIGHLIGHT_COLOR = "E85D04"


def parse_rich_text_segments(text: str) -> list[dict]:
    segments = []
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
        if closing:
            state[tag] = max(0, state[tag] - 1)
        else:
            state[tag] += 1
        cursor = match.end()

    if cursor < len(text):
        segments.append(
            {
                "text": text[cursor:],
                "bold": state["b"] > 0,
                "highlight": state["hl"] > 0,
            }
        )

    merged = []
    for segment in segments:
        if not segment["text"]:
            continue
        if merged and merged[-1]["bold"] == segment["bold"] and merged[-1]["highlight"] == segment["highlight"]:
            merged[-1]["text"] += segment["text"]
        else:
            merged.append(segment)
    return merged


def strip_rich_text_markup(text: str) -> str:
    return RICH_TEXT_TAG_RE.sub("", text)


def has_rich_text_markup(text: str) -> bool:
    return bool(RICH_TEXT_TAG_RE.search(text))


def ensure_text_space(node: ET.Element, text: str) -> None:
    if text[:1].isspace() or text[-1:].isspace():
        node.set(f"{{{XML_NS}}}space", "preserve")


def build_styled_runs(paragraph_xml: str, updated: str) -> str:
    wrapper = f'<root xmlns:a="{A_NS}">{paragraph_xml}</root>'
    root = ET.fromstring(wrapper)
    paragraph = root[0]

    text_containers = []
    first_run_template = None
    first_rpr = None
    for child in list(paragraph):
        if child.tag == f"{{{A_NS}}}r":
            text_containers.append(child)
            if first_run_template is None:
                first_run_template = child
            if first_rpr is None:
                first_rpr = child.find(f"{{{A_NS}}}rPr")
        elif child.tag == f"{{{A_NS}}}fld":
            text_containers.append(child)
            if first_rpr is None:
                first_rpr = child.find(f"{{{A_NS}}}rPr")

    if first_rpr is None:
        first_rpr = ET.Element(f"{{{A_NS}}}rPr")

    for child in text_containers:
        paragraph.remove(child)

    end_para = paragraph.find(f"{{{A_NS}}}endParaRPr")
    children = list(paragraph)
    insert_at = children.index(end_para) if end_para is not None and end_para in children else len(children)

    new_nodes = []
    segments = parse_rich_text_segments(updated) if has_rich_text_markup(updated) else [
        {"text": updated, "bold": False, "highlight": False}
    ]

    for segment in segments:
        parts = segment["text"].split("\n")
        for idx, part in enumerate(parts):
            if idx > 0:
                new_nodes.append(ET.Element(f"{{{A_NS}}}br"))
            if first_run_template is not None:
                run = copy.deepcopy(first_run_template)
                for child in list(run):
                    if child.tag != f"{{{A_NS}}}rPr":
                        run.remove(child)
                rpr = run.find(f"{{{A_NS}}}rPr")
                if rpr is None:
                    rpr = ET.Element(f"{{{A_NS}}}rPr")
                    run.insert(0, rpr)
            else:
                run = ET.Element(f"{{{A_NS}}}r")
                rpr = copy.deepcopy(first_rpr)
                run.append(rpr)
            if segment["bold"] or segment["highlight"]:
                rpr.set("b", "1")
            if segment["highlight"]:
                for fill in list(rpr.findall(f"{{{A_NS}}}solidFill")):
                    rpr.remove(fill)
                solid_fill = ET.SubElement(rpr, f"{{{A_NS}}}solidFill")
                ET.SubElement(solid_fill, f"{{{A_NS}}}srgbClr", {"val": HIGHLIGHT_COLOR})
            text_node = ET.SubElement(run, f"{{{A_NS}}}t")
            text_node.text = escape(strip_rich_text_markup(part))
            ensure_text_space(text_node, text_node.text or "")
            new_nodes.append(run)

    for offset, node in enumerate(new_nodes):
        paragraph.insert(insert_at + offset, node)

    return ET.tostring(paragraph, encoding="unicode")


def rewrite_paragraph(paragraph_xml: str, replacements: dict[str, str]) -> tuple[str, int]:
    matches = list(TEXT_RE.finditer(paragraph_xml))
    if not matches:
        return paragraph_xml, 0

    original_parts = [m.group(2) for m in matches]
    original = "".join(original_parts)
    updated = original
    replacement_count = 0

    for placeholder, value in replacements.items():
        occurrences = updated.count(placeholder)
        if occurrences:
            updated = updated.replace(placeholder, value)
            replacement_count += occurrences

    if updated == original:
        return paragraph_xml, 0

    if has_rich_text_markup(updated) or "\n" in updated:
        return build_styled_runs(paragraph_xml, updated), replacement_count

    # Keep escaped entities intact by writing the rebuilt paragraph text into the
    # first text run and blanking the remaining runs. Splitting an escaped string
    # back across the original run lengths can produce invalid XML such as "&" + "amp;".
    escaped_updated = escape(updated)
    new_parts = [escaped_updated] + [""] * (len(matches) - 1)

    rebuilt = []
    last_end = 0
    for match, new_text in zip(matches, new_parts):
        rebuilt.append(paragraph_xml[last_end:match.start(2)])
        rebuilt.append(new_text)
        last_end = match.end(2)
    rebuilt.append(paragraph_xml[last_end:])
    return "".join(rebuilt), replacement_count


def replace_tokens_in_slide(xml_bytes: bytes, replacements: dict[str, str]) -> tuple[bytes, int, int]:
    text = xml_bytes.decode("utf-8")
    updated_text = text
    replaced_paragraphs = 0
    replacement_count = 0

    paragraphs = PARAGRAPH_RE.findall(text)
    if paragraphs:
        rebuilt = []
        last_end = 0
        for match in PARAGRAPH_RE.finditer(text):
            paragraph_xml = match.group(1)
            rewritten, count = rewrite_paragraph(paragraph_xml, replacements)
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


def fill_ppt(template: Path, replacement_dict: Path, output: Path) -> dict:
    replacements = load_json(replacement_dict)
    replaced_files = 0
    replaced_paragraphs = 0
    replaced_tokens = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        try:
            with ZipFile(template, "r") as zin:
                zin.extractall(tmpdir_path)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"PPTX template not found: {template}") from exc
        except Exception as exc:
            raise ValueError(f"Failed to open PPTX template {template}: {exc}") from exc

        for slide_xml in sorted((tmpdir_path / "ppt" / "slides").glob("slide*.xml")):
            xml_bytes = slide_xml.read_bytes()
            updated_bytes, paragraph_count, token_count = replace_tokens_in_slide(xml_bytes, replacements)
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


def main():
    parser = argparse.ArgumentParser(description="Fill a PPTX template by replacing {{...}} tokens.")
    parser.add_argument("--template", default="assets/industry_section_template_master.pptx")
    parser.add_argument("--replacement-dict", default="replacement_dict.json")
    parser.add_argument("--output", default="industry_section_filled.pptx")
    parser.add_argument("--log", default="")
    args = parser.parse_args()

    try:
        result = fill_ppt(Path(args.template), Path(args.replacement_dict), Path(args.output))
    except Exception as exc:
        raise SystemExit(str(exc)) from exc

    if args.log:
        with Path(args.log).open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")


if __name__ == "__main__":
    main()
