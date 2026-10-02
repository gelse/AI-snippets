#!/usr/bin/env python3
"""Installer CLI for ai-snippets.

Reads output/install-manifest.json, plans the installation, then executes it
with collision handling (files and directories) and merge support for zoo
global modes via merge() imported from scripts/merge-modes.py.

Usage:
    scripts/install.py [install] <tool> [options]

Summary block, prompt strings, plan ordering, and exit codes mirror the
previous TypeScript installer CLI so the smoke-test contract stays intact.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "output" / "install-manifest.json"
SOURCE_ROOT = REPO_ROOT / "output"
MERGE_MODULE_PATH = REPO_ROOT / "scripts" / "merge-modes.py"

VALID_TOOLS = ("zoo", "kilo", "opencode")
SEPARATOR = "─" * 50

USAGE = """\
Usage: install.py [install] <tool> [options]

Install generated skills and agent modes for an AI coding tool.

Tools: zoo, kilo, opencode

Options:
  --global          Install to global tool config directory (default)
  --local           Install to local (project) tool config directory
  --skills-only     Install only skills (skip agent modes)
  --agents-only     Install only agent modes (skip skills)
  --dry-run         Show what would be installed without writing files
  --yes, -y         Overwrite existing files without prompting
  -h, --help        Show this help message

If no tool is specified, an interactive wizard will guide you.

Examples:
  install.py install zoo --global
  install.py install opencode --global --skills-only --yes
