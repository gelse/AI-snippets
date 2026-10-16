"""Generate mode/skill artifacts for Zoo Code, Kilo Code, and OpenCode.

Usage:
    scripts/generate.py {zoo|kilo|opencode} [--out output]
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
        if (
            self.event.style in ("|", ">")
            and not self.flow_level
            and not self.simple_key_context
        ):
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
    return yaml.dump(
        obj,
        Dumper=_LiteralDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=4096,
    )


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


def load_model_mapping():
    """Load models/mapping.yaml and build an agent-slug -> model-id dict.

    Only the ``agent`` and ``model`` fields of each ``agent-mapping`` entry
    are used; ``fallbacks`` are ignored.
    """
    with open(REPO_ROOT / "models" / "mapping.yaml") as f:
        data = yaml.safe_load(f)
    return {
        entry["agent"]: entry["model"]
        for entry in data.get("model-mapping", {}).get("agent-mapping", [])
        if entry.get("agent") and entry.get("model")
    }


def load_harnesses():
    """Load harnesses.json from repo root and return the parsed dict."""
    with open(REPO_ROOT / "harnesses.json") as f:
        return json.load(f)


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
        body = content[end + 3 :].removeprefix("\n")

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


# ---------------------------------------------------------------------------
# OpenCode v2 permission translation
# ---------------------------------------------------------------------------

# opencode V1 permission names accepted in the agent frontmatter
# 'permission' map. These are the names the opencode runtime (1.18.35)
# actually matches on when compiling {permission, pattern, action} rules:
# there is no 'shell' or 'subagent' name at runtime — modes.json's 'shell'
# emits as 'bash' and 'task' emits as 'task'.
OPENCODE_PERMISSION_ACTIONS = (
    "read",
    "edit",
    "glob",
    "grep",
    "bash",
    "task",
    "skill",
    "lsp",
    "question",
    "webfetch",
    "websearch",
    "external_directory",
    "doom_loop",
)
OPENCODE_PERMISSION_EFFECTS = {"allow", "ask", "deny"}

# modes.json key -> the opencode V1 permission name it emits as. The
# modes.json vocabulary ('shell', 'task') is the repo's own and must not be
# renamed; only the emitted opencode name changes.
MODES_KEY_TO_ACTION = {
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

# Decoded fileRegex (the value modes.json holds after JSON parse) -> opencode
# glob. Extend this mapping when a mode introduces a new fileRegex; map to
# the narrowest glob, never a bare '*'.
FILEREGEX_TO_GLOB = {r"\.md$": "*.md"}


class FileRegexNotImplemented(Exception):
    """A mode's groups carry a fileRegex with no FILEREGEX_TO_GLOB entry."""


# ---------------------------------------------------------------------------
# Shell 'auto' permission expansion
# ---------------------------------------------------------------------------

# The modes.json shell permission value 'auto' is repo vocabulary expanded at
# generate time — modes.json never carries the expanded map. It becomes a
# per-command pattern map: a catch-all '*' gate first ('ask' for primary
# modes, 'deny' for every other instantiation), then an 'allow' pair for each
# read-only command below (bare `cmd` for no-arg invocations and `cmd *` for
# invocations with arguments). Entry order is the last-match-wins policy: the
# broad '*' gate first, the safe-command allows after, so safe commands win.
#
# The list is copied from scripts/reference/approve_readonly_bash.py# (REFERENCE ONLY — not imported; nothing executes that file): upstream's
# SAFE_COMMANDS allow list. Upstream's DESTRUCTIVE_COMMANDS,
# WRAPPER_COMMANDS and DANGEROUS_PATTERNS are deliberately NOT implemented:
# those commands are absent from this list, so they fall through to the
# catch-all effect. Upstream's finer-grained flag logic (git write
# subcommands, sed -i, curl -o, ...) is also not modelled — the pattern-map
# format cannot express it — so those invocations match their command's
# allow entry like any other argument set.
SHELL_AUTO = "auto"

