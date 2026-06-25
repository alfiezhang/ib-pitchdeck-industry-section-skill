# Role Job Packets

Use role job packets when a task is narrow enough to hand to a worker or isolate as a focused role pass. Do not use them to make the main agent disappear. The main agent remains the engagement lead: it chooses the job, supplies context, integrates the result, and decides the next role.

## When To Use

Good job-packet tasks:

- extract facts from one archived source or one user report;
- review source quality for a defined claim scope;
- check one industry-boundary ambiguity;
- draft one page inside the approved banker page pack;
- fit one slide draft to a specific template layout;
- review one artifact and produce a repair brief.

Poor job-packet tasks:

- "create the whole deck";
- "run the whole workflow";
- "fix everything";
- "decide whether this project is complete" without the full context;
- "edit global artifacts freely".

## Parent Responsibilities

The parent agent must:

1. create a self-contained job packet;
2. include all task-local context the worker needs;
3. list exact input artifacts and source files;
4. state the allowed output path or result format;
5. state forbidden shortcuts;
6. receive and inspect the result;
7. integrate the result into the canonical artifact only when it is usable;
8. record blockers instead of silently downgrading quality.

The parent should not rely on conversation context the worker cannot see.

## Worker Responsibilities

The worker must:

1. do only the assigned role task;
2. read the packet and listed artifacts;
3. avoid editing unrelated global artifacts;
4. return a result, repair recommendation, or blocker;
5. preserve evidence limits and uncertainty;
6. never turn hypotheses, search snippets, or unreviewed sources into conclusions.

## Packet Shape

Use JSON for machine-readable jobs when possible:

```json
{
  "job_id": "RJ-001",
  "role": "research_external_evidence",
  "objective": "Verify the China base makeup market-size definition and source quality.",
  "engagement_context": {
    "deliverable": "pre_mandate_client_pitch_industry_section",
    "disclosure_level": "public_and_user_provided_only"
  },
  "input_artifacts": [
    "artifacts/industry_scope_pack.json",
    "artifacts/research_request_queue.json"
  ],
  "task_context": {
    "core_industry": "China face/base makeup",
    "claim_scope": "market size and definition",
    "known_limits": ["search snippets are leads only"]
  },
  "task": {
    "instructions": [
      "Run source-specific searches or ingest provided URLs.",
      "Open and archive useful sources.",
      "Extract source locator, usable facts, metrics, scope, and limits."
    ],
    "required_outputs": [
      "opened_sources",
      "source_archive_entries",
      "extracted_facts",
      "metric_candidates",
      "coverage_or_gap_notes"
    ]
  },
  "output_path": "artifacts/role_jobs/RJ-001.result.json",
  "forbidden_actions": [
    "Do not cite search snippets as evidence.",
    "Do not edit derived deck_blueprint.json; repair banker_page_pack.json instead.",
    "Do not claim client-readiness."
  ],
  "blocker_format": {
    "reason": "",
    "missing_input": "",
    "recommended_next_action": ""
  }
}
```

## Schema Boundary

Job packets define delegation context, not canonical artifact schemas.

- Do not copy field-level requirements from `schemas/*.json` into this file.
- If a worker is asked to produce or repair a canonical artifact, cite the artifact path and its schema path.
- Keep `required_outputs` at the work-product level, such as archived sources, extracted facts, repair notes, or a draft artifact path.
- The parent or owning role is responsible for integrating worker output into the canonical artifact and then running the relevant deterministic format check.

Examples:

- `banker_page_pack.json`, conforming to `schemas/banker_page_pack_schema.json`
- derived `deck_blueprint.json`, conforming to `schemas/deck_blueprint_schema.json`
- `artifacts/formal_search_plan.json`, conforming to `schemas/formal_search_plan_schema.json`
- `artifacts/page_evidence_contract.json`, conforming to `schemas/page_evidence_contract_schema.json`

## Result Shape

```json
{
  "job_id": "RJ-001",
  "role": "research_external_evidence",
  "status": "completed",
  "outputs": [
    "artifacts/source_archive/SRC-001.json"
  ],
  "decisions_or_notes": [
    "KPMG source supports broader beauty context, not base makeup market size."
  ],
  "evidence_limits": [
    "Market-size source uses online GMV sample, not all-channel retail sales."
  ],
  "blocker": null,
  "next_recommended_owner": "knowledge_repository"
}
```

Allowed status values:

- `completed`
- `completed_with_limits`
- `blocked`
- `needs_parent_decision`

## Integration Rule

Job results are not automatically canonical. The parent or owning role must integrate them into the current artifact:

- source/archive results -> Knowledge evidence DB;
- source-quality or evidence-limit results -> embedded source review fields in the evidence DB;
- reasoning results -> banker_page_pack judgment fields or an LLM-authored research request queue after parent review;
- generation results -> banker_page_pack page fields before deterministic compilation;
- template results -> template fit plan or fit feedback;
- QC results -> repair brief and owner routing.
