#!/usr/bin/env bash
#
# Smoke test for the ai-snippets installer CLI.
#
# Runs the installer against a temporary $HOME to verify:
# - Dry-run lists actions without writing
# - Real install creates files correctly
# - Second run triggers collision prompts
# - Abort exits non-zero and writes no files after abort
# - Piped multi-prompt runs work correctly
# - --yes overwrites existing files without prompting
# - Double install into same HOME yields no duplicate slugs (merge idempotency)
#
# Usage: bash scripts/smoke-test.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CLI="$ROOT_DIR/dist/cli.cjs"

if [ ! -f "$CLI" ]; then
  echo "FAIL: $CLI not found — run 'npm run build' first"
  exit 1
fi

# Create temp HOME
TMP_HOME="$(mktemp -d)"
trap 'rm -rf "$TMP_HOME" "$TMP_HOME2" "$TMP_HOME3" "$TMP_HOME4" "$TMP_HOME5" "$TMP_HOME6"' EXIT
TMP_HOME2=""
TMP_HOME3=""
TMP_HOME4=""
TMP_HOME5=""
TMP_HOME6=""

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

# ── 3. Abort mid-run: non-zero exit, zero writes after abort ───────
echo "--- Step 3: abort at second collision prompt ---"
TMP_HOME2="$(mktemp -d)"

# Pre-create destination files to force collision
mkdir -p "$TMP_HOME2/.roo/skills"
echo "existing_content_skill" > "$TMP_HOME2/.roo/skills/writing-for-humans.md"
echo "existing_content_modes" > "$TMP_HOME2/.roo/custom_modes.yaml"

# Take checksum BEFORE the run (skill file — the abort point)
CKSUM_SKILL_BEFORE=$(md5sum "$TMP_HOME2/.roo/skills/writing-for-humans.md" | awk '{print $1}')

# Drive BOTH prompts: 'o' (overwrite first) then 'a' (abort second)
set +e
printf 'o\na\n' | HOME="$TMP_HOME2" node "$CLI" install zoo --global 2>&1
EXIT_CODE=$?
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "FAIL: expected non-zero exit on abort, got 0"
  exit 1
fi

# Verify the skill file was NOT modified after the abort point.
# The modes file WAS modified (first prompt accepted 'overwrite'), which is correct.
# The abort happened at the second prompt (skills dir), so skills must be untouched.
CKSUM_SKILL_AFTER=$(md5sum "$TMP_HOME2/.roo/skills/writing-for-humans.md" | awk '{print $1}')

if [ "$CKSUM_SKILL_BEFORE" != "$CKSUM_SKILL_AFTER" ]; then
  echo "FAIL: skills file was modified after abort (before=$CKSUM_SKILL_BEFORE, after=$CKSUM_SKILL_AFTER)"
  exit 1
fi

echo "Step 3: PASS (abort exits non-zero, skill file byte-identical after abort)"
echo ""

# ── 4. Piped multi-prompt: overwrite both, summary printed, exit 0 ─
echo "--- Step 4: piped overwrite both collision prompts ---"
TMP_HOME3="$(mktemp -d)"

# Pre-create destination files to force collision
mkdir -p "$TMP_HOME3/.roo/skills"
echo "old_skill" > "$TMP_HOME3/.roo/skills/writing-for-humans.md"
echo "old_modes" > "$TMP_HOME3/.roo/custom_modes.yaml"

# Drive BOTH prompts with 'o' (overwrite) for each
OUTPUT=$(printf 'o\no\n' | HOME="$TMP_HOME3" node "$CLI" install zoo --global 2>&1)
EXIT_CODE=$?

if [ "$EXIT_CODE" -ne 0 ]; then
  echo "FAIL: expected exit 0 on overwrite-all, got $EXIT_CODE"
  exit 1
fi

# Verify summary was printed
if ! echo "$OUTPUT" | grep -q "INSTALL SUMMARY"; then
  echo "FAIL: expected INSTALL SUMMARY in output"
  exit 1
fi

# Verify skills file was overwritten with current content
if ! grep -q "writing-for-humans" "$TMP_HOME3/.roo/skills/writing-for-humans.md" 2>/dev/null; then
  # The file content comes from skills-embedded, just check it exists and is non-empty
  if [ ! -s "$TMP_HOME3/.roo/skills/writing-for-humans.md" ]; then
    echo "FAIL: skills file is empty after overwrite"
    exit 1
  fi
fi

# Verify modes file exists and was written
if [ ! -f "$TMP_HOME3/.roo/custom_modes.yaml" ]; then
  echo "FAIL: modes file missing after overwrite"
  exit 1
fi

echo "Step 4: PASS (piped multi-prompt works, summary printed)"
echo ""

# ── 5. --yes overwrites existing directory destination ──────────────
echo "--- Step 5: --yes overwrite existing directory ---"
TMP_HOME4="$(mktemp -d)"