SAFE_SHELL_COMMANDS = (
    # Display
    "echo",
    "printf",
    "cat",
    "head",
    "tail",
    "less",
    "more",
    "bat",
    # File info (read-only)
    "ls",
    "find",
    "file",
    "stat",
    "du",
    "df",
    "wc",
    "tree",
    "realpath",
    "dirname",
    "basename",
    "readlink",
    "pwd",
    "md5",
    "shasum",
    "sha256sum",
    "md5sum",
    "cksum",
    # Text processing (read-only when no -i flag)
    "grep",
    "egrep",
    "fgrep",
    "rg",
    "ag",
    "ack",
    "awk",
    "gawk",
    "sed",
    "gsed",
    "sort",
    "uniq",
    "cut",
    "tr",
    "rev",
    "fold",
    "column",
    "paste",
    "join",
    "comm",
    "diff",
    "cmp",
    "jq",
    "yq",
    "xmllint",
    "fmt",
    # Git (subcommand checked separately upstream)
    "git",
    # Network diagnostics (read-only)
    "ifconfig",
    "netstat",
    "ss",
    "route",
    "dig",
    "nslookup",
    "host",
    "ping",
    "traceroute",
    "mtr",
    "curl",
    # System info
    "ps",
    "pgrep",
    "top",
    "htop",
    "who",
    "whoami",
    "w",
    "id",
    "groups",
    "uname",
    "hostname",
    "uptime",
    "date",
    "cal",
    "printenv",
    "locale",
    "which",
    "where",
    "type",
    "command",
    "sw_vers",
    "system_profiler",
    "sysctl",
    "vm_stat",
    "iostat",
    "lsof",
    "nettop",
    "arch",
    "getconf",
    "ulimit",
    # macOS (read-only; commands with write modes checked separately upstream)
    "pbpaste",
    "plutil",
    "mdls",
    "mdfind",
    "dscacheutil",
    "klist",
    "log",
    "ioreg",
    "open",  # opens files/URLs, non-destructive
    "scutil",  # --dns/--proxy safe; --set blocked by flag check upstream
    "defaults",  # read safe; write/delete blocked by flag check upstream
    "networksetup",  # list* safe; set* blocked by flag check upstream
    # Navigation
    "cd",
    # Shell builtins (safe)
    "test",
    "[",
    "true",
    "false",
    "time",
    # Version / help
    "man",
    "info",
    "help",
)


def expand_auto_shell(instantiation):
    """Expand the shell permission value ``'auto'`` into a pattern map.

    The catch-all ``'*'`` gate comes first: ``'ask'`` for modes whose
    ``instantiation`` is ``'primary'`` (they converse with the user, so a
    prompt is answerable), ``'deny'`` for every other instantiation
    (``'all'`` and ``'subagent'`` run headless as subagents, where a prompt
    would stall). Each ``SAFE_SHELL_COMMANDS`` entry then adds ``'allow'``
    patterns — bare ``cmd`` and ``cmd *`` — so read-only commands run
    without friction regardless of arguments. The runtime applies map
    entries in order and keeps the last match.
    """
    catch_all = "ask" if instantiation == "primary" else "deny"
    shell_map = {"*": catch_all}
    for cmd in SAFE_SHELL_COMMANDS:
        shell_map[cmd] = "allow"
        shell_map[f"{cmd} *"] = "allow"
    return shell_map


