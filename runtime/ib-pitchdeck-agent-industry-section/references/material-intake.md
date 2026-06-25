# Material Intake

## Purpose

Material Intake protects what the user actually gave the team. Capture the brief, files, URLs, reports, notes, and templates faithfully before any interpretation starts. This role is about clean provenance, not industry storytelling.

## What To Preserve

- the user's original brief;
- each material's source type and access level;
- project facts separate from industry facts;
- user-provided claims separate from public evidence;
- ambiguous or missing fields that later roles should not silently infer.

If the user provides only a short text brief, start the run with:

```bash
"$PYTHON_CMD" scripts/pipeline.py start-brief --case-name "<case>" --run-dir "$RUN_DIR" --brief-text "<exact user brief>"
```

Add `--template-file "<path/to/template.pptx>"` when the user supplies a PPT/POTX template. The template is registered for Template/Output use, not as evidence.

## How To Think

Register first, interpret second. A useful intake record lets Scoping understand the market, lets Research know which user-curated materials exist, and lets Knowledge distinguish target-level facts from external evidence.

`raw_text_preview` is captured text only. It is not evidence authorization. If a user-curated industry report looks useful, classify it cleanly so Knowledge or Research can decide how to use it later.

## What To Pass On

Hand Knowledge a short, source-faithful view of:

- material list;
- target/company/transaction facts explicitly provided by the user;
- industry facts found in user materials;
- ambiguous fields;
- parsing or access limitations.

Do not pass downstream conclusions such as market attractiveness, buyer interest, valuation, or page claims.
