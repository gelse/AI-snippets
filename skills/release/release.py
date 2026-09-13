"""Release automation CLI for the AI-snippets workspace.

Runs in the TARGET repo (CWD).  Stdlib-only (Python ≥ 3.11 for tomllib).

Tag-target rule:
    The release tag always points at the HEAD of testing after the release PR
    is merged.  Tags are formatted as vX.Y.Z (one leading 'v' prefix).

Version normalization:
    Any version input (X.Y.Z, vX.Y.Z, etc.) is normalized by stripping a
    single leading 'v'.  Internal comparisons use bare X.Y.Z; tags are
    always vX.Y.Z.

Usage:
    .venv/bin/python skills/release/release.py <subcommand> [options]

Subcommands:
    preflight [--version X]   Validate repo state and optional version.
    changes   [--base TAG] [--out FILE]  Draft changelog notes.
    check-version --version X  Validate version ordering.
    finalize  --version X --notes FILE [--commit SHA]  Tag and create release.
    post-verify --version X   Verify release was published correctly.
"""

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import tomllib

# ---------------------------------------------------------------------------
# Helpers (mirroring scripts/verify.py style)
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")


def fail(msg):
    """Print an error message and exit non-zero."""
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def ok(msg):
    """Print a success message."""
    print(f"  OK: {msg}")


def run(cmd, capture=True, check=True):
    """Run a command via subprocess (list-form, no shell).

    When *check* is True (default) the process must exit 0; when False the
    caller inspects the return code manually.

    Prints a readable representation of the executed command.
    """
    display = shlex.join(cmd) if isinstance(cmd, list) else cmd
    print(f"  $ {display}")
    result = subprocess.run(
        cmd, capture_output=capture, text=True, check=False,
    )
    if check and result.returncode != 0:
        stderr = result.stderr.strip() if capture else ""
        fail(f"Command failed (exit {result.returncode}): {display}\n{stderr}")
    return result


def normalize_version(v):
    """Strip a single leading 'v' and enforce strict X.Y.Z format.

    >>> normalize_version("v1.2.3")
    '1.2.3'
    >>> normalize_version("1.2.3")
    '1.2.3'
    """
    stripped = v.removeprefix("v")
    if not _VERSION_RE.match(stripped):
        fail(
            f"Invalid version '{v}': must match X.Y.Z "
            f"(e.g. 1.2.3 or v1.2.3)"
        )
    return stripped


def parse_version_tuple(v):
    """Convert 'X.Y.Z' to (X, Y, Z) integer tuple for comparison."""
    parts = v.split(".")
    return tuple(int(p) for p in parts)


def validate_commit(sha):
    """Validate that *sha* looks like a hex commit hash."""
    if not _COMMIT_RE.match(sha):
        fail(
            f"Invalid commit SHA '{sha}': must be7-40 hex characters"
        )


def tag_name(v):
    """Return the tag form of a normalized version: vX.Y.Z."""
    return f"v{v}"


# ---------------------------------------------------------------------------
# Subcommand: preflight
# ---------------------------------------------------------------------------


def cmd_preflight(args):
    """Validate repo state before release.

    Checks: clean tree, testing branch, sync with origin, tag availability.
    If --version is given, also validates pyproject.toml and tag uniqueness.
    """
    print("[preflight] Validating release prerequisites\n")

    # Dirty tree check
    result = run(["git", "status", "--porcelain"])
    if result.stdout.strip():
        fail("Working tree is dirty — commit or stash changes first")

    # Current branch
    result = run(["git", "branch", "--show-current"])
    branch = result.stdout.strip()
    if branch != "testing":
        fail(f"Must be on 'testing' branch, currently on '{branch}'")
    ok("On 'testing' branch")

    # Fetch all remotes and tags
    run(["git", "fetch", "--all", "--tags"])

    # Sync with origin/testing
    result = run(["git", "rev-parse", "HEAD"])
    local_head = result.stdout.strip()
    result = run(["git", "rev-parse", "origin/testing"])
    remote_head = result.stdout.strip()
    if local_head != remote_head:
        fail(
            f"Local testing ({local_head[:8]}) differs from "
            f"origin/testing ({remote_head[:8]}) — git pull first"
        )
    ok(f"Local testing synced with origin/testing ({local_head[:8]})")

    # Previous tag — filter to valid release tags only
    result = run(["git", "tag", "-l", "v*"])
    raw_tags = [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]
    tags = []
    for t in raw_tags:
        ver = t[1:]  # strip leading 'v'
        if _VERSION_RE.match(ver):
            tags.append(t)
        else:
            print(f"  WARN: skipping non-release tag '{t}'")
    if tags:
        # Sort by version tuple descending
        tags_sorted = sorted(tags, key=lambda t: parse_version_tuple(t[1:]), reverse=True)
        last_tag = tags_sorted[0]
        last_version = last_tag[1:]  # strip leading 'v'
        ok(f"Previous tag: {last_tag} (version {last_version})")
    else:
        last_tag = None
        ok("No existing tags — this is the first release")

    if args.version:
        v = normalize_version(args.version)
        t = tag_name(v)

        # Tag must not exist locally
        if t in tags:
            fail(f"Tag '{t}' already exists locally")

        # Tag must not exist on remote
        result = run(["git", "ls-remote", "--tags", "origin", t])
        if result.stdout.strip():
            fail(f"Tag '{t}' already exists on remote")

        # gh release must not exist
        result = subprocess.run(
            ["gh", "release", "view", t],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            fail(f"GitHub release '{t}' already exists")

        # pyproject.toml version check
        pyproject_path = Path("pyproject.toml")
        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)
            pyproject_version = pyproject.get("project", {}).get("version", "")
            if pyproject_version:
                ok(f"pyproject.toml version: {pyproject_version}")
            else:
                ok("pyproject.toml has no version field (will be set)")
        else:
            ok("No pyproject.toml found (will be created)")

        print(f"\n  Proposed version: {v}")
        print(f"  Tag: {t}")

    if last_tag:
        print(f"  Last tag: {last_tag}")
    else:
        print("  Last tag: (none — first release)")

    print("\nPreflight passed.")


