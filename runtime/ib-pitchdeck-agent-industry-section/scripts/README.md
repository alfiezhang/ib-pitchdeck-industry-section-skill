# Runtime Scripts

Role agents should use production entrypoints under:

```text
scripts/<role>/
```

This `scripts/` tree contains:

- public shared control scripts such as `state_report.py`, `gate_report.py`, and
  `pipeline.py`;
- shared utility modules imported by multiple roles;
- role production scripts under `scripts/<role>/`;
- QC validators under `scripts/qc/validators/`;
- packaging, install, and shared support modules.

Do not browse this entire directory during normal agent work. Use
`state_report.py next` as the dashboard, use `gate_report.py` when several checks
or warnings need one root-cause view, then use the owner role document under
`references/`.

Shared runtime/orchestration scripts stay here, including:

- `state_report.py`
- `gate_report.py`
- `pipeline.py`
- `workflow.py` as a legacy alias for `state_report.py`
- `bootstrap_runtime.py`
- shared modules such as `json_utils.py`, `issue_taxonomy.py`, and
  `validation_common.py`

Normal agent work should treat the public control surface as:

- `state_report.py next` for observed state and owner routing;
- `gate_report.py` for one aggregated root-cause / owner / next-action report;
- `pipeline.py rebuild-stale` for deterministic stale/failed aggregate chains;
- `pipeline.py validate-pre-ppt`, `pipeline.py render`, and
  `pipeline.py finalize` for output readiness and delivery;
- `scripts/qc/qc_router.py` for repair grouping.

All deterministic validators belong to QC:

```text
scripts/qc/validators/<layer>/validate_*.py
```

Role production `build_*`, `extract_*`, `compile_*`, `render_*`, and repository
scripts are production tools for the relevant role. Validators are not role
production tools; QC runs and interprets them, then routes repair back to the
owning role.
