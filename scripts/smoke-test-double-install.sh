#!/usr/bin/env bash
#
# Smoke test: double install into a seeded HOME verifies no duplicate slugs.
#
# Acceptance criteria (from plans/fix-merge-duplication.md):
# - Double install into a seeded HOME yields 12 slugs (11 generated + 1 foreign), no duplicates.
# - `replaced` lists the 11 generated slugs.
# - `kept` lists only foreign slugs.
# - Foreign modes preserved in original order.
# - Repeated installs stay stable (regression: pre-fix 11→17 duplication).
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

# Count slug entries using the same YAML parser the CLI uses. This is robust
# to block- vs flow-style serialization (e.g. `customModes: []` seeds).
count_slugs_yaml() {
  MODES_FILE="$1" node -e '
    const y = require("yaml");
    const fs = require("fs");
    const doc = y.parseDocument(fs.readFileSync(process.env.MODES_FILE, "utf8"));
    const seq = doc.contents && doc.contents.get ? doc.contents.get("customModes") : null;
    const items = seq && seq.items ? seq.items : [];
    const slugs = items.map(i => (i && i.get ? i.get("slug") : null)).filter(Boolean);
    console.log(slugs.length);
  ' 2>/dev/null
}

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
FIRST_OUTPUT=$(HOME="$TMP_HOME" node "$CLI" install zoo --global --yes 2>&1)
echo "$FIRST_OUTPUT"
echo ""

# ── Second install (should not create duplicates) ──────────────────────
echo "--- Second install: zoo --global --yes ---"
SECOND_OUTPUT=$(HOME="$TMP_HOME" node "$CLI" install zoo --global --yes 2>&1)
echo "$SECOND_OUTPUT"
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

# ── Verify `replaced` reports the 11 generated slugs ───────────────────
# Acceptance criterion 2: `replaced` lists the 11 generated slugs.
REPLACED_LINE=$(echo "$SECOND_OUTPUT" | grep -m1 'Replaced slugs:' || true)
if [ -z "$REPLACED_LINE" ]; then
  echo "FAIL: no 'Replaced slugs:' line in second install output"
  exit 1
fi

REPLACED_SLUGS=$(echo "$REPLACED_LINE" | sed 's/.*Replaced slugs: *//')
REPLACED_COUNT=$(echo "$REPLACED_SLUGS" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | grep -c '.' || true)
if [ "$REPLACED_COUNT" -ne 11 ]; then
  echo "FAIL: expected 11 replaced slugs, got $REPLACED_COUNT ($REPLACED_SLUGS)"
  exit 1
fi
for slug in "${EXPECTED_GENERATED[@]}"; do
  if ! echo "$REPLACED_SLUGS" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | grep -qx "$slug"; then
    echo "FAIL: generated slug '$slug' missing from 'Replaced slugs'"
    exit 1
  fi
done

# ── Verify `kept` reports only the foreign slug ────────────────────────
# Acceptance criterion 3: `kept` lists only foreign slugs (here: just one).
KEPT_LINE=$(echo "$SECOND_OUTPUT" | grep -m1 'Kept user slugs:' || true)
if [ -z "$KEPT_LINE" ]; then
  echo "FAIL: no 'Kept user slugs:' line in second install output"
  exit 1
fi

KEPT_SLUGS=$(echo "$KEPT_LINE" | sed 's/.*Kept user slugs: *//')
if [ "$KEPT_SLUGS" != "my-custom-mode" ]; then
  echo "FAIL: expected kept slugs 'my-custom-mode', got '$KEPT_SLUGS'"
  exit 1
fi

# ── Regression: repeated installs stay stable (no 11→17 growth) ────────
# Pre-fix, a third install grew the file further (splice of stale indices).
echo ""
echo "--- Third install: regression check for repeat-install stability ---"
HOME="$TMP_HOME" node "$CLI" install zoo --global --yes > /dev/null 2>&1
SLUG_COUNT_3=$(grep -oP '^\s+-\s+slug:\s+\K.*' "$MODES_FILE" | grep -c '.' || true)
UNIQUE_COUNT_3=$(grep -oP '^\s+-\s+slug:\s+\K.*' "$MODES_FILE" | sort -u | wc -l)
if [ "$SLUG_COUNT_3" -ne 12 ] || [ "$UNIQUE_COUNT_3" -ne 12 ]; then
  echo "FAIL: third install changed slug count (total=$SLUG_COUNT_3, unique=$UNIQUE_COUNT_3, expected 12)"
  exit 1
fi
echo "Third install: still 12 unique slugs (PASS)"

# ── Edge case: empty customModes list ──────────────────────────────────
# A fresh HOME with an empty block list must receive all 11 generated modes.
echo ""
echo "--- Edge case: empty customModes list ---"
TMP_HOME_EMPTY="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME" "$TMP_HOME_EMPTY"' EXIT
mkdir -p "$TMP_HOME_EMPTY/.roo"
printf 'customModes: []\n' > "$TMP_HOME_EMPTY/.roo/custom_modes.yaml"
HOME="$TMP_HOME_EMPTY" node "$CLI" install zoo --global --yes > /dev/null 2>&1
EMPTY_COUNT=$(cd "$ROOT_DIR" && count_slugs_yaml "$TMP_HOME_EMPTY/.roo/custom_modes.yaml")
if [ "$EMPTY_COUNT" -ne 11 ]; then
  echo "FAIL: empty customModes list expected 11 slugs, got $EMPTY_COUNT"
  exit 1
fi
echo "Empty customModes list: 11 slugs installed (PASS)"

echo ""
echo "=== Double-install smoke test PASSED ==="
echo "  - 12 slugs total (11 generated + 1 foreign)"
echo "  - No duplicates"
echo "  - Foreign mode preserved in original position"
echo "  - 'replaced' lists all 11 generated slugs"
echo "  - 'kept' lists only the foreign slug"
echo "  - Repeat installs stay stable at 12 slugs"
echo "  - Empty customModes list installs all 11 modes"
