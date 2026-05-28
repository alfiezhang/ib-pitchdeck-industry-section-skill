#!/usr/bin/env python3
"""Create a human-readable index and latest-final pointer for runs/attempt_* directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional


CORE_FILES = [
    "industry_input_memo.md",
    "industry_storyboard.json",
    "industry_section_ppt_copy.json",
    "replacement_dict.json",
    "industry_section_filled_clean.pptx",
    "filled_ppt_validation.json",
    "artifacts/final_delivery_validation.json",
    "artifacts/memo_validation.json",
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def attempt_summary(attempt_dir: Path) -> dict[str, Any]:
    missing = [rel for rel in CORE_FILES if not (attempt_dir / rel).exists()]
    ppt_path = attempt_dir / "industry_section_filled_clean.pptx"
    final_gate_path = attempt_dir / "artifacts/final_delivery_validation.json"
    final_gate = load_json(final_gate_path) if final_gate_path.exists() else {}
    source_files = [
        attempt_dir / "industry_input_memo.md",
        attempt_dir / "industry_storyboard.json",
        attempt_dir / "industry_section_ppt_copy.json",
        attempt_dir / "replacement_dict.json",
    ]
    final_gate_stale = False
    if final_gate_path.exists():
        final_gate_mtime = final_gate_path.stat().st_mtime
        final_gate_stale = any(path.exists() and path.stat().st_mtime > final_gate_mtime + 1.0 for path in source_files)
    ppt_mtime = ppt_path.stat().st_mtime if ppt_path.exists() else attempt_dir.stat().st_mtime
    return {
        "name": attempt_dir.name,
        "path": str(attempt_dir),
        "clean_ppt": str(ppt_path) if ppt_path.exists() else "",
        "clean_ppt_size": ppt_path.stat().st_size if ppt_path.exists() else 0,
        "mtime": ppt_mtime,
        "missing": missing,
        "is_complete": not missing,
        "final_gate_valid": final_gate.get("is_valid") is True and not final_gate_stale,
        "final_gate_stale": final_gate_stale,
        "final_gate_errors": final_gate.get("errors", []),
        "final_gate_warnings": final_gate.get("warnings", []),
    }


def choose_latest(summaries: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not summaries:
        return None
    valid = [item for item in summaries if item["final_gate_valid"]]
    if valid:
        return sorted(valid, key=lambda item: (item["mtime"], item["name"]))[-1]
    return None


def choose_latest_candidate(summaries: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not summaries:
        return None
    complete = [item for item in summaries if item["is_complete"]]
    if complete:
        return sorted(complete, key=lambda item: (item["mtime"], item["name"]))[-1]
    with_ppt = [item for item in summaries if item["clean_ppt"]]
    if with_ppt:
        return sorted(with_ppt, key=lambda item: (item["mtime"], item["name"]))[-1]
    return sorted(summaries, key=lambda item: (item["mtime"], item["name"]))[-1]


def write_index(
    runs_dir: Path,
    summaries: list[dict[str, Any]],
    latest: Optional[dict[str, Any]],
    latest_candidate: Optional[dict[str, Any]],
) -> None:
    lines = ["# Runs Index", ""]
    if latest:
        lines.extend(
            [
                f"Latest final run: `{latest['name']}`",
                f"Latest final PPT: `{latest['clean_ppt'] or 'none'}`",
                f"Final gate valid: `{latest['final_gate_valid']}`",
                "",
            ]
        )
    else:
        lines.extend(["Latest final run: none", "Latest final PPT: none", ""])
        if latest_candidate:
            lines.extend(
                [
                    f"Latest candidate run: `{latest_candidate['name']}`",
                    f"Candidate PPT: `{latest_candidate['clean_ppt'] or 'none'}`",
                    "Candidate is not deliverable until final gate passes.",
                    "",
                ]
            )

    lines.extend(
        [
            "| Attempt | Complete | Final Gate | PPT Size | Missing / Errors |",
            "|---|---:|---:|---:|---|",
        ]
    )
    for item in sorted(summaries, key=lambda row: row["name"], reverse=True):
        issues = []
        if item["missing"]:
            issues.append("missing: " + ", ".join(item["missing"]))
        if item["final_gate_errors"]:
            issues.append("errors: " + "; ".join(str(err) for err in item["final_gate_errors"]))
        if item["final_gate_warnings"]:
            issues.append("warnings: " + "; ".join(str(warn) for warn in item["final_gate_warnings"]))
        if item.get("final_gate_stale"):
            issues.append("final gate is older than source files; rerun validation")
        lines.append(
            "| `{name}` | {complete} | {final_gate} | {size:,} | {issues} |".format(
                name=item["name"],
                complete="yes" if item["is_complete"] else "no",
                final_gate="yes" if item["final_gate_valid"] else "no",
                size=item["clean_ppt_size"],
                issues="<br>".join(issues) if issues else "",
            )
        )

    (runs_dir / "RUNS_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if latest:
        (runs_dir / "LATEST_FINAL_RUN.txt").write_text(latest["path"] + "\n", encoding="utf-8")
        (runs_dir / "LATEST_FINAL_PPT.txt").write_text((latest["clean_ppt"] or "") + "\n", encoding="utf-8")
    else:
        (runs_dir / "LATEST_FINAL_RUN.txt").write_text("", encoding="utf-8")
        (runs_dir / "LATEST_FINAL_PPT.txt").write_text("", encoding="utf-8")
    (runs_dir / "runs_index.json").write_text(
        json.dumps({"latest": latest, "latest_candidate": latest_candidate, "attempts": summaries}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Index runs/attempt_* outputs and write latest-final pointers.")
    parser.add_argument("--runs-dir", required=True, help="Directory containing attempt_* run directories.")
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    attempts = sorted(path for path in runs_dir.glob("attempt_*") if path.is_dir())
    summaries = [attempt_summary(path) for path in attempts]
    latest = choose_latest(summaries)
    latest_candidate = choose_latest_candidate(summaries)
    write_index(runs_dir, summaries, latest, latest_candidate)
    print(json.dumps({"latest": latest, "latest_candidate": latest_candidate, "attempt_count": len(summaries)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
