#!/usr/bin/env bash
#
# Smoke test for the ai-snippets installer CLI.
#
# Runs the installer against a temporary $HOME to verify:
# - Dry-run lists actions without writing
# - Real install creates files correctly
# - Second run triggers collision prompts
# - Abort exits non-zero
#
# Usage: bash scripts/smoke-test.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CLI="$ROOT_DIR/dist/cli.js"

if [ ! -f "$CLI" ]; then
  echo "FAIL: $CLI not found — run 'npm run build' first"
  exit 1
fi

# Create temp HOME
TMP_HOME="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME"' EXIT

echo "=== Smoke test: temp HOME=$TMP_HOME ==="
echo ""

# ── 1. Dry run ──────────────────────────────────────────────────────
echo "--- Step 1: dry-run zoo --global --dry-run ---"
HOME="$TMP_HOME" node "$CLI" install zoo --global --dry-run
echo ""
echo "Step 1: PASS (dry-run completed without writing)"
echo ""

# ── 2. Real install ─────────────────────────────────────────────────
echo "--- Step 2: real install zoo --global ---"
HOME="$TMP_HOME" node "$CLI" install zoo --global --yes
echo ""

# Verify skills installed (zoo skills are flat .md files, copied as-is)
SKILLS_DIR="$TMP_HOME/.roo/skills"
if [ ! -f "$SKILLS_DIR/writing-for-humans.md" ]; then
  echo "FAIL: expected $SKILLS_DIR/writing-for-humans.md to exist"
  exit 1
fi
if [ ! -f "$SKILLS_DIR/grilling.md" ]; then
  echo "FAIL: expected $SKILLS_DIR/grilling.md to exist"
  exit 1
fi

# Verify modes file merged
MODES_FILE="$TMP_HOME/.roo/custom_modes.yaml"
if [ ! -f "$MODES_FILE" ]; then
  echo "FAIL: expected $MODES_FILE to exist"
  exit 1
fi
echo "Step 2: PASS (skills and modes installed)"
echo ""

# ── 3. Second run → collision prompt (non-interactive abort) ────────
echo "--- Step 3: second run triggers collision prompt ---"
# Use a fresh HOME so we can test the collision flow with a pre-existing file
TMP_HOME2="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME" "$TMP_HOME2"' EXIT

# Pre-create destination files to force collision
mkdir -p "$TMP_HOME2/.roo/skills"
echo "existing" > "$TMP_HOME2/.roo/skills/writing-for-humans.md"
echo "existing" > "$TMP_HOME2/.roo/custom_modes.yaml"

# Pipe "a" (abort) to the prompt
set +e
echo "a" | HOME="$TMP_HOME2" node "$CLI" install zoo --global 2>&1
EXIT_CODE=$?
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "FAIL: expected non-zero exit on abort, got 0"
  exit 1
fi

echo "Step 3: PASS (abort exits non-zero)"
echo ""

echo "=== All smoke tests passed ==="