# ---------------------------------------------------------------------------
# Subcommand: changes
# ---------------------------------------------------------------------------


def cmd_changes(args):
    """Draft changelog notes from commits and merged PRs.

    --base TAG: starting point (omit for first release).
    --out FILE: write markdown to file (default: stdout).
    """
    print("[changes] Drafting changelog notes\n")

    base = args.base
    if base:
        base = normalize_version(base)
        base_tag = tag_name(base)

        # Validate the base tag exists
        result = run(
            ["git", "rev-parse", "-q", "--verify", f"refs/tags/{base_tag}"],
        )
        if result.returncode != 0:
            fail(f"Base tag '{base_tag}' does not exist")
        ok(f"Base tag: {base_tag}")

        # Compute tag date in a separate call
        result = run(["git", "log", "-1", "--format=%aI", base_tag])
        base_date = result.stdout.strip()
        ok(f"Base tag date: {base_date}")

        # Commits since base tag
        result = run(["git", "log", f"{base_tag}..HEAD", "--oneline", "--no-decorate"])
        commits = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        print(f"  Found {len(commits)} commits since {base_tag}")

        # Merged PRs after base tag date
        result = run([
            "gh", "pr", "list", "--state", "merged", "--base", "testing",
            "--limit", "100", "--json", "number,title,mergedAt",
            "--jq",
            f'[.[] | select(.mergedAt >= "{base_date}" | todate)]'
            + " | .[] | \"- #\\(.number) \\(.title)\"",
        ])
        pr_lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    else:
        print("  First release — full history")
        # All commits from root
        result = run(["git", "log", "--oneline", "--no-decorate"])
        commits = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        print(f"  Found {len(commits)} total commits")

        # All merged PRs
        result = run([
            "gh", "pr", "list", "--state", "merged", "--base", "testing",
            "--limit", "100", "--json", "number,title",
            "--jq", '.[] | "- #\\(.number) \\(.title)"',
        ])
        pr_lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]

    # Build markdown draft
    lines = []
    if base:
        lines.append(f"## Commits ({base_tag}..HEAD)\n")
    else:
        lines.append("## Commits (full history)\n")

    if commits:
        for c in commits:
            lines.append(f"- {c}")
    else:
        lines.append("- (no commits found)")
    lines.append("")

    lines.append("## Pull Requests\n")
    lines.extend(pr_lines)
    if not pr_lines:
        lines.append("- (no merged PRs found)")
    lines.append("")

    draft = "\n".join(lines)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(draft)
        print(f"\n  Draft written to: {out_path}")
    else:
        print("\n--- Changelog Draft ---")
        print(draft)
        print("--- End Draft ---")

    print("Changes draft complete.")


# ---------------------------------------------------------------------------
# Subcommand: check-version
# ---------------------------------------------------------------------------


