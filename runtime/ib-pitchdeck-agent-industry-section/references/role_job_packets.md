# Role Job Packets

Use a role job packet when one bounded task is easier to isolate than to keep in the main thread. The parent agent remains the engagement lead: it chooses the task, gives the worker only the context needed, inspects the result, and integrates usable work into the canonical artifact.

Good packet tasks include one source review, one boundary ambiguity, one small search batch, one page repair, one template-fit problem, or one QC repair brief.

Avoid packets for broad requests such as "make the whole deck", "fix everything", or "decide whether the project is complete" without full context.

## Parent Guidance

A good packet is self-contained. Include the task, engagement context, relevant input files, source limits, output location or result format, and the shortcuts the worker should avoid. After the worker returns, inspect the result before integrating it. Preserve blockers instead of silently weakening quality.

The worker should not rely on conversation context that is not in the packet.

## Example Packet

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
      "Extract locator, usable facts, metrics, scope, and limits."
    ],
    "expected_outputs": [
      "opened_sources",
      "source_archive_entries",
      "extracted_facts",
      "metric_candidates",
      "coverage_or_gap_notes"
    ]
  },
  "output_path": "artifacts/role_jobs/RJ-001.result.json",
  "avoid": [
    "Citing search snippets as evidence.",
    "Editing derived deck_blueprint.json instead of repairing banker_page_pack.json.",
    "Calling the work client-ready."
  ],
  "blocker_format": {
    "reason": "",
    "missing_input": "",
    "recommended_next_action": ""
  }
}
```

## Worker Result

```json
{
  "job_id": "RJ-001",
  "role": "research_external_evidence",
  "status": "completed_with_limits",
  "outputs": [
    "artifacts/source_archive/SRC-001.json"
  ],
  "decisions_or_notes": [
    "The source supports broader beauty context, not base makeup market size."
  ],
  "evidence_limits": [
    "Market-size source uses online GMV sample, not all-channel retail sales."
  ],
  "blocker": null,
  "next_recommended_owner": "knowledge_repository"
}
```

Allowed status values: `completed`, `completed_with_limits`, `blocked`, `needs_parent_decision`.

## Integration

Job results are not automatically canonical. The parent or owning role integrates source/archive results into the evidence DB, page draft fields into `banker_page_pack.json`, template notes into the fit plan, and QC notes into a repair brief. Workers should not hand-author derived renderer artifacts or the final PPT.
