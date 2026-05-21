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

mkdir -p "$SOURCE_DIR"

touch "$SOURCE_DIR/brief.md"

echo "Case workspace created:"
echo "  $CASE_ROOT"
echo ""
echo "Suggested source files:"
echo "  $SOURCE_DIR/brief.md"
echo "  $SOURCE_DIR/industry_input_memo.md"
echo "  $SOURCE_DIR/industry_storyboard.json"
echo "  $SOURCE_DIR/industry_section_ppt_copy.json"
echo ""
echo "Suggested run output:"
echo "  runs/$CASE_NAME/attempt_<timestamp>/"