def cmd_check_version(args):
    """Validate version format and ordering.

    Checks: X.Y.Z format, strictly greater than last tag, tag not yet used.
    """
    print("[check-version] Validating version\n")

    v = normalize_version(args.version)
    t = tag_name(v)

    v_tuple = parse_version_tuple(v)
    ok(f"Version format valid: {v}")

    # Ordering check against last tag — skip non-release tags with warning
    result = run(["git", "tag", "-l", "v*"])
    raw_tags = [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]
    release_tags = []
    for tg in raw_tags:
        ver = tg[1:]
        if _VERSION_RE.match(ver):
            release_tags.append(tg)
        else:
            print(f"  WARN: skipping non-release tag '{tg}'")

    if release_tags:
        release_tags_sorted = sorted(
            release_tags, key=lambda tg: parse_version_tuple(tg[1:]), reverse=True,
        )
        last_tag = release_tags_sorted[0]
        last_version = last_tag[1:]
        last_tuple = parse_version_tuple(last_version)

        if v_tuple <= last_tuple:
            fail(
                f"Version {v} is not greater than last tag {last_tag} "
                f"({last_version})"
            )
        ok(f"Version {v} > last tag {last_tag}")
    else:
        ok("No existing tags — version ordering not applicable")

    # Tag existence check
    result = run(["git", "ls-remote", "--tags", "origin", t])
    if result.stdout.strip():
        fail(f"Tag '{t}' already exists on remote")
    ok(f"Tag '{t}' does not yet exist")

    print(f"\nVersion {v} (tag {t}) is valid.")


# ---------------------------------------------------------------------------
# Subcommand: finalize
# ---------------------------------------------------------------------------