"""


class CliArgs:
    """Parsed command line arguments."""

    def __init__(self) -> None:
        self.tool: str | None = None
        self.scope: str = "global"
        self.filter: str = "all"
        self.dry_run: bool = False
        self.yes: bool = False


def _fail_usage(message: str) -> None:
    print(message, file=sys.stderr)
    print(USAGE, file=sys.stderr)
    sys.exit(1)


def parse_args(argv: list[str]) -> CliArgs:
    """Manually parse argv.

    argparse is unsuitable here: it would bind the tool positional to a
    choice-validated slot and exit 2 on the wrong error path, and it cannot
    express the "drop a literal leading 'install'" pre-normalization.

    '--' terminates parsing: every token after it is ignored.
    """
    tokens = list(argv)

    # Pre-normalize: drop a literal 'install' if it is the first non-flag token.
    for i, tok in enumerate(tokens):
        if tok == "--" or tok.startswith("-"):
            continue
        if tok == "install":
            del tokens[i]
        break

    args = CliArgs()
    scope_flag: str | None = None
    filter_flag: str | None = None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--":
            break  # '--' terminates parsing; all remaining tokens are ignored
        if args.tool is None and not tok.startswith("-"):
            if tok not in VALID_TOOLS:
                _fail_usage(f"ERROR: unknown tool '{tok}'")
            args.tool = tok
        elif tok in ("--global", "--local"):
            if scope_flag is not None and scope_flag != tok:
                _fail_usage("ERROR: --global and --local are mutually exclusive")
            scope_flag = tok
            args.scope = "global" if tok == "--global" else "local"
        elif tok in ("--skills-only", "--agents-only"):
            if filter_flag is not None and filter_flag != tok:
                _fail_usage("ERROR: --skills-only and --agents-only are mutually exclusive")
            filter_flag = tok
            args.filter = "skills-only" if tok == "--skills-only" else "agents-only"
        elif tok == "--dry-run":
            args.dry_run = True
        elif tok in ("--yes", "-y"):
            args.yes = True
        elif tok in ("-h", "--help"):
            print(USAGE)
            sys.exit(0)
        else:
            _fail_usage(f"Unknown argument: {tok}")
        i += 1
    return args


def _load_merge():
    """Load merge() from scripts/merge-modes.py (filename kept for the Makefile)."""
    spec = importlib.util.spec_from_file_location("merge_modes", MERGE_MODULE_PATH)
    if spec is None or spec.loader is None:
        print(f"ERROR: cannot load merge module {MERGE_MODULE_PATH}", file=sys.stderr)
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.merge


def _load_manifest() -> dict:
    if not MANIFEST_PATH.is_file():
        print(
            "ERROR: output/install-manifest.json not found — "
            "run `make all` (or `make manifest`) first.",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(MANIFEST_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _ask(question: str) -> str:
    """Write the question to stderr, then read exactly one line of stdin.

    One line per call keeps piped multi-answer runs (e.g. printf 'o\\na\\n')
    driving sequential prompts correctly.
    """
    sys.stdout.flush()
    sys.stderr.write(question)
    sys.stderr.flush()
    line = sys.stdin.readline()
    if line == "":
        return ""  # EOF
    return line.strip()


def _prompt_overwrite(dest: str, merge: bool) -> str:
    """Three-line collision prompt on stderr; returns overwrite|skip|abort."""
    verb = "Merge into" if merge else "Overwrite"
    print(f"\n  Destination exists: {dest}", file=sys.stderr)
    print(f"  {verb}?", file=sys.stderr)
    answer = _ask("  [o]verwrite / [s]kip / [a]bort: ").lower()
    if answer in ("a", "abort"):
        return "abort"
    if answer in ("s", "skip"):
        return "skip"
    if answer == "":
        if not sys.stdin.isatty():
            print(
                "Unexpected end of input — cannot prompt for overwrite in "
                "non-interactive mode. Use --yes or provide answers via stdin.",
                file=sys.stderr,
            )
            sys.exit(1)
        return "overwrite"  # TTY default
    return "overwrite"


def _collect_artifacts(entry: dict, args: CliArgs) -> list[dict]:
    """Build the artifact list in manifest key order (modes → modesDir → skillsDir)."""
    artifacts: list[dict] = []
    scope_key = args.scope

    modes = entry.get("modes")
    if modes and args.filter in ("all", "agents-only"):
        dest = modes.get(scope_key)
        if dest:
            artifacts.append({
                "kind": "modes",
                "src": modes["src"],
                "dest": os.path.expanduser(dest),
                "is_dir": False,
                "merge": bool(modes.get("merge", False)),
            })

    modes_dir = entry.get("modesDir")
    if modes_dir and args.filter in ("all", "agents-only"):
        dest = modes_dir.get(scope_key)
        if dest:
            artifacts.append({
                "kind": "modesDir",
                "src": modes_dir["src"],
                "dest": os.path.expanduser(dest),
                "is_dir": True,
                "merge": False,
            })

    skills_dir = entry.get("skillsDir")
    if skills_dir and args.filter in ("all", "skills-only"):
        dest = skills_dir.get(scope_key)
        if dest:
            artifacts.append({
                "kind": "skillsDir",
                "src": skills_dir["src"],
                "dest": os.path.expanduser(dest),
                "is_dir": True,
                "merge": False,
            })

    return artifacts


def _print_plan(artifacts: list[dict], args: CliArgs) -> None:
    lines = [
        f"Tool: {args.tool}",
        f"Scope: {args.scope}",
        f"Filter: {args.filter}",
    ]
    if args.dry_run:
        lines.append("Mode: DRY RUN (no files were written)")
    lines.append("")
    lines.append("Actions:")

    for art in artifacts:
        src_path = SOURCE_ROOT / art["src"]
        if not src_path.exists():
            print(f"ERROR: Source artifact not found: {src_path}", file=sys.stderr)
            sys.exit(1)
        exists = os.path.exists(art["dest"])
        if art["is_dir"]:
            label = "update" if exists else "create"
        elif exists:
            label = "merge" if art["merge"] else "overwrite"
        else:
            label = "create"
        lines.append(f"  [{label}] {art['dest']} ← output/{art['src']}")

    print("\n".join(lines))


def _install_artifacts(artifacts: list[dict], args: CliArgs, merge_fn) -> dict:
    result = {"installed": 0, "skipped": 0, "merged": 0, "replaced": [], "kept": []}

    for art in artifacts:
        src_path = SOURCE_ROOT / art["src"]
        dest: str = art["dest"]
        dest_exists = os.path.exists(dest)

        # Dry-run: count only, no prompts, no writes.
        if args.dry_run:
            if dest_exists and art["merge"]:
                result["merged"] += 1
            else:
                result["installed"] += 1
            continue

        # Collision handling covers files AND directories.
        if dest_exists and not args.yes:
            choice = _prompt_overwrite(dest, art["merge"])
            if choice == "skip":
                result["skipped"] += 1
                continue
            if choice == "abort":
                sys.exit(1)  # USER_ABORT: no further writes this run

        if art["is_dir"]:
            os.makedirs(dest, exist_ok=True)
            shutil.copytree(src_path, dest, dirs_exist_ok=True)
            result["installed"] += 1
        elif art["merge"]:
            # A merge target counts as merged only — never Installed/updated.
            replaced, kept, _added = merge_fn(src_path, dest)
            result["replaced"].extend(replaced)
            result["kept"].extend(kept)
            result["merged"] += 1
        else:
            dest_dir = os.path.dirname(dest)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(src_path, dest)
            result["installed"] += 1

    return result


def _print_summary(result: dict, dry_run: bool) -> None:
    print()
    print(SEPARATOR)
    print("DRY RUN SUMMARY (no files were written)" if dry_run else "INSTALL SUMMARY")
    print(SEPARATOR)
    if result["installed"] > 0:
        print(f"  Installed/updated: {result['installed']}")
    if result["skipped"] > 0:
        print(f"  Skipped: {result['skipped']}")
    if result["merged"] > 0:
        print(f"  Merged: {result['merged']}")
    if result["replaced"]:
        print(f"  Replaced slugs: {', '.join(result['replaced'])}")
    if result["kept"]:
        print(f"  Kept user slugs: {', '.join(result['kept'])}")
    if (
        result["installed"] == 0
        and result["skipped"] == 0
        and result["merged"] == 0
    ):
        print("  Nothing to install.")
    print(SEPARATOR)


def _wizard(manifest: dict) -> tuple[str, str] | None:
    """Interactive tool/scope wizard; prompts go to stderr. Never asks filters."""
    tools = list(manifest["tools"])

    print("\nAvailable tools:", file=sys.stderr)
    for i, tool in enumerate(tools):
        print(f"  {i + 1}. {tool}", file=sys.stderr)
    print(file=sys.stderr)

    answer = _ask(f"Select tool [1-{len(tools)}]: ")
    try:
        idx = int(answer) - 1
    except ValueError:
        idx = -1
    if idx < 0 or idx >= len(tools):
        return None
    tool = tools[idx]

    print(file=sys.stderr)
    print("  1. Global (tool-wide config)", file=sys.stderr)
    print("  2. Local (project-level config)", file=sys.stderr)
    scope = "local" if _ask("Select scope [1-2]: ") == "2" else "global"

    print(file=sys.stderr)
    print(f"Installing {tool} ({scope})...", file=sys.stderr)
    confirm = _ask("Proceed? [Y/n]: ")
    if confirm.lower() in ("n", "no"):
        return None
    return tool, scope


def main(argv: list[str]) -> int:
    args = parse_args(argv[1:])
    merge_fn = _load_merge()
    manifest = _load_manifest()

    if args.tool is None:
        wizard_result = _wizard(manifest)
        if wizard_result is None:
            print("Aborted.")
            return 1
        args.tool, args.scope = wizard_result

    tool_entry = manifest["tools"].get(args.tool)
    if tool_entry is None:
        available = ", ".join(manifest["tools"])
        print(f'Error: Unknown tool "{args.tool}". Available: {available}', file=sys.stderr)
        return 1

    artifacts = _collect_artifacts(tool_entry, args)
    if not artifacts:
        print("No artifacts to install for the given scope/filter combination.")
        return 0

    _print_plan(artifacts, args)
    print()

    result = _install_artifacts(artifacts, args, merge_fn)
    _print_summary(result, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
