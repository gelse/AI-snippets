"""Verify modes.json integrity and zoo emitter round-trip fidelity.

Usage:
    .venv/bin/python scripts/verify.py

Exits non-zero with a clear message on failure.
"""

import json
import re
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Required keys per mode (excluding optional 'deprecated')
REQUIRED_MODE_KEYS = {
    "slug",
    "name",
    "description",
    "roleDefinition",
    "whenToUse",
    "customInstructions",
    "groups",
    "source",
    "instantiation",
}

REQUIRED_TOP_KEYS = {"customModes", "skills", "permissions"}

# Required keys per non-deprecated mode's permissions entry (global
# terminology; 'task' maps to opencode's 'subagent' action at emit time)
REQUIRED_PERMISSION_KEYS = {
    "edit",
    "shell",
    "read",
    "glob",
    "grep",
    "skill",
    "task",
}
VALID_PERMISSION_EFFECTS = {"allow", "ask", "deny"}


def fail(msg):
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def ok(msg):
    print(f"  OK: {msg}")


# ---------------------------------------------------------------------------
# (a) Structural validation of modes.json
# ---------------------------------------------------------------------------

def validate_structure():
    """Load modes.json and assert valid JSON, required keys, unique slugs,
    groups shape, permissions coverage, and skill file existence."""
    print("[a] Structural validation")

    json_path = REPO_ROOT / "modes.json"
    if not json_path.exists():
        fail("modes.json not found")

    try:
        with open(json_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON: {exc}")

    ok("Valid JSON")

    # Top-level keys
    missing_top = REQUIRED_TOP_KEYS - set(data.keys())
    if missing_top:
        fail(f"Missing top-level keys: {missing_top}")
    ok(f"Top-level keys present: {sorted(data.keys())}")

    # Permissions block: dict of slug -> {edit, shell, read, glob, grep,
    # skill, task}; per-mode entries are validated in the mode loop below
    permissions = data["permissions"]
    if not isinstance(permissions, dict):
        fail(
            "Top-level 'permissions' must be a dict; got "
            f"{type(permissions).__name__}"
        )

    # Modes
    modes = data["customModes"]
    if not isinstance(modes, list) or len(modes) == 0:
        fail("customModes must be a non-empty list")
    ok(f"{len(modes)} modes found")

    slugs = []
    for i, mode in enumerate(modes):
        slug = mode.get("slug", f"<missing at index {i}>")
        if not re.fullmatch(r"[a-z0-9-]+", slug):
            fail(f"Mode slug '{slug}' must match ^[a-z0-9-]+$")
        slugs.append(slug)

        missing = REQUIRED_MODE_KEYS - set(mode.keys())
        if missing:
            fail(f"Mode '{slug}' missing keys: {missing}")

        # Validate customInstructions is a valid agent file reference
        ci = mode.get("customInstructions", "")
        expected_ci = f"agents/{slug}.md"
        if ci != expected_ci:
            fail(
                f"Mode '{slug}' customInstructions must be "
                f"'{expected_ci}', got '{ci}'"
            )
        ci_path = REPO_ROOT / ci
        if not ci_path.exists():
            fail(f"Mode '{slug}' agent file not found: {ci_path}")
        if not ci_path.read_text().strip():
            fail(f"Mode '{slug}' agent file is empty: {ci_path}")

        # instantiation value check
        inst = mode.get("instantiation")
        if inst not in {"primary", "subagent", "all"}:
            fail(
                f"Mode '{slug}' instantiation must be one of "
                f"'primary', 'subagent', 'all'; got '{inst}'"
            )

        # Groups shape: list of strings or [str, dict]
        groups = mode.get("groups", [])
        if not isinstance(groups, list):
            fail(f"Mode '{slug}' groups must be a list")
        for g in groups:
            if isinstance(g, str):
                continue
            if isinstance(g, list):
                if len(g) < 1 or not isinstance(g[0], str):
                    fail(f"Mode '{slug}' nested group must start with a string: {g}")
                if len(g) >= 2 and not isinstance(g[1], dict):
                    fail(f"Mode '{slug}' nested group second element must be a dict: {g}")
            else:
                fail(f"Mode '{slug}' group entry must be string or list: {g!r}")

        # Permissions entry: required for every non-deprecated mode
        # (deprecated modes are skipped by the opencode emitter)
        if not mode.get("deprecated"):
            perms = permissions.get(slug)
            if perms is None:
                fail(f"Mode '{slug}' missing 'permissions' entry")
            if not isinstance(perms, dict):
                fail(
                    f"Mode '{slug}' permissions entry must be a dict; got "
                    f"{type(perms).__name__}"
                )
            if set(perms.keys()) != REQUIRED_PERMISSION_KEYS:
                fail(
                    f"Mode '{slug}' permissions keys must be exactly "
                    f"{sorted(REQUIRED_PERMISSION_KEYS)}; got {sorted(perms.keys())}"
                )
            for key, effect in perms.items():
                if effect not in VALID_PERMISSION_EFFECTS:
                    fail(
                        f"Mode '{slug}' permissions '{key}' must be one of "
                        f"{sorted(VALID_PERMISSION_EFFECTS)}; got '{effect}'"
                    )

    ok("All modes have required keys and valid groups shape")

    # Inverse check: every permissions key must name a non-deprecated mode
    for key in permissions:
        source = next((m for m in modes if m["slug"] == key), None)
        if source is None or source.get("deprecated"):
            fail(f"permissions key '{key}' is not a known non-deprecated mode slug")
    ok(f"Permissions block: {len(permissions)} entries, all non-deprecated slugs")

    # Unique slugs
    seen = set()
    for s in slugs:
        if s in seen:
            fail(f"Duplicate slug: {s}")
        seen.add(s)
    ok(f"All {len(slugs)} slugs unique")

    # Skills — accept skills/{name}.md (flat) or skills/{name}/SKILL.md (directory)
    skills = data.get("skills", [])
    valid_forms = {}  # name -> set of forms seen ("flat", "dir")
    for skill in skills:
        if "name" not in skill or "file" not in skill:
            fail(f"Skill entry missing 'name' or 'file': {skill}")
        name = skill["name"]
        if not re.fullmatch(r"[a-z0-9-]+", name):
            fail(f"Skill name '{name}' must match ^[a-z0-9-]+$")

        flat_path = f"skills/{name}.md"
        dir_path = f"skills/{name}/SKILL.md"

        if skill["file"] == flat_path:
            form = "flat"
        elif skill["file"] == dir_path:
            form = "dir"
        else:
            fail(
                f"Skill 'file' mismatch for '{name}': "
                f"expected '{flat_path}' or '{dir_path}', "
                f"got '{skill['file']}'"
            )

        if name not in valid_forms:
            valid_forms[name] = set()
        valid_forms[name].add(form)

        skill_path = REPO_ROOT / skill["file"]
        if not skill_path.exists():
            fail(f"Skill file not found: {skill_path}")

    # Duplicate skill name check
    seen_names = []
    for skill in skills:
        name = skill["name"]
        if name in seen_names:
            fail(f"Duplicate skill name: '{name}'")
        seen_names.append(name)

    # Flat + directory coexistence check
    for name, forms in valid_forms.items():
        if "flat" in forms and "dir" in forms:
            fail(
                f"Skill '{name}' has both flat form (skills/{name}.md) "
                f"and directory form (skills/{name}/SKILL.md) — "
                f"use only one"
            )

    ok(f"All {len(skills)} skill files exist; no duplicates or coexistence conflicts")

    return data


# ---------------------------------------------------------------------------
# (b) Round-trip: emit to zoo, load back, deep-compare
# ---------------------------------------------------------------------------

def round_trip(data):
    """Emit to a temp dir via zoo emitter, yaml.safe_load the result,
    and deep-compare customModes to the JSON source (ignoring 'deprecated')."""
    print("[b] Round-trip verification")

    with tempfile.TemporaryDirectory() as tmpdir:
        # Import and run zoo emitter
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from generate import emit_zoo, resolve_custom_instructions

        # Resolve agent file references so emitted content matches file contents
        resolved = json.loads(json.dumps(data))  # deep copy
        resolved["customModes"] = resolve_custom_instructions(resolved["customModes"])
        emit_zoo(resolved, Path(tmpdir))

        roomodes_path = Path(tmpdir) / "zoo" / ".roomodes"
        if not roomodes_path.exists():
            fail("Zoo emitter did not create .roomodes")

        with open(roomodes_path) as f:
            emitted = yaml.safe_load(f)

    if "customModes" not in emitted:
        fail("Emitted .roomodes missing 'customModes' key")

    emitted_modes = emitted["customModes"]
    json_modes = resolved["customModes"]

    if len(emitted_modes) != len(json_modes):
        fail(
            f"Mode count mismatch: emitted {len(emitted_modes)} vs "
            f"JSON {len(json_modes)}"
        )

    for i, (em, jm) in enumerate(zip(emitted_modes, json_modes)):
        slug = jm.get("slug", f"<index {i}>")

        # Strip 'deprecated' from JSON mode for comparison
        jm_clean = {k: v for k, v in jm.items() if k != "deprecated"}

        if set(em.keys()) != set(jm_clean.keys()):
            fail(
                f"Mode '{slug}' key mismatch:\n"
                f"  emitted keys: {sorted(em.keys())}\n"
                f"  expected keys: {sorted(jm_clean.keys())}"
            )

        for key, expected in jm_clean.items():
            if em[key] != expected:
                fail(
                    f"Mode '{slug}' value mismatch for key '{key}':\n"
                    f"  emitted: {em[key]!r}\n"
                    f"  expected: {expected!r}"
                )

    ok(f"All {len(emitted_modes)} modes round-trip match (ignoring 'deprecated')")


# ---------------------------------------------------------------------------
# (c) OpenCode agents: mode must match the mode's instantiation value
# ---------------------------------------------------------------------------

def verify_opencode_agent_modes():
    """Emit opencode agents to a temp dir and assert frontmatter mode matches
    the mode's ``instantiation`` value (defaulting to ``all`` when absent).

    The opencode emitter writes ``mode: <instantiation>`` so each agent's
    visibility is driven by modes.json: ``primary`` agents appear in the
    primary TUI picker, ``subagent`` agents are only invocable as subagents,
    and ``all`` agents are available in both places.
    """
    print("[c] OpenCode agent mode verification")

    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from generate import (
            FileRegexNotImplemented,
            emit_opencode,
            resolve_custom_instructions,
        )

        json_path = REPO_ROOT / "modes.json"
        with open(json_path) as f:
            data = json.load(f)

        resolved = json.loads(json.dumps(data))
        resolved["customModes"] = resolve_custom_instructions(resolved["customModes"])
        try:
            emit_opencode(resolved, Path(tmpdir))
        except FileRegexNotImplemented as exc:
            fail(f"OpenCode emitter: {exc}")

        agents_dir = Path(tmpdir) / "opencode" / "agents"
        if not agents_dir.exists():
            fail("OpenCode emitter did not create agents/ directory")

        agent_files = sorted(agents_dir.glob("*.md"))
        if not agent_files:
            fail("No agent .md files found in emitted opencode/agents/")

        for agent_file in agent_files:
            content = agent_file.read_text()
            # Parse frontmatter between --- delimiters
            if not content.startswith("---\n"):
                fail(f"Agent {agent_file.name}: missing frontmatter")

            end = content.index("---", 4)
            fm_text = content[4:end]

            m = re.search(r"^mode:\s*(.+)$", fm_text, re.MULTILINE)
            if not m:
                fail(f"Agent {agent_file.name}: missing 'mode' field in frontmatter")

            mode_value = m.group(1).strip().strip('"').strip("'")

            slug = agent_file.stem
            source_mode = next(
                (m for m in data["customModes"] if m["slug"] == slug), None
            )
            if source_mode is None:
                fail(f"Agent {agent_file.name}: no matching mode in modes.json")

            expected = source_mode.get("instantiation", "all")
            if mode_value != expected:
                fail(
                    f"Agent {agent_file.name}: mode is '{mode_value}', "
                    f"expected '{expected}' (from instantiation)"
                )

            ok(f"{agent_file.name}: mode={mode_value}")

    ok(f"All {len(agent_files)} opencode agents match their instantiation value")


# ---------------------------------------------------------------------------
# (d) OpenCode agents: model must match models/mapping.yaml, in field position
# ---------------------------------------------------------------------------

def load_agent_model_mapping():
    """Load models/mapping.yaml and build an agent-slug -> model-id dict.

    Mirrors ``generate.load_model_mapping``: only the ``agent`` and ``model``
    fields of each ``agent-mapping`` entry are used; ``fallbacks`` are ignored.
    """
    with open(REPO_ROOT / "models" / "mapping.yaml") as f:
        data = yaml.safe_load(f)
    return {
        entry["agent"]: entry["model"]
        for entry in data.get("model-mapping", {}).get("agent-mapping", [])
        if entry.get("agent") and entry.get("model")
    }


def verify_opencode_agent_models():
    """Emit opencode agents to a temp dir and assert each frontmatter carries
    ``model: litellm/<model_id>`` matching models/mapping.yaml for that slug.

    Also asserts field position: the ``model`` key must appear after ``mode``,
    and ``permissions`` (plural list) appears after ``model`` when present.
    """
    print("[d] OpenCode agent model verification")

    model_by_slug = load_agent_model_mapping()

    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from generate import (
            FileRegexNotImplemented,
            emit_opencode,
            resolve_custom_instructions,
        )

        json_path = REPO_ROOT / "modes.json"
        with open(json_path) as f:
            data = json.load(f)

        resolved = json.loads(json.dumps(data))
        resolved["customModes"] = resolve_custom_instructions(resolved["customModes"])
        try:
            emit_opencode(resolved, Path(tmpdir))
        except FileRegexNotImplemented as exc:
            fail(f"OpenCode emitter: {exc}")

        agents_dir = Path(tmpdir) / "opencode" / "agents"
        if not agents_dir.exists():
            fail("OpenCode emitter did not create agents/ directory")

        agent_files = sorted(agents_dir.glob("*.md"))
        if not agent_files:
            fail("No agent .md files found in emitted opencode/agents/")

        for agent_file in agent_files:
            content = agent_file.read_text()
            if not content.startswith("---\n"):
                fail(f"Agent {agent_file.name}: missing frontmatter")

            end = content.index("---", 4)
            fm_text = content[4:end]

            # Ordered top-level frontmatter keys (nested keys are indented,
            # so the column-0 anchor excludes them).
            keys = re.findall(r"^([A-Za-z][\w-]*):", fm_text, re.MULTILINE)

            slug = agent_file.stem
            expected_model = model_by_slug.get(slug)

            # Defensive default: slugs without a mapping entry legitimately
            # carry no 'model' field (the emitter skips it) — skip checks.
            if expected_model is None:
                if "model" in keys:
                    fail(
                        f"Agent {agent_file.name}: has 'model' field but no "
                        f"mapping entry in mapping.yaml"
                    )
                ok(f"{agent_file.name}: model=(no mapping entry, skipped)")
                continue

            if "model" not in keys:
                fail(
                    f"Agent {agent_file.name}: missing 'model' field in "
                    f"frontmatter (mapping has model={expected_model!r})"
                )

            m = re.search(r"^model:\s*(.+)$", fm_text, re.MULTILINE)
            model_value = m.group(1).strip().strip('"').strip("'")

            expected_value = f"litellm/{expected_model}"
            if model_value != expected_value:
                fail(
                    f"Agent {agent_file.name}: model is '{model_value}', "
                    f"expected '{expected_value}' (from mapping.yaml)"
                )

            # Field position: description < mode < model < permissions
            if keys[:2] != ["description", "mode"]:
                fail(
                    f"Agent {agent_file.name}: frontmatter must start with "
                    f"'description', 'mode'; got {keys[:2]}"
                )
            model_idx = keys.index("model")
            mode_idx = keys.index("mode")
            if model_idx != mode_idx + 1:
                fail(
                    f"Agent {agent_file.name}: 'model' must come directly "
                    f"after 'mode'; key order is {keys}"
                )
            if "permissions" in keys and keys.index("permissions") < model_idx:
                fail(
                    f"Agent {agent_file.name}: 'permissions' must come after "
                    f"'model'; key order is {keys}"
                )

            ok(f"{agent_file.name}: model={model_value}")

    ok(f"All {len(agent_files)} opencode agents match mapping.yaml (model + position)")


# ---------------------------------------------------------------------------
# (e) OpenCode agents: permissions list content and rule semantics
# ---------------------------------------------------------------------------

def _scoped_edit_glob(groups, fileregex_to_glob):
    """Return the mapped glob for the mode's first fileRegex edit group.

    Mirrors the emitter's nested-``["edit", {"fileRegex": "..."}]`` shape
    check so the semantic comparison in check (e) reads the mode's groups
    directly instead of trusting the emitter's output. An unmapped pattern
    raises ``FileRegexNotImplemented`` like the emitter does, keeping this
    an independent fail-loud oracle rather than a silent fallback.
    """
    from generate import FileRegexNotImplemented  # caller sets up sys.path

    for g in groups:
        if not (isinstance(g, list) and g and g[0] == "edit"):
            continue
        if len(g) < 2 or not isinstance(g[1], dict):
            continue
        file_regex = g[1].get("fileRegex")
        if file_regex is None:
            continue
        if file_regex not in fileregex_to_glob:
            raise FileRegexNotImplemented(
                f"no FILEREGEX_TO_GLOB mapping for fileRegex {file_regex!r}"
            )
        return fileregex_to_glob[file_regex]
    return None


def verify_opencode_agent_permissions():
    """Emit opencode agents to a temp dir and assert each frontmatter's
    ``permissions`` list matches the mode's entry in modes.json.permissions.

    Per agent: list shape (list of ``{action, resource, effect}`` rules),
    the opencode action/effect vocabularies, round-trip equivalence with
    ``translate_opencode_permissions``, the last-match-wins semantics for
    scoped edit rules (broad deny first, scoped allow last; no scoped rule
    when edit is denied/gated or has no scoped group), and the stable
    action ordering edit, shell, read, glob, grep, skill, subagent.
    """
    print("[e] OpenCode agent permissions verification")

    json_path = REPO_ROOT / "modes.json"
    with open(json_path) as f:
        data = json.load(f)

    modes_by_slug = {m["slug"]: m for m in data["customModes"]}

    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from generate import (
            FILEREGEX_TO_GLOB,
            OPENCODE_PERMISSION_ACTIONS,
            OPENCODE_PERMISSION_EFFECTS,
            FileRegexNotImplemented,
            emit_opencode,
            resolve_custom_instructions,
            translate_opencode_permissions,
        )

        resolved = json.loads(json.dumps(data))
        resolved["customModes"] = resolve_custom_instructions(resolved["customModes"])
        try:
            emit_opencode(resolved, Path(tmpdir))
        except FileRegexNotImplemented as exc:
            fail(f"OpenCode emitter: {exc}")

        agents_dir = Path(tmpdir) / "opencode" / "agents"
        if not agents_dir.exists():
            fail("OpenCode emitter did not create agents/ directory")

        agent_files = sorted(agents_dir.glob("*.md"))
        if not agent_files:
            fail("No agent .md files found in emitted opencode/agents/")

        for agent_file in agent_files:
            slug = agent_file.stem
            content = agent_file.read_text()
            if not content.startswith("---\n"):
                fail(f"Agent {slug}.md: missing frontmatter")

            end = content.index("---", 4)
            fm = yaml.safe_load(content[4:end])

            source_mode = modes_by_slug.get(slug)
            if source_mode is None:
                fail(f"Agent {slug}.md: no matching mode in modes.json")

            permissions = fm.get("permissions")
            if not isinstance(permissions, list) or not permissions:
                fail(
                    f"Agent {slug}.md: 'permissions' must be a non-empty "
                    f"list; got {permissions!r}"
                )

            # Rule shape and action/effect vocabularies
            for rule in permissions:
                if not isinstance(rule, dict) or set(rule.keys()) != {
                    "action",
                    "resource",
                    "effect",
                }:
                    fail(f"Agent {slug}.md: malformed permission rule: {rule!r}")
                if rule["action"] not in OPENCODE_PERMISSION_ACTIONS:
                    fail(
                        f"Agent {slug}.md: rule action '{rule['action']}' "
                        f"not in opencode action set "
                        f"{sorted(OPENCODE_PERMISSION_ACTIONS)}"
                    )
                if rule["effect"] not in OPENCODE_PERMISSION_EFFECTS:
                    fail(
                        f"Agent {slug}.md: rule effect '{rule['effect']}' "
                        f"not in {sorted(OPENCODE_PERMISSION_EFFECTS)}"
                    )
                if not isinstance(rule["resource"], str) or not rule["resource"]:
                    fail(
                        f"Agent {slug}.md: rule resource must be a non-empty "
                        f"string: {rule!r}"
                    )

            # Round-trip equivalence with the translator
            try:
                expected = translate_opencode_permissions(
                    slug, source_mode.get("groups", []), data["permissions"]
                )
            except FileRegexNotImplemented as exc:
                fail(f"OpenCode translation: {exc}")
            canonical = sorted(
                (r["action"], r["resource"], r["effect"]) for r in permissions
            )
            expected_canonical = sorted(
                (r["action"], r["resource"], r["effect"]) for r in expected
            )
            if canonical != expected_canonical:
                fail(
                    f"Agent {slug}.md: emitted permissions diverge from the "
                    f"translation of modes.json.permissions['{slug}']:\n"
                    f"  emitted:  {canonical}\n"
                    f"  expected: {expected_canonical}"
                )

            # Semantic last-match-wins on the edit rules
            edit_rules = [r for r in permissions if r["action"] == "edit"]
            try:
                scoped_glob = _scoped_edit_glob(
                    source_mode.get("groups", []), FILEREGEX_TO_GLOB
                )
            except FileRegexNotImplemented as exc:
                fail(f"OpenCode translation: {exc}")
            edit_value = data["permissions"][slug]["edit"]
            if scoped_glob is not None and edit_value == "allow":
                if len(edit_rules) != 2:
                    fail(
                        f"Agent {slug}.md: edit='{edit_value}' with a scoped "
                        f"group expects exactly two edit rules (broad deny + "
                        f"scoped allow); got {edit_rules!r}"
                    )
                if edit_rules[0] != {
                    "action": "edit",
                    "resource": "*",
                    "effect": "deny",
                }:
                    fail(
                        f"Agent {slug}.md: first edit rule must be the broad "
                        f"'*' deny; got {edit_rules[0]!r}"
                    )
                if edit_rules[1] != {
                    "action": "edit",
                    "resource": scoped_glob,
                    "effect": "allow",
                }:
                    fail(
                        f"Agent {slug}.md: second edit rule must be the "
                        f"scoped '{scoped_glob}' allow; got {edit_rules[1]!r}"
                    )
            else:
                # No scoped group, or edit denied/gated: the scoped group is
                # dead at the opencode layer, so exactly one broad rule
                if len(edit_rules) != 1 or edit_rules[0]["resource"] != "*":
                    fail(
                        f"Agent {slug}.md: edit='{edit_value}' without a "
                        "live scoped group expects exactly one broad '*' "
                        f"edit rule; got {edit_rules!r}"
                    )

            # Stable action ordering (first occurrence per action)
            first_seen = list(dict.fromkeys(r["action"] for r in permissions))
            expected_order = [
                a
                for a in (
                    "edit",
                    "shell",
                    "read",
                    "glob",
                    "grep",
                    "skill",
                    "subagent",
                )
                if a in first_seen
            ]
            if first_seen != expected_order:
                fail(
                    f"Agent {slug}.md: rule order {first_seen} does not "
                    f"match the stable order {expected_order}"
                )

            ok(f"{agent_file.name}: {len(permissions)} rules, semantics OK")

    ok(f"All {len(agent_files)} opencode agents carry the expected permissions")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    data = validate_structure()
    round_trip(data)
    verify_opencode_agent_modes()
    verify_opencode_agent_models()
    verify_opencode_agent_permissions()
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