def cmd_finalize(args):
    """Tag the release and create a GitHub release.

    Fetches origin, checks out testing, pulls --ff-only, creates tag,
    pushes tag, and creates a GitHub release.  Resumable: if the tag
    already exists on remote but no GitHub release is found, the tag
    step is skipped and only the release is created.
    """
    print("[finalize] Creating release\n")

    v = normalize_version(args.version)
    t = tag_name(v)

    # Fetch origin
    run(["git", "fetch", "origin"])

    # Dirty-tree guard
    result = run(["git", "status", "--porcelain"])
    if result.stdout.strip():
        fail("Working tree is dirty — commit or stash changes first")

    # Checkout testing
    run(["git", "checkout", "testing"])

    # Pull ff-only
    run(["git", "pull", "--ff-only"])

    # Determine target commit
    if args.commit:
        target = args.commit
        validate_commit(target)
        # Verify the commit exists
        result = run(["git", "cat-file", "-t", target])
        ok(f"Using provided commit: {target}")
    else:
        result = run(["git", "rev-parse", "HEAD"])
        target = result.stdout.strip()
        ok(f"Using HEAD of testing: {target[:8]}")

    # Sanity: pyproject version == v
    pyproject_path = Path("pyproject.toml")
    if pyproject_path.exists():
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
        pyproject_version = pyproject.get("project", {}).get("version", "")
        if pyproject_version and normalize_version(pyproject_version) != v:
            fail(
                f"pyproject.toml version '{pyproject_version}' does not match "
                f"release version '{v}'"
            )
        ok(f"pyproject.toml version consistent: {pyproject_version}")

    # Check if tag already exists on remote (resumable finalize)
    result = run(["git", "tag", "-l", t])
    local_tag_exists = bool(result.stdout.strip())

    result = run(["git", "ls-remote", "--tags", "origin", t])
    remote_tag_exists = bool(result.stdout.strip())

    tag_already_pushed = local_tag_exists or remote_tag_exists

    if tag_already_pushed:
        # Check if GitHub release already exists
        gh_result = subprocess.run(
            ["gh", "release", "view", t],
            capture_output=True, text=True, check=False,
        )
        if gh_result.returncode == 0:
            fail(
                f"Tag '{t}' and GitHub release both already exist — "
                f"nothing to do"
            )
        # Tag exists but no release — resumable path
        if remote_tag_exists:
            ok(f"Tag '{t}' exists on remote but no GitHub release — "
               "skipping tag creation, proceeding to release")
        else:
            # Local tag exists but wasn't pushed yet — push it
            run(["git", "push", "origin", t])
            ok(f"Pushed tag {t} to origin (skipping local creation)")
    else:
        # Create tag
        run(["git", "tag", "-a", t, target, "-m", f"Release {t}"])
        ok(f"Created tag {t} at {target[:8]}")

        # Push tag
        run(["git", "push", "origin", t])
        ok(f"Pushed tag {t} to origin")

    # Read notes
    notes_path = Path(args.notes)
    if not notes_path.exists():
        fail(f"Notes file not found: {notes_path}")

    # Create GitHub release
    result = subprocess.run(
        [
            "gh", "release", "create", t,
            "--target", target,
            "--title", f"Release {t}",
            "--notes-file", str(notes_path),
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        fail(
            f"gh release create failed: {stderr}\n\n"
            f"The tag '{t}' is already pushed.  To recover:\n"
            f"  - Re-run finalize (it will skip tag creation and retry the "
            f"release).\n"
            f"  - Or run manually:\n"
            f"    gh release create {t} --target {target} "
            f"--notes-file {notes_path}"
        )
    release_url = result.stdout.strip()
    ok(f"GitHub release created: {release_url}")

    print(f"\n  Tagged commit: {target}")
    print(f"  Tag: {t}")
    print(f"  Release: {release_url}")
    print("\nFinalize complete.")


# ---------------------------------------------------------------------------
# Subcommand: post-verify
# ---------------------------------------------------------------------------


def cmd_post_verify(args):
    """Verify the release was published correctly.

    Checks: tag points at expected commit (with annotated-tag peeling),
    gh release exists, branch clean.
    """
    print("[post-verify] Verifying release\n")

    v = normalize_version(args.version)
    t = tag_name(v)

    # Expected commit = HEAD of testing
    run(["git", "fetch", "origin"])
    result = run(["git", "rev-parse", "origin/testing"])
    expected = result.stdout.strip()
    ok(f"Expected commit (origin/testing HEAD): {expected[:8]}")

    # Tag points at expected commit — peel annotated tags
    # Use refs/tags/<t>* pattern to include the ^{} peeled line
    result = run(["git", "ls-remote", "origin", f"refs/tags/{t}*"])
    output = result.stdout.strip()
    if not output:
        fail(f"Tag '{t}' not found on remote")

    # Resolve the peeled commit SHA:
    #   1. Prefer refs/tags/vX.Y.Z^{} (dereferenced, for annotated tags)
    #   2. Fall back to refs/tags/vX.Y.Z (lightweight or raw)
    peeled_line = None
    plain_line = None
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            ref = parts[1]
            if ref == f"refs/tags/{t}^{{}}":
                peeled_line = line
            elif ref == f"refs/tags/{t}":
                plain_line = line

    chosen_line = peeled_line or plain_line
    if not chosen_line:
        fail(f"Tag '{t}' not found in ls-remote output")

    tag_sha = chosen_line.split()[0]
    tag_type = "peeled" if peeled_line else "direct"
    ok(f"Tag '{t}' resolved ({tag_type}): {tag_sha[:8]}")

    if tag_sha != expected:
        fail(
            f"Tag '{t}' points at {tag_sha[:8]}, expected {expected[:8]}"
        )
    ok(f"Tag '{t}' points at {tag_sha[:8]} (matches origin/testing)")

    # gh release exists
    result = subprocess.run(
        ["gh", "release", "view", t, "--json", "url"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        fail(f"gh release view failed for '{t}'")
    release_data = json.loads(result.stdout)
    release_url = release_data.get("url", "")
    ok(f"GitHub release exists: {release_url}")

    # Branch and tree state
    result = run(["git", "branch", "--show-current"])
    branch = result.stdout.strip()
    if branch != "testing":
        fail(f"Expected branch 'testing', currently on '{branch}'")
    ok("On 'testing' branch")

    result = run(["git", "status", "--porcelain"])
    if result.stdout.strip():
        fail("Working tree is dirty")
    ok("Working tree is clean")

    result = run(["git", "rev-parse", "HEAD"])
    local_head = result.stdout.strip()
    if local_head != expected:
        fail(
            f"Local HEAD ({local_head[:8]}) differs from "
            f"origin/testing ({expected[:8]})"
        )
    ok(f"Local == origin/testing ({local_head[:8]})")

    print(f"\n  Version: {v}")
    print(f"  Tag: {t}")
    print(f"  Tagged commit: {expected}")
    print(f"  Release URL: {release_url}")
    print(f"  Branch: {branch} (clean, synced)")
    print("\nPost-verify passed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Release automation for the AI-snippets workspace",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # preflight
    pf = sub.add_parser("preflight", help="Validate repo state before release")
    pf.add_argument("--version", help="Proposed version (X.Y.Z or vX.Y.Z)")

    # changes
    ch = sub.add_parser("changes", help="Draft changelog notes")
    ch.add_argument("--base", help="Base tag to diff from (omit for first release)")
    ch.add_argument("--out", help="Output file path (default: stdout)")

    # check-version
    cv = sub.add_parser("check-version", help="Validate version format and ordering")
    cv.add_argument("--version", required=True, help="Version to check (X.Y.Z or vX.Y.Z)")

    # finalize
    fi = sub.add_parser("finalize", help="Tag release and create GitHub release")
    fi.add_argument("--version", required=True, help="Release version (X.Y.Z or vX.Y.Z)")
    fi.add_argument("--notes", required=True, help="Path to changelog notes file")
    fi.add_argument("--commit", help="Specific commit SHA to tag (default: HEAD of testing)")

    # post-verify
    pv = sub.add_parser("post-verify", help="Verify release was published correctly")
    pv.add_argument("--version", required=True, help="Version to verify (X.Y.Z or vX.Y.Z)")

    args = parser.parse_args()

    commands = {
        "preflight": cmd_preflight,
        "changes": cmd_changes,
        "check-version": cmd_check_version,
        "finalize": cmd_finalize,
        "post-verify": cmd_post_verify,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