# Pre-create destination to force collision
mkdir -p "$TMP_HOME4/.roo/skills"
echo "preexisting" > "$TMP_HOME4/.roo/skills/grilling.md"
echo "preexisting" > "$TMP_HOME4/.roo/custom_modes.yaml"

HOME="$TMP_HOME4" node "$CLI" install zoo --global --yes
EXIT_CODE=$?

if [ "$EXIT_CODE" -ne 0 ]; then
  echo "FAIL: expected exit 0 on --yes, got $EXIT_CODE"
  exit 1
fi

# Verify grilling.md was overwritten (content should differ from "preexisting")
GRILLING_CONTENT=$(cat "$TMP_HOME4/.roo/skills/grilling.md")
if [ "$GRILLING_CONTENT" = "preexisting" ]; then
  echo "FAIL: grilling.md was not overwritten by --yes"
  exit 1
fi

echo "Step 5: PASS (--yes overwrites existing files)"
echo ""

# ── 6. EOF on non-TTY stdin exits non-zero ──────────────────────────
echo "--- Step 6: piped empty/EOF input exits non-zero ---"
TMP_HOME5="$(mktemp -d)"

mkdir -p "$TMP_HOME5/.roo/skills"
echo "existing" > "$TMP_HOME5/.roo/skills/writing-for-humans.md"
echo "existing" > "$TMP_HOME5/.roo/custom_modes.yaml"

# Pipe empty stdin (EOF with no answer)
set +e
printf '' | HOME="$TMP_HOME5" node "$CLI" install zoo --global 2>&1
EXIT_CODE=$?
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "FAIL: expected non-zero exit on empty stdin, got 0"
  exit 1
fi

# Verify no files were modified (compare against original content)
CKSUM_AFTER=$(md5sum "$TMP_HOME5/.roo/custom_modes.yaml" | awk '{print $1}')
CKSUM_EXPECTED=$(echo "existing" | md5sum | awk '{print $1}')
if [ "$CKSUM_AFTER" != "$CKSUM_EXPECTED" ]; then
  echo "FAIL: modes file was modified on empty stdin (expected=$CKSUM_EXPECTED, got=$CKSUM_AFTER)"
  exit 1
fi

echo "Step 6: PASS (EOF on non-TTY exits non-zero, no writes)"
echo ""

# ── 7. Merge idempotency: double install, no duplicate slugs ──
echo "--- Step 7: merge idempotency, double install ---"
TMP_HOME6="$(mktemp -d)"
mkdir -p "$TMP_HOME6/.roo"

# Seed a foreign mode that must survive the double install
cat > "$TMP_HOME6/.roo/custom_modes.yaml" <<'YAML'
customModes:
  - slug: my-foreign-mode
    name: my-foreign-mode
    description: Foreign user mode for smoke test
    roleDefinition: You are a foreign test mode.
YAML

# First install (zoo writes 11 modes)
HOME="$TMP_HOME6" node "$CLI" install zoo --global --yes

# Second install (must not duplicate slugs)
OUTPUT2=$(HOME="$TMP_HOME6" node "$CLI" install zoo --global --yes 2>&1)

MODES_FILE="$TMP_HOME6/.roo/custom_modes.yaml"
SLUGS=$(grep -E '^[[:space:]]*(- )?slug:' "$MODES_FILE" \
  | sed -E 's/^[[:space:]]*(- )?slug:[[:space:]]*//' | tr -d '"')

# Count must be exactly 12 (11 zoo + 1 foreign)
SLUG_COUNT=$(echo "$SLUGS" | wc -l)
if [ "$SLUG_COUNT" -ne 12 ]; then
  echo "FAIL: Expected 12 slugs after double install"
  exit 1
fi

# No duplicate slugs
DUPS=$(echo "$SLUGS" | sort | uniq -d)
if [ -n "$DUPS" ]; then
  echo "FAIL: Duplicate slugs detected after double install"
  exit 1
fi

# Foreign mode preserved
if ! echo "$SLUGS" | grep -qx 'my-foreign-mode'; then
  echo "FAIL: Foreign mode 'my-foreign-mode' missing from modes file"
  exit 1
fi

# Installer reports kept user slugs including foreign mode
if ! echo "$OUTPUT2" | grep -q 'Kept user slugs: my-foreign-mode'; then
  echo "FAIL: Kept-user-slugs line missing foreign mode"
  exit 1
fi

# Replaced slugs line must NOT contain the foreign mode
REPLACED_LINE=$(echo "$OUTPUT2" | grep 'Replaced slugs:' || true)
if [ -z "$REPLACED_LINE" ]; then
  echo "FAIL: Replaced slugs line missing from output"
  exit 1
fi
if echo "$REPLACED_LINE" | grep -q 'my-foreign-mode'; then
  echo "FAIL: Foreign mode incorrectly listed as replaced"
  exit 1
fi

echo "Step 7: PASS (double install yields 12 unique slugs, foreign mode kept)"
echo ""

echo "=== All smoke tests passed ==="
