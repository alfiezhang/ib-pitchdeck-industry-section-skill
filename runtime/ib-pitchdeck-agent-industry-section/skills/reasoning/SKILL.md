---
name: ib-industry-reasoning
description: Produce banker judgment for the IB industry section from validated evidence, including supported judgments, hypotheses, research requests, hypothesis resolution, and issue analysis.
---

# Reasoning

## Your Job

Turn validated evidence into banker judgment for a pre-mandate client pitch.
This role decides what can be said, what is only directional, what remains a
hypothesis, and whether the run has enough evidence for a client-ready industry
section.

Reasoning does not search, manage sources, design slides, fit templates, or
render PPT.

## Inputs

- `artifacts/research_evidence_db.json`
- `industry_research_pack.md`
- `artifacts/formal_research_execution_report.json`
- `artifacts/coverage_accounting.json`
- `artifacts/industry_scope_pack.json`

## Outputs

- `industry_issue_analysis.json`
- `artifacts/hypothesis_store.json`
- `artifacts/research_request_queue.json`
- `artifacts/page_argument_pack.json`

## How To Think

- Read evidence status before forming judgment:
  - supported;
  - directional;
  - caveat only;
  - not researched.
- Decide which industry questions matter for this target and transaction.
- Interpret buyer relevance:
  - why this industry matters to a potential client;
  - what buyers will likely test;
  - what makes the timing or positioning credible;
  - where the story is weak.
- Separate:
  - supported judgment;
  - hypothesis;
  - research request;
  - caveat/diligence question.
- Decide deliverable depth:
  - `enough_for_client_pitch`;
  - `evidence_limited_pitch_outline`;
  - `research_first_required`.
- Record that decision explicitly in `evidence_readiness`:
  - `decision_status`: `llm_decided` when Reasoning makes the decision, or
    `qc_confirmed` when QC confirms it;
  - `decision_owner`: `reasoning` or `qc`;
  - `decision_note`: one sentence explaining the evidence quality basis.
- Create page/section argument candidates only from supported or appropriately
  caveated judgments.

## Hypothesis Resolution

```text
Hypothesis Store
  -> Hypothesis Resolution
      -> supported by evidence -> Supported Judgments
      -> weak/directional -> Research Request Queue or body-only context
      -> unresolved -> Caveat / Diligence Question Block
      -> contradicted -> reject or reframe
```

Allowed deck usage:

- `supported`: headline allowed.
- `directional`: body/context only.
- `caveat_only`: caveat or diligence question only.
- `not_researched`: not allowed in deck claims.

## What Scripts Handle

Python may:

- build issue-analysis skeletons;
- normalize mechanical fields;
- validate evidence IDs and metric IDs;
- build hypothesis and page-argument skeletons.
- provide evidence counts, gap counts, and candidate rows as telemetry.

Python must not:

- decide that evidence is persuasive;
- decide deliverable depth from the number of EV/MET rows;
- grant headline/chart/body permission by default;
- write banker conclusions;
- promote hypotheses into supported judgments.

## What You May Edit

LLM may edit:

- substantive issue analysis;
- hypothesis treatment;
- research request prioritization;
- page argument rationale;
- deliverable depth decision.

LLM must not:

- change evidence IDs to pass validation;
- delete weak evidence instead of caveating it;
- write conclusions unsupported by evidence;
- skip research requests when evidence is thin.

## Good Output Looks Like

A good Reasoning output has:

- a clear client-pitch point of view;
- explicit evidence status for each major claim;
- an explicit `evidence_readiness` decision before Generation starts;
- useful research requests for gaps;
- no hypothesis disguised as conclusion;
- enough material for Generation to write slides without inventing facts.

## Avoid These Failure Modes

- Producing a full 8-page argument when evidence only supports an outline.
- Treating user brief facts as externally validated.
- Turning market-size leads into supported claims without source quality.
- Writing generic industry statements unrelated to the target's pitch.
- Sending every weak point to the deck instead of resolving or caveating it.

## Hand Off

Hand off `page_argument_pack` to Generation. If depth is insufficient, hand off
research requests to Research instead of forcing a full deck.

## Useful Commands

```bash
"$PYTHON_CMD" scripts/build_issue_analysis_skeleton.py \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --formal-research-execution-report "$RUN_DIR/artifacts/formal_research_execution_report.json" \
  --output "$RUN_DIR/industry_issue_analysis.json"

"$PYTHON_CMD" scripts/validate_issue_analysis.py \
  --issue-analysis "$RUN_DIR/industry_issue_analysis.json" \
  --research-pack "$RUN_DIR/industry_research_pack.md" \
  --output "$RUN_DIR/artifacts/issue_analysis_validation.json"

"$PYTHON_CMD" scripts/build_hypothesis_store_skeleton.py \
  --issue-analysis "$RUN_DIR/industry_issue_analysis.json" \
  --research-evidence-db "$RUN_DIR/artifacts/research_evidence_db.json" \
  --output "$RUN_DIR/artifacts/hypothesis_store.json"

"$PYTHON_CMD" scripts/build_research_request_queue.py \
  --hypothesis-store "$RUN_DIR/artifacts/hypothesis_store.json" \
  --output "$RUN_DIR/artifacts/research_request_queue.json"

"$PYTHON_CMD" scripts/build_page_argument_pack.py \
  --issue-analysis "$RUN_DIR/industry_issue_analysis.json" \
  --hypothesis-store "$RUN_DIR/artifacts/hypothesis_store.json" \
  --output "$RUN_DIR/artifacts/page_argument_pack.json"
```
