#!/usr/bin/env python3
"""Check artifact_manifest.json for internal workflow drift."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from json_utils import load_json_file


ROOT_DIR = Path(__file__).resolve().parents[1]


def _script_path(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text.split()[0]


def validate_manifest(manifest: dict[str, Any], root_dir: Path) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != "artifact_manifest_v1":
        errors.append("schema_version must be artifact_manifest_v1")

    artifacts = manifest.get("artifacts")
    gates = manifest.get("gates")
    artifact_layers = manifest.get("artifact_layers", {})
    if not isinstance(artifacts, dict):
        return ["artifacts must be an object"]
    if not isinstance(gates, list):
        errors.append("gates must be an array")
        gates = []
    if artifact_layers and not isinstance(artifact_layers, dict):
        errors.append("artifact_layers must be an object when present")
        artifact_layers = {}

    for artifact_key, artifact in artifacts.items():
        if not isinstance(artifact, dict):
            errors.append(f"artifacts.{artifact_key} must be an object")
            continue
        if not str(artifact.get("path") or "").strip():
            errors.append(f"artifacts.{artifact_key}.path is required")
        for ref_key in ("validator", "builder"):
            script = _script_path(artifact.get(ref_key))
            if script and not (root_dir / script).exists():
                errors.append(f"artifacts.{artifact_key}.{ref_key} points to missing script: {script}")
        for input_key in artifact.get("inputs") or []:
            if str(input_key) not in artifacts:
                errors.append(f"artifacts.{artifact_key}.inputs references unknown artifact: {input_key}")
        if artifact.get("validator") and not str(artifact.get("validation") or "").strip():
            errors.append(f"artifacts.{artifact_key} has validator but no validation path")

    seen_gates: set[str] = set()
    for idx, gate in enumerate(gates, start=1):
        if not isinstance(gate, dict):
            errors.append(f"gates[{idx}] must be an object")
            continue
        gate_id = str(gate.get("gate") or "").strip()
        artifact_key = str(gate.get("artifact") or "").strip()
        if not gate_id:
            errors.append(f"gates[{idx}].gate is required")
        elif gate_id in seen_gates:
            errors.append(f"duplicate gate id: {gate_id}")
        seen_gates.add(gate_id)
        if artifact_key not in artifacts:
            errors.append(f"gates[{idx}] references unknown artifact: {artifact_key}")

    final_gate = next((gate for gate in gates if isinstance(gate, dict) and gate.get("gate") == "final_delivery"), {})
    if final_gate.get("require_client_ready") is not True:
        errors.append("final_delivery gate must set require_client_ready=true")

    layer_membership: dict[str, str] = {}
    for layer_name, layer in artifact_layers.items():
        if not isinstance(layer, dict):
            errors.append(f"artifact_layers.{layer_name} must be an object")
            continue
        layer_artifacts = layer.get("artifacts")
        if not isinstance(layer_artifacts, list):
            errors.append(f"artifact_layers.{layer_name}.artifacts must be an array")
            continue
        for artifact_key in layer_artifacts:
            artifact_key = str(artifact_key)
            if artifact_key not in artifacts:
                errors.append(f"artifact_layers.{layer_name} references unknown artifact: {artifact_key}")
                continue
            if artifact_key in layer_membership:
                errors.append(
                    f"artifact {artifact_key} appears in multiple layers: "
                    f"{layer_membership[artifact_key]} and {layer_name}"
                )
            layer_membership[artifact_key] = str(layer_name)
        for path_key in ("main_llm_authoring_path",):
            path_items = layer.get(path_key, [])
            if path_items and not isinstance(path_items, list):
                errors.append(f"artifact_layers.{layer_name}.{path_key} must be an array")
                continue
            for artifact_key in path_items:
                if str(artifact_key) not in artifacts:
                    errors.append(f"artifact_layers.{layer_name}.{path_key} references unknown artifact: {artifact_key}")
    if artifact_layers:
        missing_from_layers = sorted(set(artifacts) - set(layer_membership))
        if missing_from_layers:
            errors.append(f"artifacts missing from artifact_layers: {', '.join(missing_from_layers)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(ROOT_DIR / "templates" / "artifact_manifest.json"))
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    try:
        manifest = load_json_file(manifest_path)
    except Exception as exc:
        result = {"is_valid": False, "error_count": 1, "errors": [f"cannot read manifest: {exc}"]}
    else:
        errors = validate_manifest(manifest, ROOT_DIR)
        result = {"is_valid": not errors, "error_count": len(errors), "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["is_valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
