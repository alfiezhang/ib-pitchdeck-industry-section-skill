# Runtime Scripts

Do not treat this folder as a menu. Most files here are internal helpers,
validators, or deterministic render utilities. The main agent should start from
`SKILL.md`, read the relevant `references/*.md`, and use only the entrypoint
named by the current role or QC repair brief.

## Public Agent Surface

Normal agent work should use only:

- `start_case_from_brief.py` for one-shot text brief intake;
- `state_report.py next` for observed state and owner routing;
- `qc/gate_report.py` for one aggregated root-cause / owner / next-action report;
- `pipeline.py rebuild-stale` for deterministic stale/failed aggregate chains;
- `pipeline.py validate-pre-ppt`, `pipeline.py render`, and
  `pipeline.py finalize` for output readiness and delivery;
- `scripts/qc/qc_router.py` for repair grouping.

Everything else should be called only when a role reference, `state_report.py`,
`qc/gate_report.py`, or QC repair brief names the exact script.

## Internal Layout

- root `scripts/*.py`: small public runtime entrypoints only.
- `scripts/<role>/`: role production tools.
- `scripts/qc/validators/<layer>/`: deterministic QC validators.
- `scripts/_lib/`: shared imports used by multiple role tools; not commands.

Install/package/manifest-check tooling lives in the repository-level
`devtools/` folder and is not part of the installed runtime skill.

All deterministic validators belong to QC:

```text
scripts/qc/validators/<layer>/validate_*.py
```

Role production `build_*`, `extract_*`, `compile_*`, `render_*`, and repository
scripts are production tools for the relevant role. Validators are not role
production tools; QC runs and interprets them, then routes repair back to the
owning role.
