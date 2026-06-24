#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import ROLE_SCRIPT_DIRS, SCRIPT_IMPORT_PATHS, SKILL_DIR, _write_json


def _minimal_banker_page_pack() -> dict:
    return {
        "schema_version": "banker_page_pack",
        "research_requests": [
            {
                "origin_page_argument_id": "PA-002",
                "page_role": "market_size_segmentation",
                "research_question": "Which public source best supports the market-size definition?",
                "required_source_type": "public_search",
                "minimum_actual_searches": 2,
                "allowed_use_before_resolution": "context_only",
            }
        ],
        "slides": [
            {
                "slide_no": 1,
                "fixed_page_role": "industry_overview",
                "client_question": "What matters?",
                "open_questions": ["Which source confirms the adoption curve?"],
            }
        ],
    }


def test_build_research_request_queue_from_banker_page_pack(tmp_path: Path) -> None:
    pack_path = tmp_path / "banker_page_pack.json"
    output_path = tmp_path / "artifacts" / "research_request_queue.json"
    _write_json(pack_path, _minimal_banker_page_pack())

    result = subprocess.run(
        [
            sys.executable,
            str(ROLE_SCRIPT_DIRS["build_research_request_queue.py"]),
            "--banker-page-pack",
            str(pack_path),
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        cwd=str(SKILL_DIR),
        env={**__import__("os").environ, "PYTHONPATH": ":".join(str(path) for path in SCRIPT_IMPORT_PATHS)},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "research_request_queue_v1"
    assert [row["request_id"] for row in payload["requests"]] == ["RQ-001", "RQ-002"]
    assert payload["requests"][0]["origin_issue_id"] == "PA-002"
    assert payload["requests"][1]["origin_issue_area"] == "industry_overview"
    assert payload["requests"][1]["downstream_permission_if_unresolved"] == "caveat_or_diligence_question_only"
