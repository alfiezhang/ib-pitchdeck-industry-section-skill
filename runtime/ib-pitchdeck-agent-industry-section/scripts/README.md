# Runtime Scripts

Do not treat this folder as a menu. Most files here are internal helpers,
validators, or deterministic render utilities. The main agent should start from
`SKILL.md`, read the relevant `references/*.md`, and use only the entrypoint
named by the current role or QC repair brief.

## Public Agent Surface

Normal agent work should use only:

- `start_case_from_brief.py` for one-shot text brief intake;
- `status.py next` for observed state and owner routing;
- `status.py gate` for one aggregated mechanical state report;
- `pipeline.py rebuild-stale` for deterministic stale derived chains;
- `pipeline.py validate-pre-ppt`, `pipeline.py render`, and
  `pipeline.py finalize` for output readiness and delivery;
- `scripts/qc/validate_artifact.py --artifact <artifact>` for one deterministic artifact check.

Everything else should be called only when a role reference, `status.py`, or QC repair brief names the exact script.

## Internal Layout

- root `scripts/*.py`: small public runtime entrypoints only.
- `scripts/<role>/`: role production tools.
- `scripts/qc/validate_artifact.py`: unified deterministic artifact validator.
- `scripts/_lib/`: shared imports used by multiple role tools; not commands.

Install/package/manifest-check tooling lives in the repository-level
`devtools/` folder and is not part of the installed runtime skill.

All deterministic validators belong to QC:

```text
scripts/qc/validate_artifact.py --artifact <artifact>
```

Role production `build_*`, `extract_*`, `compile_*`, `render_*`, and repository
scripts are production tools for the relevant role. Mechanical validation is not role
production work; QC interprets it, then routes repair back to the
owning role.
