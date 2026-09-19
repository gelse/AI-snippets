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

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
_SAFE_FILENAME_RE = re.compile(r"^[a-z0-9._-]+$")


# ---------------------------------------------------------------------------
# YAML helpers – force literal block scalars for multiline strings
# ---------------------------------------------------------------------------


class _LiteralDumper(yaml.SafeDumper):
    """YAML dumper that uses literal block scalars for multiline strings.

    PyYAML's ``analyze_scalar`` sets ``allow_block = False`` when the string
    contains non-ASCII characters (treated as "special").  This causes
    ``choose_scalar_style`` to silently fall back to double-quoted output
    even when the representer explicitly requested literal/folded style.
    We override ``choose_scalar_style`` to grant the request unconditionally
    for ``|`` and ``>`` styles.
    """

    def choose_scalar_style(self):
        if (self.event.style in ("|", ">")
                and not self.flow_level
                and not self.simple_key_context):
            return self.event.style
        return yaml.emitter.Emitter.choose_scalar_style(self)


def _str_representer(dumper, data):
    """Use literal block scalar (|-) for multiline strings, plain for single-line."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_LiteralDumper.add_representer(str, _str_representer)


def _yaml_dump(obj):
    """Dump obj to YAML with literal block scalars for multiline strings."""
    return yaml.dump(obj, Dumper=_LiteralDumper, default_flow_style=False,
                     allow_unicode=True, sort_keys=False, width=4096)


def load_modes():
    """Load modes.json from repo root."""
    with open(REPO_ROOT / "modes.json") as f:
        return json.load(f)


def load_skill_content(skill_file):
    """Load skill .md content using the file path from modes.json."""
    skill_path = REPO_ROOT / skill_file
    with open(skill_path) as f:
        return f.read()


def load_agent_content(agent_file):
    """Load agent .md content from a repo-relative path (e.g. agents/code.md)."""
    return (REPO_ROOT / agent_file).read_text()


def resolve_custom_instructions(modes):
    """Replace agents/*.md paths in modes with their file contents."""
    for mode in modes:
        ci = mode["customInstructions"]
        if isinstance(ci, str) and ci.startswith("agents/"):
            mode["customInstructions"] = load_agent_content(ci)
    return modes


def copy_skill_extra_files(skill, dest_dir):
    """Copy companion files (e.g. *.py) for directory-form skills into dest_dir.

    For skills declared as skills/<name>/SKILL.md, any other files in the
    skills/<name>/ directory (scripts, configs) are copied beside the emitted
    skill so the installed skill actually ships them.  Flat-form skills have no
    extras and are unaffected (output stays byte-identical).

    Skips dotfiles and filenames not matching ``^[a-z0-9._-]+$``.
    """
    name = skill["name"]
    src_dir = REPO_ROOT / "skills" / name
    if skill["file"] != f"skills/{name}/SKILL.md":
        return
    if not src_dir.is_dir():
        return
    for extra in sorted(src_dir.iterdir()):
        if extra.name == "SKILL.md" or not extra.is_file():
            continue
        # Skip dotfiles and unsafe filenames
        if extra.name.startswith(".") or not _SAFE_FILENAME_RE.match(extra.name):
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(extra, dest_dir / extra.name)


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
    zoo_dir = out_dir / "zoo"
    shutil.rmtree(zoo_dir, ignore_errors=True)
    zoo_dir.mkdir(parents=True, exist_ok=True)

    custom_modes = [mode_to_dict(m) for m in data["customModes"]]
    roomodes = {"customModes": custom_modes}

    with open(zoo_dir / ".roomodes", "w") as f:
        f.write(_yaml_dump(roomodes))

    skills_dir = zoo_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for skill in data["skills"]:
        content = load_skill_content(skill["file"])
        content = ensure_skill_frontmatter(content, skill["name"])
        with open(skills_dir / f"{skill['name']}.md", "w") as f:
            f.write(content)
        # Companion files for directory-form skills go in skills/<name>/
        copy_skill_extra_files(skill, skills_dir / skill["name"])

    print(f"  zoo: {zoo_dir / '.roomodes'} + {len(data['skills'])} skills")


# ---------------------------------------------------------------------------
# Kilo Code emitter
# ---------------------------------------------------------------------------

def emit_kilo(data, out_dir):
    """Emit Kilo Code artifacts."""
    kilo_dir = out_dir / "kilo"
    shutil.rmtree(kilo_dir, ignore_errors=True)
    kilo_dir.mkdir(parents=True, exist_ok=True)

    custom_modes = [mode_to_dict(m) for m in data["customModes"]]
    kilocodemodes = {"customModes": custom_modes}

    with open(kilo_dir / ".kilocodemodes", "w") as f:
        f.write(_yaml_dump(kilocodemodes))

    skills_dir = kilo_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    for skill in data["skills"]:
        content = load_skill_content(skill["file"])
        content = ensure_skill_frontmatter(content, skill["name"])
        with open(skills_dir / f"{skill['name']}.md", "w") as f:
            f.write(content)
        # Companion files for directory-form skills go in skills/<name>/
        copy_skill_extra_files(skill, skills_dir / skill["name"])

    print(f"  kilo: {kilo_dir / '.kilocodemodes'} + {len(data['skills'])} skills")


# ---------------------------------------------------------------------------
# OpenCode emitter
# ---------------------------------------------------------------------------

def emit_opencode(data, out_dir):
    """Emit OpenCode artifacts."""
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

        fm_str = _yaml_dump(frontmatter)
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

        fm_str = _yaml_dump(frontmatter)
        with open(skill_dir / f"{skill['name']}.md", "w") as f:
            f.write(f"---\n{fm_str}---\n{body}\n")
        # Companion files for directory-form skills go in skill/<name>/
        copy_skill_extra_files(skill, skill_dir / skill["name"])

    print(f"  opencode: {count} agents + {len(data['skills'])} skills in {oc_dir}")


# ---------------------------------------------------------------------------
# Claude Code emitter
# ---------------------------------------------------------------------------

def emit_claude(data, out_dir):
    """Emit Claude Code artifacts."""
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

        fm_str = _yaml_dump(frontmatter)
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

        fm_str = _yaml_dump(frontmatter)
        with open(skill_dir / "SKILL.md", "w") as f:
            f.write(f"---\n{fm_str}---\n{body}\n")
        # Companion files for directory-form skills go beside SKILL.md
        copy_skill_extra_files(skill, skill_dir)

    print(f"  claude: {count} agents + {len(data['skills'])} skills in {claude_dir}")


# ---------------------------------------------------------------------------
# Manifest emitter
# ---------------------------------------------------------------------------

def _read_version():
    """Read package version from scripts/package.json or root package.json.

    Returns version string or None if unavailable.
    """
    for candidate in (REPO_ROOT / "scripts" / "package.json",
                      REPO_ROOT / "package.json"):
        try:
            with open(candidate) as f:
                pkg = json.load(f)
            v = pkg.get("version")
            if v:
                return v
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return None


def emit_manifest(data, out_dir):
    """Emit install-manifest.json describing tool artifact paths."""
    manifest_dir = out_dir
    manifest_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "package": "@gelse/ai-snippets",
        "tools": {
            "zoo": {
                "modes": {
                    "src": "zoo/.roomodes",
                    "local": ".roomodes",
                    "global": "~/.roo/custom_modes.yaml",
                    "merge": True,
                },
                "skillsDir": {
                    "src": "zoo/skills",
                    "local": ".roo/skills",
                    "global": "~/.roo/skills",
                },
            },
            "kilo": {
                "modes": {
                    "src": "kilo/.kilocodemodes",
                    "local": ".kilocodemodes",
                    "global": None,
                },
                "skillsDir": {
                    "src": "kilo/skills",
                    "local": ".kilo/skills",
                    "global": "~/.kilo/skills",
                },
            },
            "opencode": {
                "modesDir": {
                    "src": "opencode/agents",
                    "local": ".opencode/agents",
                    "global": "~/.config/opencode/agents",
                },
                "skillsDir": {
                    "src": "opencode/skill",
                    "local": ".opencode/skills",
                    "global": "~/.config/opencode/skills",
                },
            },
            "claude": {
                "modesDir": {
                    "src": "claude/agents",
                    "local": ".claude/agents",
                    "global": "~/.claude/agents",
                },
                "skillsDir": {
                    "src": "claude/skills",
                    "local": ".claude/skills",
                    "global": "~/.claude/skills",
                },
            },
        },
    }

    version = _read_version()
    if version:
        manifest["version"] = version

    manifest_path = manifest_dir / "install-manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"  manifest: {manifest_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

EMITTERS = {
    "zoo": emit_zoo,
    "kilo": emit_kilo,
    "opencode": emit_opencode,
    "claude": emit_claude,
    "manifest": emit_manifest,
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
    data["customModes"] = resolve_custom_instructions(data["customModes"])
    out_dir = REPO_ROOT / args.out

    # Defense-in-depth: validate all skill names before processing
    for skill in data["skills"]:
        if not re.fullmatch(r"[a-z0-9-]+", skill["name"]):
            print(
                f"ERROR: Invalid skill name '{skill['name']}' — "
                "must match ^[a-z0-9-]+$",
                file=sys.stderr,
            )
            sys.exit(1)

    print(f"Generating {args.tool} artifacts...")
    EMITTERS[args.tool](data, out_dir)
    print("Done.")


if __name__ == "__main__":
    main()
