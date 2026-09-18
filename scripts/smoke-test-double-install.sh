#!/usr/bin/env bash
#
# Smoke test: double install into a seeded HOME verifies no duplicate slugs.
#
# Acceptance criteria (from plans/fix-merge-duplication.md):
# - Double install into a seeded HOME yields 12 slugs (11 generated + 1 foreign), no duplicates.
# - `replaced` lists the 11 generated slugs.
# - `kept` lists only foreign slugs.
# - Foreign modes preserved in original order.
#
# Usage: bash scripts/smoke-test-double-install.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CLI="$ROOT_DIR/dist/cli.cjs"

if [ ! -f "$CLI" ]; then
  echo "FAIL: $CLI not found — run 'npm run build' first"
  exit 1
fi

# ── Seeded HOME ────────────────────────────────────────────────────────
# Create a HOME with one foreign mode already present.
TMP_HOME="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME"' EXIT

mkdir -p "$TMP_HOME/.roo"

# Seed custom_modes.yaml with a foreign mode (not in generated slugs).
cat > "$TMP_HOME/.roo/custom_modes.yaml" << 'YAML'
customModes:
  - slug: my-custom-mode
    name: My Custom Mode
    description: A user-defined mode
    roleDefinition: You are a custom assistant.
    whenToUse: Use when custom work is needed.
    customInstructions: Do custom things.
    groups:
      - read
YAML

echo "=== Double-install smoke test: temp HOME=$TMP_HOME ==="
echo ""

# ── First install ──────────────────────────────────────────────────────
echo "--- First install: zoo --global --yes ---"
HOME="$TMP_HOME" node "$CLI" install zoo --global --yes
echo ""

# ── Second install (should not create duplicates) ──────────────────────
echo "--- Second install: zoo --global --yes ---"
HOME="$TMP_HOME" node "$CLI" install zoo --global --yes
echo ""

# ── Verify slug counts ─────────────────────────────────────────────────
MODES_FILE="$TMP_HOME/.roo/custom_modes.yaml"
if [ ! -f "$MODES_FILE" ]; then
  echo "FAIL: modes file missing at $MODES_FILE"
  exit 1
fi

# Extract all slug values from the YAML file.
SLUGS=$(grep -oP '^\s+-\s+slug:\s+\K.*' "$MODES_FILE" || true)
SLUG_COUNT=$(echo "$SLUGS" | grep -c '.' || true)

echo "Slugs found: $SLUG_COUNT"
echo "$SLUGS" | sed 's/^/  /'

if [ "$SLUG_COUNT" -ne 12 ]; then
  echo "FAIL: expected 12 slugs (11 generated + 1 foreign), got $SLUG_COUNT"
  exit 1
fi

# ── Verify no duplicate slugs ──────────────────────────────────────────
UNIQUE_COUNT=$(echo "$SLUGS" | sort -u | wc -l)
if [ "$UNIQUE_COUNT" -ne 12 ]; then
  echo "FAIL: found duplicate slugs (unique=$UNIQUE_COUNT, total=$SLUG_COUNT)"
  echo "Duplicates:"
  echo "$SLUGS" | sort | uniq -d | sed 's/^/  /'
  exit 1
fi

# ── Verify foreign mode is preserved ───────────────────────────────────
if ! echo "$SLUGS" | grep -q '^my-custom-mode$'; then
  echo "FAIL: foreign mode 'my-custom-mode' not found in output"
  exit 1
fi

# ── Verify foreign mode order (should come before generated slugs) ─────
# The foreign mode was in the original file, so it should appear before
# the generated modes which are appended at the end.
FIRST_LINE=$(echo "$SLUGS" | head -1)
if [ "$FIRST_LINE" != "my-custom-mode" ]; then
  echo "FAIL: foreign mode 'my-custom-mode' should be first (got '$FIRST_LINE')"
  exit 1
fi

# ── Verify all 11 generated slugs present ──────────────────────────────
EXPECTED_GENERATED=(
  "orchestrator"
  "investigator"
  "plan"
  "review-code"
  "security-review"
  "review-plan"
  "code"
  "verify"
  "ask"
  "architect"
  "debug"
)

for slug in "${EXPECTED_GENERATED[@]}"; do
  if ! echo "$SLUGS" | grep -q "^${slug}$"; then
    echo "FAIL: expected generated slug '$slug' not found"
    exit 1
  fi
done

echo ""
echo "=== Double-install smoke test PASSED ==="
echo "  - 12 slugs total (11 generated + 1 foreign)"
echo "  - No duplicates"
echo "  - Foreign mode preserved in original position"
