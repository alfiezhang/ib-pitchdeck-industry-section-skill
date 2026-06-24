# QC scripts and validators

QC owns deterministic validation. Public status dashboards stay in root `scripts/`; this folder contains only runtime dependency checks and the unified mechanical artifact validator.

Public QC tools:
- `check_runtime_dependencies.py`
- `validate_artifact.py`

`validate_artifact.py` reports deterministic red-lines only: files, JSON, IDs, cross-references, renderer inputs, and PPT package mechanics. QC interprets those reports, performs LLM quality review where needed, and routes repair to the owning role.
