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

# Required keys per non-deprecated mode's permissions entry, in the
# canonical row order. This is the repo's own vocabulary (modes.json) and
# is deliberately NOT renamed to opencode's action names; the emitter
# translates at emit time ('shell' -> 'bash', 'task' -> 'task').
# EXPECTED_PERMS_KEY_ORDER asserts the modes.json row order itself: every
# permissions row must key its entries exactly in this order.
EXPECTED_PERMS_KEY_ORDER = (
    "edit",
    "shell",
    "read",
    "glob",
    "grep",
    "skill",
    "task",
    "lsp",
    "question",
    "external_directory",
    "doom_loop",
)
REQUIRED_PERMISSION_KEYS = frozenset(EXPECTED_PERMS_KEY_ORDER)
VALID_PERMISSION_EFFECTS = {"allow", "ask", "deny"}

# The modes.json shell value 'auto' (repo vocabulary, expanded at emit time
# by generate.expand_auto_shell into a safe-command pattern map). Valid as a
# scalar for the 'shell' key only: it is never an emitted effect and never
# valid on another action — the structural check below enforces that.
SHELL_AUTO = "auto"

# Ground-truth oracle: the permission names opencode 1.18.35 actually
# compiles into permission rulesets (V1 AgentConfig `permission` map; the
# field is a map of name -> effect | {pattern -> effect}, verified against
# the binary via `opencode debug agent <name>`). Deliberately NOT imported
# from generate.py: if the emitter invents or misnames actions (e.g. the
# repo-vocabulary names 'shell'/'subagent'), this set is the independent
# regression tripwire that keeps verify green only for runtime-true names.
OPENCODE_V1_PERMISSION_NAMES = {
    "read",
    "edit",
    "glob",
    "grep",
    "list",
    "bash",
    "task",
    "external_directory",
    "todowrite",
    "question",
    "webfetch",
    "websearch",
    "lsp",
    "doom_loop",
    "skill",
}

# modes.json key -> the opencode V1 permission name the emitter must use.
# 'shell' and 'task' are repo vocabulary; only their EMITTED names change.
# The 4 new keys are identity (same name in modes.json and opencode
# frontmatter).
MODES_KEY_TO_V1_NAME = {
    "edit": "edit",
    "shell": "bash",
    "read": "read",
    "glob": "glob",
    "grep": "grep",
    "skill": "skill",
    "task": "task",
    "lsp": "lsp",
    "question": "question",
    "external_directory": "external_directory",
    "doom_loop": "doom_loop",
}

