---
name: ib-industry-reasoning
description: Produce banker judgment for the IB industry section from validated evidence, including supported judgments, hypotheses, research requests, hypothesis resolution, and issue analysis.
---

# Reasoning

Owns industry and transaction judgment. It consumes scoped industry definitions
and validated evidence; it does not search or render.

## Outputs

- `industry_issue_analysis.json`
- Future artifacts:
  - `artifacts/hypothesis_store.json`
  - `artifacts/research_request_queue.json`
  - `artifacts/reasoning_qc_report.json`

## Responsibilities

- Decide which findings are supported, directional, caveated, or not researched.
- Explain buyer relevance and pre-mandate pitch relevance.
- Generate research requests when evidence is insufficient.
- Convert supported judgments into page/section argument candidates.

## Hypothesis Resolution

```text
Hypothesis Store
  -> Hypothesis Resolution
      -> supported by evidence -> Supported Judgments
      -> weak/directional -> Research Request Queue
      -> unresolved -> Caveat / Diligence Question Block
```

Allowed deck usage:

- `supported`: headline allowed.
- `directional`: body/context only.
- `caveat_only`: caveat or diligence question only.
- `not_researched`: not allowed in deck claims.

## Commands

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

"$PYTHON_CMD" scripts/validate_hypothesis_store.py \
  --hypothesis-store "$RUN_DIR/artifacts/hypothesis_store.json" \
  --output "$RUN_DIR/artifacts/hypothesis_store_validation.json"

"$PYTHON_CMD" scripts/build_research_request_queue.py \
  --hypothesis-store "$RUN_DIR/artifacts/hypothesis_store.json" \
  --output "$RUN_DIR/artifacts/research_request_queue.json"

"$PYTHON_CMD" scripts/validate_research_request_queue.py \
  --research-request-queue "$RUN_DIR/artifacts/research_request_queue.json" \
  --output "$RUN_DIR/artifacts/research_request_queue_validation.json"

"$PYTHON_CMD" scripts/build_page_argument_pack.py \
  --issue-analysis "$RUN_DIR/industry_issue_analysis.json" \
  --hypothesis-store "$RUN_DIR/artifacts/hypothesis_store.json" \
  --output "$RUN_DIR/artifacts/page_argument_pack.json"

"$PYTHON_CMD" scripts/validate_page_argument_pack.py \
  --page-argument-pack "$RUN_DIR/artifacts/page_argument_pack.json" \
  --output "$RUN_DIR/artifacts/page_argument_pack_validation.json"
```
