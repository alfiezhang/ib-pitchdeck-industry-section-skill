#!/usr/bin/env python3
"""Unified status, gate summary, and repair-routing dashboard.

This replaces the old split state/gate/router scripts. It is intentionally
mechanical: it reports which artifacts are missing or structurally invalid. LLM
review remains responsible for page quality, judgment, and pitch relevance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


RUNTIME_ROOT = next(
    parent for parent in Path(__file__).resolve().parents
    if (parent / "configs").is_dir() and (parent / "scripts").is_dir()
)
for path in [RUNTIME_ROOT / "scripts", RUNTIME_ROOT / "scripts" / "qc", RUNTIME_ROOT / "scripts" / "_lib"]:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)

from validate_artifact import ARTIFACT_PATHS, VALIDATION_OUTPUTS


PYTHON_COMMAND_TEMPLATE = "$PYTHON_CMD"

MAIN_PATH = [
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
    "material_extracts": "scripts/material-intake/ingest_materials.py",
    "formal_search_plan": "scripts/research-external-evidence/ib_research_graph.py prepare",
    "executable_search_batch": "LLM Query Author edits artifacts/executable_search_batch.json",
    "formal_research_execution": "scripts/research-external-evidence/ib_research_graph.py compile",
    "source_archive": "scripts/research-external-evidence/ib_research_graph.py compile",
    "research_evidence_db": "scripts/knowledge-repository/build_research_evidence_db.py, then Knowledge LLM authoring",
    "research_pack": "scripts/knowledge-repository/export_research_pack_from_db.py",
    "template_registry": "scripts/template/extract_template_registry.py",
    "banker_page_pack": "Generation LLM authors banker_page_pack.json",
    "deck_blueprint": "scripts/generation/compile_banker_page_pack.py",
    "page_evidence_contract": "scripts/generation/compile_banker_page_pack.py",
    "renderer_spec": "scripts/generation/compile_banker_page_pack.py",
    "replacement_dict": "scripts/output/generate_replacement_dict.py",
    "filled_ppt": "scripts/pipeline.py render",
    "final_delivery": "scripts/qc/validate_artifact.py --artifact final_delivery",
}


def _load_json(path: Path) -> dict[str, Any]:
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
        f"{PYTHON_COMMAND_TEMPLATE} scripts/qc/validate_artifact.py "
        f"--artifact {artifact} --run-dir {run_dir} --output {validation_path(run_dir, artifact)}"
    )


def artifact_status(run_dir: Path, artifact: str) -> dict[str, Any]:
    path = artifact_path(run_dir, artifact)
    validation = validation_path(run_dir, artifact)
    exists = path.exists()
    validation_payload = _load_json(validation) if validation.exists() else {}
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


def build_status(run_dir: Path) -> dict[str, Any]:
    rows = [artifact_status(run_dir, artifact) for artifact in MAIN_PATH]
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


def write_markdown(report: dict[str, Any], path: Path) -> None:
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


def write_json(report: dict[str, Any], path: Path | None) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("next", "gate", "route", "summary"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--run-dir", required=True)
        cmd.add_argument("--output")
        cmd.add_argument("--markdown-output")
    args = parser.parse_args()

    report = build_status(Path(args.run_dir))
    if args.command in {"gate", "route", "summary"}:
        report["view"] = args.command
    output = Path(args.output) if args.output else None
    if output is None and args.command == "next":
        output = Path(args.run_dir) / "artifacts/status_report.json"
    write_json(report, output)
    if args.markdown_output:
        write_markdown(report, Path(args.markdown_output))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "complete" or args.command in {"next", "gate", "route", "summary"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
