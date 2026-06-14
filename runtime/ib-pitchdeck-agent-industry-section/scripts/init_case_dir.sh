#!/usr/bin/env bash
#
# init_case_dir.sh — Create a clean case workspace under cases/<case_name>/source
#
# Usage:
#   ./scripts/init_case_dir.sh "China Base Makeup Brand"

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: ./scripts/init_case_dir.sh <case-name>" >&2
  exit 1
fi

RAW_NAME="$1"
CASE_NAME="$(printf '%s' "$RAW_NAME" | tr ' ' '_' | tr '/:*?"<>|' '_')"
CASE_ROOT="cases/$CASE_NAME"
SOURCE_DIR="$CASE_ROOT/source"
SOURCE_ARTIFACT_DIR="$SOURCE_DIR/artifacts"

mkdir -p "$SOURCE_ARTIFACT_DIR"

touch "$SOURCE_DIR/brief.md"

echo "Case workspace created:"
echo "  $CASE_ROOT"
echo ""
echo "Suggested authoring/source files:"
echo "  $SOURCE_DIR/brief.md"
echo "  $SOURCE_DIR/artifacts/research_evidence_db.json"
echo "  $SOURCE_DIR/industry_issue_analysis.json"
echo "  $SOURCE_DIR/template_registry.json"
echo "  $SOURCE_DIR/deck_blueprint.json"
echo ""
echo "Generated files:"
echo "  $SOURCE_DIR/industry_research_pack.md  # export from research_evidence_db.json"
echo "  $SOURCE_DIR/page_evidence_contract.json"
echo "  $SOURCE_DIR/renderer_spec.json"
echo "  (page_evidence_contract.json and renderer_spec.json are generated from deck_blueprint by scripts/generation/compile_deck_blueprint.py)"
echo ""
echo "Suggested run output:"
echo "  runs/$CASE_NAME/attempt_<timestamp>/"
