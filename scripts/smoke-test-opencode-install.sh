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
# - Every installed agent carries a V1 `permission:` map with at least one
#   `allow` effect (checked with the repo venv python; skipped when absent).
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

# ── 4. Permissions frontmatter on installed agents ──────────────────
echo "--- Step 4: every installed agent carries a V1 permission map ---"

if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
  echo "SKIP: $ROOT_DIR/.venv/bin/python not available — permission assertions not run"
  echo ""
  echo "=== All opencode-install smoke tests passed (step 4 skipped) ==="
  exit 0
fi

# An agent whose rules are all-deny is a misconfiguration: every emitted
# permission map must contain at least one `allow` effect. The v2
# `permissions` list is rejected here: opencode 1.18.35 ignores it. Deeper
# shape and semantics are enforced by scripts/verify.py check (f).
CHECKED=0
for agent in "$AGENTS_DIR"/*.md; do
  slug="$(basename "$agent" .md)"
  if ! "$ROOT_DIR/.venv/bin/python" -c "
import yaml, sys
d = yaml.safe_load(sys.stdin.read().split('---', 2)[1])
assert 'permissions' not in d, 'inert v2 permissions list present'
p = d.get('permission')
assert isinstance(p, dict) and len(p) > 0, 'missing V1 permission map'
def effects(entry):
    return {entry} if isinstance(entry, str) else set(entry.values())
assert any('allow' in effects(v) for v in p.values()), 'no allow effect'
for k in ('lsp','question','external_directory','doom_loop'):
    assert k in p, f'missing new action {k!r} in permission map'
    v = p[k]
    if isinstance(v, str):
        assert v in {'allow','ask','deny'}, f'new action {k!r} effect {v!r} not in allow/ask/deny'
    elif isinstance(v, dict) and v and all(isinstance(pat, str) and pat and isinstance(eff, str) and eff in {'allow','ask','deny'} for pat, eff in v.items()):
        pass  # pattern map is valid for lsp / external_directory
    else:
        raise AssertionError(f'new action {k!r} value {v!r} is not a string in allow/ask/deny nor a non-empty pattern map of such effects')
assert isinstance(p['question'], str), 'question is actionOnly; must be a plain scalar, got ' + type(p['question']).__name__
assert isinstance(p['doom_loop'], str), 'doom_loop is actionOnly; must be a plain scalar, got ' + type(p['doom_loop']).__name__
" < "$agent"; then
    echo "FAIL: agent $slug.md failed a V1 permission map assertion (missing key, invalid effect, or non-scalar actionOnly action)"
    exit 1
  fi
  CHECKED=$((CHECKED + 1))
done

echo "Step 4: PASS ($CHECKED agents carry a permission map with an allow effect)"
echo ""

echo "=== All opencode-install smoke tests passed ==="