# Required keys of harnesses.json (per-harness prose blocks injected into
# emitted agent bodies; zoo/kilo stay present-and-empty)
REQUIRED_HARNESS_KEYS = {"zoo", "kilo", "opencode"}
HARNESS_INNER_KEY = "subtaskInstructions"


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
    # skill, task, lsp, question, external_directory, doom_loop}, keyed in
    # the canonical row order; per-mode entries are validated in the mode
    # loop below. Values are an effect string or a non-empty pattern map of
    # such effects (plan.shell / review-code.shell are pattern maps; lsp /
    # external_directory may be); question / doom_loop are scalar-only
    # (upstream actionOnly); shell additionally accepts the scalar 'auto',
    # which generate.expand_auto_shell expands at emit time.
    permissions = data["permissions"]
    if not isinstance(permissions, dict):
        fail(
            f"Top-level 'permissions' must be a dict; got {type(permissions).__name__}"
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
                f"Mode '{slug}' customInstructions must be '{expected_ci}', got '{ci}'"
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
                    fail(
                        f"Mode '{slug}' nested group second element must be a dict: {g}"
                    )
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
            if list(perms.keys()) != list(EXPECTED_PERMS_KEY_ORDER):
                fail(
                    f"Mode '{slug}' permissions keys must be exactly "
                    f"{list(EXPECTED_PERMS_KEY_ORDER)} in this order; got "
                    f"{list(perms.keys())}"
                )
            for key, effect in perms.items():
                if isinstance(effect, str) and effect in VALID_PERMISSION_EFFECTS:
                    continue
                if key == "shell" and effect == SHELL_AUTO:
                    continue
                if (
                    isinstance(effect, dict)
                    and effect
                    and all(isinstance(pattern, str) and pattern for pattern in effect)
                    and all(
                        isinstance(value, str) and value in VALID_PERMISSION_EFFECTS
                        for value in effect.values()
                    )
                ):
                    if key in {"question", "doom_loop"}:
                        fail(
                            f"Mode '{slug}' permissions '{key}' must be a "
                            f"plain scalar in {sorted(VALID_PERMISSION_EFFECTS)}; "
                            f"opencode's '{key}' action is actionOnly "
                            f"(scalar effects only). Got {effect!r}"
                        )
                    continue
                fail(
                    f"Mode '{slug}' permissions '{key}' must be a string in "
                    f"{sorted(VALID_PERMISSION_EFFECTS)}"
                    + (" or 'auto'" if key == "shell" else "")
                    + " or a non-empty pattern map of non-empty string keys "
                    f"to those effects; got {effect!r}"
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
# (b) harnesses.json schema
# ---------------------------------------------------------------------------


def verify_harnesses_schema():
    """Load harnesses.json and assert its schema: exact top-level key set,
    exactly one inner key per harness, list-of-string values, empty lists
    for zoo/kilo, and a non-empty list for opencode."""
    print("[b] harnesses.json schema")

    json_path = REPO_ROOT / "harnesses.json"
    if not json_path.exists():
        fail("harnesses.json not found")

    try:
        with open(json_path) as f:
            harnesses = json.load(f)
    except json.JSONDecodeError as exc:
        fail(f"harnesses.json: invalid JSON: {exc}")

    ok("Valid JSON")

    if set(harnesses.keys()) != REQUIRED_HARNESS_KEYS:
        fail(
            "harnesses.json top-level keys must be exactly "
            f"{sorted(REQUIRED_HARNESS_KEYS)}; got {sorted(harnesses.keys())}"
        )
    ok(f"Top-level keys: {sorted(harnesses.keys())}")

    for key in sorted(REQUIRED_HARNESS_KEYS):
        entry = harnesses[key]
        if not isinstance(entry, dict):
            fail(f"harnesses.json '{key}' must be a dict; got {type(entry).__name__}")
        if set(entry.keys()) != {HARNESS_INNER_KEY}:
            fail(
                f"harnesses.json '{key}' keys must be exactly "
                f"['{HARNESS_INNER_KEY}']; got {sorted(entry.keys())}"
            )
        instructions = entry[HARNESS_INNER_KEY]
        if not isinstance(instructions, list):
            fail(
                f"harnesses.json '{key}.{HARNESS_INNER_KEY}' must be a "
                f"list; got {type(instructions).__name__}"
            )
        for i, instruction in enumerate(instructions):
            if not isinstance(instruction, str):
                fail(
                    f"harnesses.json '{key}.{HARNESS_INNER_KEY}'[{i}] must "
                    f"be a string; got {type(instruction).__name__}"
                )
        if key in {"zoo", "kilo"} and instructions:
            fail(
                f"harnesses.json '{key}' must carry an empty "
                f"'{HARNESS_INNER_KEY}' list; got {len(instructions)} "
                "instruction(s)"
            )
        if key == "opencode" and not instructions:
            fail(f"harnesses.json 'opencode' '{HARNESS_INNER_KEY}' must be non-empty")

    ok("Per-harness schema valid (zoo/kilo empty, opencode non-empty)")


# ---------------------------------------------------------------------------
# (c) Round-trip: emit to zoo, load back, deep-compare
# ---------------------------------------------------------------------------


def round_trip(data):
    """Emit to a temp dir via zoo emitter, yaml.safe_load the result,
    and deep-compare customModes to the JSON source (ignoring 'deprecated')."""
    print("[c] Round-trip verification")

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
# (d) OpenCode agents: mode must match the mode's instantiation value
# ---------------------------------------------------------------------------


def verify_opencode_agent_modes():
    """Emit opencode agents to a temp dir and assert frontmatter mode matches
    the mode's ``instantiation`` value (defaulting to ``all`` when absent).

    The opencode emitter writes ``mode: <instantiation>`` so each agent's
    visibility is driven by modes.json: ``primary`` agents appear in the
    primary TUI picker, ``subagent`` agents are only invocable as subagents,
    and ``all`` agents are available in both places.
    """
    print("[d] OpenCode agent mode verification")

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
# (e) OpenCode agents: model must match models/mapping.yaml, in field position
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
    and ``permission`` (the V1 rules map) appears after ``model`` when
    present.
    """
    print("[e] OpenCode agent model verification")

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

            # Field position: description < mode < model < permission
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
            if "permission" in keys and keys.index("permission") < model_idx:
                fail(
                    f"Agent {agent_file.name}: 'permission' must come after "
                    f"'model'; key order is {keys}"
                )

            ok(f"{agent_file.name}: model={model_value}")

    ok(f"All {len(agent_files)} opencode agents match mapping.yaml (model + position)")


# ---------------------------------------------------------------------------
# (f) OpenCode agents: permission map content and rule semantics
# ---------------------------------------------------------------------------


def _scoped_edit_glob(groups, fileregex_to_glob):
    """Return the mapped glob for the mode's first fileRegex edit group.

    Mirrors the emitter's nested-``["edit", {"fileRegex": "..."}]`` shape
    check so the semantic comparison in check (f) reads the mode's groups
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


def _expand_auto_shell_oracle(instantiation, safe_commands):
    """Independent expansion of the modes.json shell value ``'auto'``.

    Mirrors the emitter's ``expand_auto_shell`` without calling it, so an
    emitter bug in the expansion is caught rather than round-tripped. The
    command list is passed in (``SAFE_SHELL_COMMANDS`` from generate.py,
    like ``FILEREGEX_TO_GLOB``) — this oracle checks the expansion
    semantics, not the list contents: catch-all ``'*'`` first ('ask' for
    ``instantiation == 'primary'`` modes — they converse with the user —
    'deny' for every other instantiation, which run headless), then a bare
    ``cmd`` and a ``cmd *`` allow for every safe command. Entry order is
    last-match-wins policy.
    """
    catch_all = "ask" if instantiation == "primary" else "deny"
    expected = {"*": catch_all}
    for cmd in safe_commands:
        expected[cmd] = "allow"
        expected[f"{cmd} *"] = "allow"
    return expected


def verify_opencode_agent_permissions():
    """Emit opencode agents to a temp dir and assert each frontmatter's
    ``permission`` map matches the mode's entry in modes.json.permissions.

    This is the regression check for the subagent-spawn defect: opencode
    1.18.35 compiles only the V1 ``permission`` map (name -> effect |
    {pattern: effect}) into permission rulesets. A v2 ``permissions`` list
    of ``{action, resource, effect}`` rules is swept into ``options`` and
    never enforced, so a ruleset built from it contains no ``task`` rule
    and the subagent-spawn gate injects ``{permission:"task", pattern:"*",
    action:"deny"}`` which strips the ``task`` tool from every spawned
    subagent.

    Per agent: the frontmatter must carry the V1 ``permission`` map and no
    inert ``permissions`` list; names must be opencode's V1 permission
    names (modes.json 'shell'/'task' must emit as 'bash'/'task', never as
    'shell'/'subagent'); values must be valid effects or pattern->effect
    maps; the map must equal both an independent modes.json oracle and the
    emitter's own translation; and scoped edit entries must be ordered
    broad-deny first, scoped-allow last (last-match-wins). A map-valued
    ``bash`` entry must additionally match the modes.json oracle
    order-sensitively and carry exactly one catch-all ``*`` pattern
    (emitter-fidelity guard); a scalar ``bash`` entry must stay scalar.
    A shell ``'auto'`` row is expanded by the oracle too (catch-all gate
    first — 'ask' for ``instantiation == 'primary'`` modes, 'deny'
    otherwise — then bare and ``cmd *`` allows per SAFE command), so the
    emitted expansion must match the independently computed one.
    """
    print("[f] OpenCode agent permissions verification")

    json_path = REPO_ROOT / "modes.json"
    with open(json_path) as f:
        data = json.load(f)

    modes_by_slug = {m["slug"]: m for m in data["customModes"]}

    with tempfile.TemporaryDirectory() as tmpdir:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from generate import (
            FILEREGEX_TO_GLOB,
            OPENCODE_PERMISSION_ACTIONS,
            SAFE_SHELL_COMMANDS,
            SHELL_AUTO,
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

            permissions = fm.get("permission")
            if "permissions" in fm:
                fail(
                    f"Agent {slug}.md: found the inert v2 'permissions' "
                    "list; opencode 1.18.35 sweeps it into 'options' and "
                    "never enforces it (no ruleset entry is compiled from "
                    "it, so the spawn gate injects a 'task': deny and "
                    "strips the task tool from subagents). Emit the V1 "
                    "'permission' map instead."
                )
            if not isinstance(permissions, dict) or not permissions:
                fail(
                    f"Agent {slug}.md: 'permission' must be a non-empty "
                    f"map of name -> effect | {{pattern: effect}}; got "
                    f"{permissions!r}"
                )

            # Name vocabulary: runtime-true V1 names only — never the
            # repo's 'shell'/'subagent' vocabulary, which the runtime does
            # not recognize (this is the regression tripwire for the
            # permission-action name mismatch).
            for name in permissions:
                if name in {"shell", "subagent"}:
                    fail(
                        f"Agent {slug}.md: permission name '{name}' is "
                        "modes.json vocabulary, not an opencode action; "
                        "'shell' must emit as 'bash' and 'task' as 'task'"
                    )
                if name not in OPENCODE_V1_PERMISSION_NAMES:
                    fail(
                        f"Agent {slug}.md: permission name '{name}' not in "
                        f"opencode's V1 permission names "
                        f"{sorted(OPENCODE_V1_PERMISSION_NAMES)}"
                    )

            # Value shape: effect string, or non-empty pattern -> effect
            for name, entry in permissions.items():
                if isinstance(entry, str):
                    if entry not in VALID_PERMISSION_EFFECTS:
                        fail(
                            f"Agent {slug}.md: permission '{name}' effect "
                            f"must be in {sorted(VALID_PERMISSION_EFFECTS)}; "
                            f"got '{entry}'"
                        )
                    continue
                if not isinstance(entry, dict) or not entry:
                    fail(
                        f"Agent {slug}.md: permission '{name}' must be an "
                        f"effect or a non-empty pattern map; got {entry!r}"
                    )
                for pattern, effect in entry.items():
                    if not isinstance(pattern, str) or not pattern:
                        fail(
                            f"Agent {slug}.md: permission '{name}' has a "
                            f"non-string pattern: {pattern!r}"
                        )
                    if effect not in VALID_PERMISSION_EFFECTS:
                        fail(
                            f"Agent {slug}.md: permission '{name}' pattern "
                            f"'{pattern}' effect must be in "
                            f"{sorted(VALID_PERMISSION_EFFECTS)}; got "
                            f"'{effect}'"
                        )

            # Independent oracle straight from modes.json: every matrix key
            # must appear under its translated opencode name with the same
            # effect (scoped edit excepted), in the stable emit order. A
            # shell 'auto' row expands here too — the oracle never trusts the
            # emitter's expansion of it.
            perms_row = data["permissions"][slug]
            try:
                scoped_glob = _scoped_edit_glob(
                    source_mode.get("groups", []), FILEREGEX_TO_GLOB
                )
            except FileRegexNotImplemented as exc:
                fail(f"OpenCode translation: {exc}")
            edit_value = perms_row["edit"]
            instantiation = source_mode.get("instantiation", "all")

            expected_map = {}
            for key in EXPECTED_PERMS_KEY_ORDER:
                name = MODES_KEY_TO_V1_NAME[key]
                if key == "edit" and edit_value == "allow" and scoped_glob:
                    expected_map[name] = {"*": "deny", scoped_glob: "allow"}
                elif key == "shell" and perms_row[key] == SHELL_AUTO:
                    expected_map[name] = _expand_auto_shell_oracle(
                        instantiation, SAFE_SHELL_COMMANDS
                    )
                else:
                    expected_map[name] = perms_row[key]

            if list(permissions.keys()) != list(expected_map.keys()):
                fail(
                    f"Agent {slug}.md: permission names/order "
                    f"{list(permissions.keys())} != expected "
                    f"{list(expected_map.keys())} (modes.json keys mapped "
                    f"through {MODES_KEY_TO_V1_NAME})"
                )

            # bash-specific: scalar rows keep the plain effect; map-valued
            # rows are compared order-sensitively (dict == is order-insensitive,
            # so a reordered map would slip past the deep equality below) and
            # must carry exactly one catch-all '*' pattern. Entry order is
            # policy set in modes.json; this guards emitter fidelity only.
            expected_bash = expected_map["bash"]
            emitted_bash = permissions["bash"]
            if isinstance(expected_bash, str):
                # Scalar row: the dict checks must not run (a str has no
                # .items() and would count zero '*' keys).
                if not isinstance(emitted_bash, str):
                    fail(
                        f"Agent {slug}.md: permission 'bash' must be the "
                        f"string {expected_bash!r}; got {emitted_bash!r}"
                    )
            elif not isinstance(emitted_bash, dict):
                fail(
                    f"Agent {slug}.md: permission 'bash' must be a pattern "
                    f"map matching the modes.json entry for '{slug}'; got "
                    f"{emitted_bash!r}"
                )
            elif list(emitted_bash.items()) != list(expected_bash.items()):
                fail(
                    f"Agent {slug}.md: emitted 'bash' pattern map diverges "
                    f"from the modes.json oracle for '{slug}' (entries are "
                    "applied in order and the runtime keeps the last match, "
                    "so entry order is policy):\n"
                    f"  emitted:  {list(emitted_bash.items())!r}\n"
                    f"  expected: {list(expected_bash.items())!r}"
                )
            elif list(emitted_bash).count("*") != 1:
                fail(
                    f"Agent {slug}.md: 'bash' pattern map for '{slug}' must "
                    f"have exactly one catch-all '*' key; got "
                    f"{list(emitted_bash).count('*')}"
                )

            if permissions != expected_map:
                fail(
                    f"Agent {slug}.md: emitted permission map diverges from "
                    f"the modes.json oracle for '{slug}':\n"
                    f"  emitted:  {permissions!r}\n"
                    f"  expected: {expected_map!r}"
                )

            # Semantic last-match-wins on the scoped edit entry: the
            # pattern map is applied in order and the runtime keeps the
            # last matching rule, so the broad '*' deny must come first and
            # the scoped allow last.
            if edit_value == "allow" and scoped_glob:
                edit_entry = permissions.get("edit")
                if not isinstance(edit_entry, dict):
                    fail(
                        f"Agent {slug}.md: edit='{edit_value}' with a "
                        f"scoped group expects a pattern map; got "
                        f"{edit_entry!r}"
                    )
                if list(edit_entry.keys()) != ["*", scoped_glob]:
                    fail(
                        f"Agent {slug}.md: scoped edit patterns must be "
                        f"ordered ['*', {scoped_glob!r}] (broad deny first, "
                        f"scoped allow last, last-match-wins); got "
                        f"{list(edit_entry.keys())!r}"
                    )
            elif not isinstance(permissions.get("edit"), str):
                # No scoped group, or edit denied/gated: the scoped group
                # is dead at the opencode layer, so one plain effect
                fail(
                    f"Agent {slug}.md: edit='{edit_value}' without a live "
                    f"scoped group expects a plain effect; got "
                    f"{permissions.get('edit')!r}"
                )

            # Round-trip equivalence with the translator
            try:
                translated = translate_opencode_permissions(
                    slug,
                    source_mode.get("groups", []),
                    data["permissions"],
                    instantiation=instantiation,
                )
            except FileRegexNotImplemented as exc:
                fail(f"OpenCode translation: {exc}")
            if translated != permissions:
                fail(
                    f"Agent {slug}.md: emitted permission map diverges from "
                    f"the translation of modes.json.permissions['{slug}']:\n"
                    f"  emitted:    {permissions!r}\n"
                    f"  translated: {translated!r}"
                )

            ok(
                f"{agent_file.name}: permission map "
                f"({len(permissions)} entries), names+semantics OK"
            )

        # Hygiene: the emitter's own vocabulary tuple must never drift back
        # to repo names ('shell', 'subagent') the runtime does not accept.
        if not set(OPENCODE_PERMISSION_ACTIONS).issubset(OPENCODE_V1_PERMISSION_NAMES):
            fail(
                "generate.OPENCODE_PERMISSION_ACTIONS contains names the "
                "opencode runtime does not recognize: "
                f"{sorted(set(OPENCODE_PERMISSION_ACTIONS) - OPENCODE_V1_PERMISSION_NAMES)}"
            )

        # Synthetic 'auto' rows: no live mode uses shell 'auto' yet, so the
        # expansion is exercised here directly against the translator — the
        # catch-all gate must be 'ask' for a 'primary' instantiation and
        # 'deny' for any other ('all', 'subagent'), and the full expansion
        # must equal the independent oracle. Also: 'auto' on any non-shell
        # key must be rejected at translate time.
        for inst, gate in (("primary", "ask"), ("all", "deny"), ("subagent", "deny")):
            auto_row = dict.fromkeys(EXPECTED_PERMS_KEY_ORDER, "deny")
            auto_row["shell"] = SHELL_AUTO
            translated = translate_opencode_permissions(
                "synthetic", [], {"synthetic": auto_row}, instantiation=inst
            )
            expected_auto = _expand_auto_shell_oracle(inst, SAFE_SHELL_COMMANDS)
            if translated["bash"] != expected_auto:
                fail(
                    f"shell 'auto' (instantiation {inst!r}): translation "
                    f"diverges from the oracle:\n"
                    f"  translated: {list(translated['bash'].items())!r}\n"
                    f"  expected:   {list(expected_auto.items())!r}"
                )
            if translated["bash"]["*"] != gate:
                fail(
                    f"shell 'auto' (instantiation {inst!r}): catch-all gate "
                    f"must be {gate!r}; got {translated['bash']['*']!r}"
                )
            bad_row = dict(auto_row)
            bad_row["question"] = SHELL_AUTO
            try:
                translate_opencode_permissions(
                    "synthetic", [], {"synthetic": bad_row}, instantiation=inst
                )
            except ValueError:
                pass
            else:
                fail(
                    "permissions 'question': 'auto' must be rejected — the "
                    "'auto' expansion is valid for 'shell' only"
                )
        ok(
            "shell 'auto' expansion: catch-all gate per instantiation + "
            "safe-command allows match the oracle; non-shell 'auto' rejected"
        )

    ok(f"All {len(agent_files)} opencode agents carry a runtime-true V1 permission map")


# ---------------------------------------------------------------------------
# (g) OpenCode agents: subtask block presence, position, and provenance
# ---------------------------------------------------------------------------


def verify_opencode_subtask_block():
    """Emit all three harnesses to a temp dir and verify the subtask block.

    Per opencode agent: the body must carry ``## Starting Subtasks`` exactly
    once, positioned directly between the role prose and the first stub
    heading, with content matching ``harnesses.json['opencode']
    ['subtaskInstructions']`` (round-trip oracle via
    ``generate.load_harnesses()``). Zoo and kilo emitted files must not
    contain the heading at all — their harnesses.json lists are empty, so
    any occurrence would break their byte-identity guarantee.
    """
    print("[g] OpenCode subtask-block verification")

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from generate import (
        emit_kilo,
        emit_opencode,
        emit_zoo,
        load_harnesses,
        resolve_custom_instructions,
    )

    subtask_instructions = (
        load_harnesses().get("opencode", {}).get("subtaskInstructions", [])
    )
    joined = "\n\n".join(subtask_instructions)

    json_path = REPO_ROOT / "modes.json"
    with open(json_path) as f:
        data = json.load(f)

    resolved = json.loads(json.dumps(data))
    resolved["customModes"] = resolve_custom_instructions(resolved["customModes"])

    with tempfile.TemporaryDirectory() as tmpdir:
        emit_zoo(resolved, Path(tmpdir))
        emit_kilo(resolved, Path(tmpdir))
        emit_opencode(resolved, Path(tmpdir))

        # Byte-identity guard: zoo/kilo carry empty subtaskInstructions
        for tool in ("zoo", "kilo"):
            tool_dir = Path(tmpdir) / tool
            for path in sorted(tool_dir.rglob("*")):
                if not path.is_file():
                    continue
                if "## Starting Subtasks" in path.read_text():
                    fail(
                        f"{tool} output {path.name} must not contain "
                        "'## Starting Subtasks'"
                    )
        ok("zoo/kilo outputs carry no '## Starting Subtasks' heading")

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
            body = content[end + 3 :].removeprefix("\n")

            occurrences = body.count("## Starting Subtasks")
            if occurrences != 1:
                fail(
                    f"Agent {agent_file.name}: '## Starting Subtasks' must "
                    f"appear exactly once; got {occurrences}"
                )

            expected_block = f"## Starting Subtasks\n\n{joined}"
            if expected_block not in body:
                fail(
                    f"Agent {agent_file.name}: subtask block does not match "
                    "harnesses.json opencode subtaskInstructions; expected "
                    f"{expected_block!r}"
                )

            # Position: split on '\n## ' — section 0 is the role prose and
            # the subtask section must follow it directly, before any stub
            # heading (## Skill, ## Tools, ...).
            sections = body.split("\n## ")
            if len(sections) < 2 or not sections[1].startswith("Starting Subtasks"):
                fail(
                    f"Agent {agent_file.name}: 'Starting Subtasks' must be "
                    "the first heading after the role; section headings are "
                    f"{[s.splitlines()[0] for s in sections]}"
                )

            ok(f"{agent_file.name}: subtask block present, positioned, matches config")

    ok(
        f"All {len(agent_files)} opencode agents carry the subtask block "
        "from harnesses.json"
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    data = validate_structure()
    verify_harnesses_schema()
    round_trip(data)
    verify_opencode_agent_modes()
    verify_opencode_agent_models()
    verify_opencode_agent_permissions()
    verify_opencode_subtask_block()
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