def translate_opencode_permissions(
    slug, groups, global_perms, instantiation="all"
) -> dict:
    """Translate a mode's permissions entry to an opencode V1 permission map.

    Returns the agent frontmatter ``permission`` map: opencode name ->
    effect string, or name -> {pattern: effect} for scoped entries.
    opencode compiles the map into ``{permission, pattern, action}`` rules
    in insertion order and keeps the last matching rule, so a scoped edit
    entry lists the broad ``*`` deny first and the scoped allow second.
    The modes.json keys 'shell' and 'task' are repo vocabulary; they are
    emitted as 'bash' and 'task', the names the runtime matches on.

    ``perms['shell']`` accepts three shapes. A scalar effect passes through
    verbatim. The scalar ``'auto'`` (valid for 'shell' only) expands via
    ``expand_auto_shell(instantiation)`` into the safe-command pattern map
    — catch-all ``'*'`` gate first ('ask' for ``instantiation == 'primary'``
    modes, 'deny' otherwise), then the ``SAFE_SHELL_COMMANDS`` allows —
    so the emitter (not modes.json) carries the expanded list. ``'auto'``
    on any other key raises ``ValueError``: the runtime knows no such
    effect and a silent pass-through would emit a broken map. A dict is
    passed through verbatim (Python preserves insertion order;
    ``_yaml_dump`` emits dicts in insertion order via ``sort_keys=False``),
    so the author-supplied order is policy and is not re-sorted or
    re-arranged here. Map values for any
    of the other keys (``read``, ``glob``, ``grep``, ``skill``, ``task``,
    ``lsp``, ``external_directory``) are also passed through unvalidated by
    the translator (``edit`` is not: a scoped edit group is synthesized into
    the broad-deny/scoped-allow map above); the structural check in
    ``scripts/verify.py`` and verify (f)'s value-shape check cover them.

    The four new keys (``lsp``, ``question``, ``external_directory``,
    ``doom_loop``) are emitted verbatim from the modes.json row — no
    implicit runtime fallback is added (a silent fallback could
    reintroduce upstream's default-``ask`` stall risk for partial rows).

    When ``perms['question']`` or ``perms['doom_loop']`` is a dict, the
    translator raises ``TypeError`` — these two actions are upstream
    ``actionOnly`` and accept scalar effects only. ``lsp`` and
    ``external_directory`` accept scalar or pattern map; the structural
    check in ``scripts/verify.py`` covers their shape.
    """
    if slug not in global_perms:
        raise ValueError(
            f"No permissions entry for mode '{slug}'; every non-deprecated "
            "mode must declare one in modes.json.permissions"
        )
    perms = global_perms[slug]

    # Scoped edit group: the ["edit", {"fileRegex": "..."}] shape in groups
    scoped_glob = None
    for g in groups:
        if not (isinstance(g, list) and g and g[0] == "edit"):
            continue
        if len(g) < 2 or not isinstance(g[1], dict) or "fileRegex" not in g[1]:
            continue
        file_regex = g[1]["fileRegex"]
        if file_regex not in FILEREGEX_TO_GLOB:
            raise FileRegexNotImplemented(
                f"Mode '{slug}': no FILEREGEX_TO_GLOB mapping for fileRegex "
                f"{file_regex!r} — add one in scripts/generate.py, mapped to "
                "the narrowest glob (never a bare '*')"
            )
        scoped_glob = FILEREGEX_TO_GLOB[file_regex]
        break

    perm_map = {}
    if perms["edit"] == "allow" and scoped_glob is not None:
        # Broad deny first, scoped allow second: last-match-wins lets the
        # scoped allow win for matching paths while the rest stays denied.
        perm_map["edit"] = {"*": "deny", scoped_glob: "allow"}
    else:
        # deny/ask gates the whole action, so no scoped override is ever
        # emitted — a scoped allow would subvert that decision.
        perm_map["edit"] = perms["edit"]

    # Map-valued 'shell' (per-command bash patterns): the author-supplied
    # entry order is policy and passes through untouched, but each entry
    # must at least be shape-valid (non-empty string pattern -> effect in
    # the opencode vocabulary) — mirroring the missing-slug guard above.
    if isinstance(perms["shell"], dict):
        if not perms["shell"]:
            raise ValueError(
                f"Mode '{slug}': permissions 'shell' pattern map must not be empty"
            )
        for pattern, effect in perms["shell"].items():
            if (
                not isinstance(pattern, str)
                or not pattern
                or not isinstance(effect, str)
                or effect not in OPENCODE_PERMISSION_EFFECTS
            ):
                raise ValueError(
                    f"Mode '{slug}': permissions 'shell' pattern map "
                    f"entries must map non-empty string patterns to one "
                    f"of {sorted(OPENCODE_PERMISSION_EFFECTS)}; got "
                    f"{pattern!r}: {effect!r}"
                )

    # 'auto' is repo vocabulary valid for 'shell' only: on any other key it
    # would emit an effect string the runtime does not know, so fail loud at
    # generate time instead of silently producing a broken map (the
    # structural check in scripts/verify.py rejects it at check time too).
    for key, value in perms.items():
        if key != "shell" and value == SHELL_AUTO:
            raise ValueError(
                f"Mode '{slug}': permissions '{key}' must not be "
                f"{SHELL_AUTO!r} — the {SHELL_AUTO!r} expansion is valid "
                "for 'shell' only"
            )

    # Scalar-only actions: upstream marks 'question' and 'doom_loop' as
    # actionOnly (scalar effects only), so a pattern map would be silently
    # inert there. Fail loud at generate time — symmetric with the shell
    # guard above — instead of emitting a map the runtime cannot apply.
    for scalar_only_key in ("question", "doom_loop"):
        v = perms[scalar_only_key]
        if isinstance(v, dict):
            raise TypeError(
                f"Mode '{slug}': permissions '{scalar_only_key}' must be a "
                f"plain scalar in {sorted(OPENCODE_PERMISSION_EFFECTS)}; "
                f"opencode's '{scalar_only_key}' action is actionOnly "
                "(scalar effects only). Got "
                f"{v!r}"
            )

    for key in (
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
    ):
        if key == "shell" and perms["shell"] == SHELL_AUTO:
            # Expanded form: catch-all gate first, then SAFE_SHELL_COMMANDS
            # allows (see expand_auto_shell)
            perm_map[MODES_KEY_TO_ACTION[key]] = expand_auto_shell(instantiation)
            continue
        perm_map[MODES_KEY_TO_ACTION[key]] = perms[key]
    return perm_map


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
        body = content[end + 3 :].removeprefix("\n")
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

    model_by_slug = load_model_mapping()
    subtask_instructions = (
        load_harnesses().get("opencode", {}).get("subtaskInstructions", [])
    )

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
            "mode": mode.get("instantiation", "all"),
        }

        # Inserted between 'mode' and 'permission' so frontmatter field order
        # is: description, mode, model, permission. Skipped when the slug has
        # no mapping entry.
        model_id = model_by_slug.get(slug)
        if model_id:
            frontmatter["model"] = f"litellm/{model_id}"

        frontmatter["permission"] = translate_opencode_permissions(
            slug,
            groups,
            data["permissions"],
            instantiation=mode.get("instantiation", "all"),
        )

        subtask_block = "## Starting Subtasks"
        joined = "\n\n".join(subtask_instructions)
        if joined:
            subtask_block += "\n\n" + joined
        if instructions:
            body = f"{role}\n\n{subtask_block}\n\n{instructions}"
        else:
            body = f"{role}\n\n{subtask_block}"

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
        skill_subdir = skill_dir / skill["name"]
        skill_subdir.mkdir(parents=True, exist_ok=True)
        with open(skill_subdir / "SKILL.md", "w") as f:
            f.write(f"---\n{fm_str}---\n{body}\n")
        # Companion files for directory-form skills go in skill/<name>/
        copy_skill_extra_files(skill, skill_dir / skill["name"])

    print(f"  opencode: {count} agents + {len(data['skills'])} skills in {oc_dir}")


# ---------------------------------------------------------------------------
# Manifest emitter
# ---------------------------------------------------------------------------


def _read_version():
    """Read package version from scripts/package.json or root package.json.

    Returns version string or None if unavailable.
    """
    for candidate in (
        REPO_ROOT / "scripts" / "package.json",
        REPO_ROOT / "package.json",
    ):
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
