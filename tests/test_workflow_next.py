#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "runtime" / "ib-industry-section-skill" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from workflow import next_payload  # noqa: E402


FIXTURE_DIR = ROOT / "tests" / "fixtures" / "minimal_research_db"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_workflow_next_produces_pack_stage_repair_commands(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    artifacts = run_dir / "artifacts"
    artifacts.mkdir()

    _write_json(run_dir / "input_card.json", {"target_company": "Sample Target", "industry": "sample sector", "geography": "Sampleland"})
    _write_json(artifacts / "input_card_validation.json", {"is_valid": True})

    _write_json(artifacts / "industry_scope_pack.json", {"schema_version": "industry_scope_pack_v1", "scope_summary": {"working_market": "sample"}})
    _write_json(artifacts / "industry_scope_pack_validation.json", {"is_valid": True, "errors": [], "warnings": []})

    _write_json(artifacts / "formal_search_plan.json", {"issue_search_plan": []})
    _write_json(artifacts / "formal_search_plan_validation.json", {"is_valid": True, "errors": [], "warnings": []})

    _write_json(artifacts / "source_reviews.json", {"schema_version": "source_reviews_v1", "reviews": []})
    _write_json(artifacts / "source_reviews_validation.json", {"is_valid": True, "errors": [], "warnings": []})

    _write_json(artifacts / "source_archive" / "source_archive_index.json", {"schema_version": "source_archive_index_v1", "entries": []})
    _write_json(artifacts / "source_archive_validation.json", {"is_valid": True, "errors": [], "warnings": []})

    _write_json(artifacts / "formal_research_execution_report.json", {"issue_results": []})
    _write_json(artifacts / "formal_research_execution_validation.json", {"is_valid": True, "errors": [], "warnings": []})

    _write_json(artifacts / "stage_gate_pre_research_pack_validation.json", {"is_valid": True})

    _write_json(artifacts / "research_evidence_db.json", json.loads((FIXTURE_DIR / "research_evidence_db.json").read_text(encoding="utf-8")))
    _write_json(artifacts / "research_evidence_db_validation.json", {"is_valid": True, "errors": [], "warnings": []})

    payload = next_payload(run_dir)
    assert payload["current_stage"] == "RESEARCH_PACK_MISSING_OR_FAILED", payload
    command_text = "\n".join(item["command"] for item in payload["recommended_next_commands"])
    assert "export_research_pack_from_db.py" in command_text, payload["recommended_next_commands"]
    assert "validate_research_pack.py" in command_text, payload["recommended_next_commands"]
    assert "--source-registry templates/source_registry.json" in command_text, payload["recommended_next_commands"]


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_workflow_next_produces_pack_stage_repair_commands(Path(tmp_dir))
        print("workflow next regression tests passed.")
