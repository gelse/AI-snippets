"""Generate mode/skill artifacts for Zoo Code, Kilo Code, OpenCode, and Claude Code.

Usage:
    scripts/generate.py {zoo|kilo|opencode|claude} [--out output]
"""

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_modes():
    """Load modes.json from repo root."""
    with open(REPO_ROOT / "modes.json") as f:
        return json.load(f)


def load_skill_content(skill_file):
    """Load skill .md content using the file path from modes.json."""
    skill_path = REPO_ROOT / skill_file
    with open(skill_path) as f:
        return f.read()


def _find_frontmatter_end(content):
    """Find the closing '---' of YAML frontmatter.

    Returns the index of the closing delimiter, or exits with a clear
    message if the closing delimiter is missing.
    """
    try:
        return content.index("---", 3)
    except ValueError:
        print(
            "ERROR: Frontmatter starts with '---' but closing '---' not found.",
            file=sys.stderr,
        )
        sys.exit(1)


def ensure_skill_frontmatter(content, skill_name):
    """Ensure skill content has name and description frontmatter.

    Preserves existing frontmatter if present; adds missing fields.
    """
    if content.startswith("---\n"):
        end = _find_frontmatter_end(content)
        frontmatter = content[3:end].strip()
        body = content[end + 3:].removeprefix("\n")

        has_name = bool(re.search(r"^name:", frontmatter, re.MULTILINE))
        has_desc = bool(re.search(r"^description:", frontmatter, re.MULTILINE))

        additions = ""
        if not has_name:
            additions += f"\nname: {skill_name}"
        if not has_desc:
            additions += f"\ndescription: {skill_name}"

        if additions:
            frontmatter += additions
            return f"---\n{frontmatter}\n---\n{body}"
        return content
    else:
        fm = f"name: {skill_name}\ndescription: {skill_name}"
        return f"---\n{fm}\n---\n{content}"


def has_edit_group(groups):
    """Check if a mode's groups contain an edit group."""
    for g in groups:
        if g == "edit":
            return True
        if isinstance(g, list) and len(g) > 0 and g[0] == "edit":
            return True
    return False


