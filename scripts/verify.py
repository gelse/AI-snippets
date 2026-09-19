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
}

REQUIRED_TOP_KEYS = {"customModes", "skills"}


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
    groups shape, and skill file existence."""
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

    ok("All modes have required keys and valid groups shape")

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
# main
# ---------------------------------------------------------------------------

def main():
    data = validate_structure()
    round_trip(data)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
