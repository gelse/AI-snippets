#!/usr/bin/env bash
#
# Smoke test: make install-opencode-global installs opencode agents and skills.
#
# Acceptance criteria:
# - `make opencode && make install-opencode-global` with an isolated
#   $OPENCODE_CONFIG_HOME (temp dir) exits 0 and prints no `cp: cannot stat`
#   errors.
# - Agents land at $OPENCODE_CONFIG_HOME/opencode/agents/*.md (one per
#   generated agent).
# - Every generated skill lands at
#   $OPENCODE_CONFIG_HOME/opencode/skills/<name>/SKILL.md (directory form),
#   with a non-zero expected skill count; companion side files land alongside.
#
# Usage: bash scripts/smoke-test-opencode-install.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

TMP_CONFIG_HOME="$(mktemp -d)"
trap 'rm -rf "$TMP_CONFIG_HOME"' EXIT

echo "=== OpenCode install smoke test: OPENCODE_CONFIG_HOME=$TMP_CONFIG_HOME ==="
echo ""

# ── 1. Generate and install into the isolated config home ───────────
echo "--- Step 1: make opencode && make install-opencode-global ---"
set +e
MAKE_OUTPUT=$(cd "$ROOT_DIR" && LC_ALL=C make opencode && LC_ALL=C make install-opencode-global OPENCODE_CONFIG_HOME="$TMP_CONFIG_HOME" 2>&1)
EXIT_CODE=$?
set -e
echo "$MAKE_OUTPUT"
echo ""

if [ "$EXIT_CODE" -ne 0 ]; then
  echo "FAIL: expected exit 0 from make, got $EXIT_CODE"
  exit 1
fi

# Primary regression gate: pre-fix, make exited 0 but the unmatched glob made
# cp print "cannot stat 'output/opencode/skill/*.md'". LC_ALL=C (set on the
# make invocation) keeps the message stable across locales.
if echo "$MAKE_OUTPUT" | grep -q "cannot stat"; then
  echo "FAIL: 'cp: cannot stat' in make output — skill glob matched no files"
  exit 1
fi
echo "Step 1: PASS (make exited 0, no cp errors)"
echo ""

# ── 2. Agents installed ─────────────────────────────────────────────
echo "--- Step 2: agents under \$OPENCODE_CONFIG_HOME/opencode/agents/ ---"
AGENTS_DIR="$TMP_CONFIG_HOME/opencode/agents"

if [ ! -d "$ROOT_DIR/output/opencode/agents" ]; then
  echo "FAIL: $ROOT_DIR/output/opencode/agents missing — 'make opencode' did not run"
  exit 1
fi

AGENT_SRC_COUNT=$(find "$ROOT_DIR/output/opencode/agents" -maxdepth 1 -name '*.md' | wc -l)
AGENT_DST_COUNT=$(find "$AGENTS_DIR" -maxdepth 1 -name '*.md' 2>/dev/null | wc -l)

if [ "$AGENT_SRC_COUNT" -eq 0 ]; then
  echo "FAIL: no generated agents in output/opencode/agents — nothing to assert"
  exit 1
fi

if [ "$AGENT_DST_COUNT" -ne "$AGENT_SRC_COUNT" ]; then
  echo "FAIL: expected $AGENT_SRC_COUNT agents installed, found $AGENT_DST_COUNT"
  exit 1
fi
echo "Step 2: PASS ($AGENT_DST_COUNT agents installed)"
echo ""

# ── 3. Skills installed in directory form ───────────────────────────
echo "--- Step 3: every generated skill at \$OPENCODE_CONFIG_HOME/opencode/skills/<name>/SKILL.md ---"
SKILLS_DST_DIR="$TMP_CONFIG_HOME/opencode/skills"

if [ ! -d "$ROOT_DIR/output/opencode/skill" ]; then
  echo "FAIL: $ROOT_DIR/output/opencode/skill missing — 'make opencode' did not run"
  exit 1
fi

EXPECTED_SKILLS=$(find "$ROOT_DIR/output/opencode/skill" -mindepth 1 -maxdepth 1 -type d | wc -l)
if [ "$EXPECTED_SKILLS" -eq 0 ]; then
  echo "FAIL: no generated skills in output/opencode/skill — nothing to assert"
  exit 1
fi

INSTALLED=0
for skill_dir in "$ROOT_DIR"/output/opencode/skill/*/; do
  name="$(basename "$skill_dir")"
  if [ ! -f "$SKILLS_DST_DIR/$name/SKILL.md" ]; then
    echo "FAIL: expected $SKILLS_DST_DIR/$name/SKILL.md (directory form)"
    exit 1
  fi
  # Companion side files must land alongside SKILL.md
  for src in "$skill_dir"*; do
    base="$(basename "$src")"
    if [ -f "$src" ] && [ "$base" != "SKILL.md" ] && [ ! -e "$SKILLS_DST_DIR/$name/$base" ]; then
      echo "FAIL: expected side file $SKILLS_DST_DIR/$name/$base beside SKILL.md"
      exit 1
    fi
  done
  INSTALLED=$((INSTALLED + 1))
done

if [ "$INSTALLED" -ne "$EXPECTED_SKILLS" ]; then
  echo "FAIL: expected $EXPECTED_SKILLS skills installed, verified $INSTALLED"
  exit 1
fi
echo "Step 3: PASS ($INSTALLED skills installed as <name>/SKILL.md, side files included)"
echo ""

echo "=== All opencode-install smoke tests passed ==="