def extract_skill_description(content):
    """Extract description from skill frontmatter."""
    if content.startswith("---\n"):
        end = _find_frontmatter_end(content)
        fm = content[3:end]
        m = re.search(r"^description:\s*(.+)$", fm, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return ""


def extract_body_after_frontmatter(content):
    """Extract body content after YAML frontmatter."""
    if content.startswith("---\n"):
        end = _find_frontmatter_end(content)
        body = content[end + 3:].removeprefix("\n")
        return body
    return content


def mode_to_dict(mode):
    """Convert a mode dict for YAML output, excluding deprecated key."""
    return {k: v for k, v in mode.items() if k != "deprecated"}


# ---------------------------------------------------------------------------
# Zoo Code emitter
# ---------------------------------------------------------------------------

def emit_zoo(data, out_dir):
    """Emit Zoo Code artifacts."""
    import yaml

    zoo_dir = out_dir / "zoo"
    shutil.rmtree(zoo_dir, ignore_errors=True)
    zoo_dir.mkdir(parents=True, exist_ok=True)

    custom_modes = [mode_to_dict(m) for m in data["customModes"]]
    roomodes = {"customModes": custom_modes}

    with open(zoo_dir / ".roomodes", "w") as f:
        yaml.dump(roomodes, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    skills_dir = zoo_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for skill in data["skills"]:
        content = load_skill_content(skill["file"])
        content = ensure_skill_frontmatter(content, skill["name"])
        with open(skills_dir / f"{skill['name']}.md", "w") as f:
            f.write(content)

    print(f"  zoo: {zoo_dir / '.roomodes'} + {len(data['skills'])} skills")


# ---------------------------------------------------------------------------
# Kilo Code emitter
# ---------------------------------------------------------------------------

def emit_kilo(data, out_dir):
    """Emit Kilo Code artifacts."""
    import yaml

    kilo_dir = out_dir / "kilo"
    shutil.rmtree(kilo_dir, ignore_errors=True)
    kilo_dir.mkdir(parents=True, exist_ok=True)

    custom_modes = [mode_to_dict(m) for m in data["customModes"]]
    kilocodemodes = {"customModes": custom_modes}

    with open(kilo_dir / ".kilocodemodes", "w") as f:
        yaml.dump(kilocodemodes, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    skills_dir = kilo_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for skill in data["skills"]:
        content = load_skill_content(skill["file"])
        content = ensure_skill_frontmatter(content, skill["name"])
        with open(skills_dir / f"{skill['name']}.md", "w") as f:
            f.write(content)

    print(f"  kilo: {kilo_dir / '.kilocodemodes'} + {len(data['skills'])} skills")


# ---------------------------------------------------------------------------
# OpenCode emitter
# ---------------------------------------------------------------------------

def emit_opencode(data, out_dir):
    """Emit OpenCode artifacts."""
    import yaml

    oc_dir = out_dir / "opencode"
    shutil.rmtree(oc_dir, ignore_errors=True)
    agents_dir = oc_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for mode in data["customModes"]:
        if mode.get("deprecated"):
            continue

        slug = mode["slug"]
        desc = mode["description"]
        when = mode["whenToUse"]
        role = mode["roleDefinition"]
        instructions = mode.get("customInstructions", "")
        groups = mode.get("groups", [])

        frontmatter = {
            "description": f"{desc} (Use when: {when})",
            "mode": "subagent",
        }

        if not has_edit_group(groups):
            frontmatter["permission"] = {"edit": "deny"}

        body = f"{role}\n\n{instructions}" if instructions else role

        fm_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
        content = f"---\n{fm_str}---\n{body}\n"

        with open(agents_dir / f"{slug}.md", "w") as f:
            f.write(content)
        count += 1

    skill_dir = oc_dir / "skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    for skill in data["skills"]:
        raw = load_skill_content(skill["file"])
        skill_desc = extract_skill_description(raw)
        body = extract_body_after_frontmatter(raw)

        frontmatter = {"name": skill["name"]}
        if skill_desc:
            frontmatter["description"] = skill_desc

        fm_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
        with open(skill_dir / f"{skill['name']}.md", "w") as f:
            f.write(f"---\n{fm_str}---\n{body}\n")

    print(f"  opencode: {count} agents + {len(data['skills'])} skills in {oc_dir}")


# ---------------------------------------------------------------------------
# Claude Code emitter
# ---------------------------------------------------------------------------

def emit_claude(data, out_dir):
    """Emit Claude Code artifacts."""
    import yaml

    claude_dir = out_dir / "claude"
    shutil.rmtree(claude_dir, ignore_errors=True)
    agents_dir = claude_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for mode in data["customModes"]:
        if mode.get("deprecated"):
            continue

        slug = mode["slug"]
        desc = mode["description"]
        when = mode["whenToUse"]
        role = mode["roleDefinition"]
        instructions = mode.get("customInstructions", "")

        frontmatter = {
            "name": slug,
            "description": f"{desc} (Use when: {when})",
        }

        body = f"{role}\n\n{instructions}" if instructions else role

        fm_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
        content = f"---\n{fm_str}---\n{body}\n"

        with open(agents_dir / f"{slug}.md", "w") as f:
            f.write(content)
        count += 1

    for skill in data["skills"]:
        skill_dir = claude_dir / "skills" / skill["name"]
        skill_dir.mkdir(parents=True, exist_ok=True)

        raw = load_skill_content(skill["file"])
        skill_desc = extract_skill_description(raw)
        body = extract_body_after_frontmatter(raw)

        frontmatter = {"name": skill["name"]}
        if skill_desc:
            frontmatter["description"] = skill_desc

        fm_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
        with open(skill_dir / "SKILL.md", "w") as f:
            f.write(f"---\n{fm_str}---\n{body}\n")

    print(f"  claude: {count} agents + {len(data['skills'])} skills in {claude_dir}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

EMITTERS = {
    "zoo": emit_zoo,
    "kilo": emit_kilo,
    "opencode": emit_opencode,
    "claude": emit_claude,
}


def main():
    parser = argparse.ArgumentParser(
        description="Generate mode/skill artifacts for AI coding tools"
    )
    parser.add_argument(
        "tool",
        choices=list(EMITTERS.keys()),
        help="Target tool to generate artifacts for",
    )
    parser.add_argument(
        "--out",
        default="output",
        help="Output directory relative to repo root (default: output)",
    )
    args = parser.parse_args()

    data = load_modes()
    out_dir = REPO_ROOT / args.out

    print(f"Generating {args.tool} artifacts...")
    EMITTERS[args.tool](data, out_dir)
    print("Done.")


if __name__ == "__main__":
    main()
