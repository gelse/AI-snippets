#!/usr/bin/env python3
# REFERENCE ONLY — THIS FILE IS NOT USED DIRECTLY.
#
# Vendored verbatim from https://gist.githubusercontent.com/thuwyh/c1968ddd36bd8ea68f134be04570d371/raw/77a75f82af2d2513db2582a6593fc249644a1871/approve_readonly_bash.py
# (a Claude Code PreToolUse hook). Nothing in this repository imports or
# executes it. The only thing consumed from it is the SAFE_COMMANDS list,
# copied into scripts/generate.py, which expands the modes.json shell
# permission "auto" into a per-command allow list at generate time.
# Kept here for provenance and for the richer deny-first / flag-level logic
# (DANGEROUS_PATTERNS, WRAPPER_COMMANDS, DESTRUCTIVE_COMMANDS,
# DESTRUCTIVE_FLAGS, GIT_WRITE_SUBCMDS) in case the emitted pattern-map
# format ever grows expressive enough to model it. Upstream's deny lists are
# intentionally not implemented: those commands are absent from
# SAFE_COMMANDS, so they fall through to the "auto" catch-all effect
# ("ask" for primary modes, "deny" for all others).
"""Claude Code PreToolUse hook: auto-approve read-only Bash commands.

Deny-first, then allowlist. Unknown commands fall through to user prompt.
Returns JSON with permissionDecision and reason for better diagnostics.
"""
import json
import re
import sys

# ── Deny-first: dangerous patterns that must NEVER be auto-approved ──────────

DANGEROUS_PATTERNS = [
    r":\(\)\s*\{.*\|.*&\s*\}\s*;",    # fork bomb
    r"\|\s*(ba)?sh\b",                  # pipe-to-shell: curl x | sh
    r"\|\s*bash\b",                     # pipe-to-bash
    r"\|\s*zsh\b",                      # pipe-to-zsh
    r"\|\s*python[23]?\b",             # pipe-to-python
    r"\|\s*perl\b",                     # pipe-to-perl
    r"\|\s*ruby\b",                     # pipe-to-ruby
    r"\|\s*node\b",                     # pipe-to-node
    r"`[^`]+`",                         # backtick command substitution
    r"\$\([^)]+\)",                     # $(...) command substitution
]

# Commands that can wrap/execute other commands — never auto-approve
WRAPPER_COMMANDS = {
    "sudo", "su", "doas",
    "eval", "exec", "source", ".",
    "xargs",   # xargs rm -rf
    "nohup",
    "bash", "sh", "zsh", "fish",       # explicit shell invocation
    "python", "python3", "node",        # can run arbitrary code
    "ruby", "perl", "php",
    "ssh",                              # remote execution
}

# Commands that modify files/state — never auto-approve
DESTRUCTIVE_COMMANDS = {
    "rm", "rmdir", "shred", "unlink",
    "mv", "cp",
    "chmod", "chown", "chgrp",
    "mkdir", "mkfifo", "mknod", "touch",
    "ln",
    "kill", "killall", "pkill",
    "dd", "mkfs", "fsck",
    "shutdown", "reboot", "halt",
    "mount", "umount",
    "launchctl",
    "systemctl", "service",
    "tee",                              # writes to files
    "install",                          # copies + sets permissions
    "patch",                            # modifies files
    "truncate", "fallocate",
    "chflags", "xattr",
    "ditto", "rsync", "scp",
    "tar",                              # can extract/overwrite
    "unzip", "zip", "gzip", "gunzip",  # can modify files
    "pbcopy",                           # modifies clipboard
    "write",
}

# ── Allowlist: read-only commands ────────────────────────────────────────────

SAFE_COMMANDS = {
    # Display
    "echo", "printf", "cat", "head", "tail", "less", "more", "bat",
    # File info (read-only)
    "ls", "find", "file", "stat", "du", "df", "wc", "tree",
    "realpath", "dirname", "basename", "readlink", "pwd",
    "md5", "shasum", "sha256sum", "md5sum", "cksum",
    # Text processing (read-only when no -i flag)
    "grep", "egrep", "fgrep", "rg", "ag", "ack",
    "awk", "gawk", "sed", "gsed",
    "sort", "uniq", "cut", "tr", "rev", "fold",
    "column", "paste", "join", "comm", "diff", "cmp",
    "jq", "yq", "xmllint", "fmt",
    # Git (subcommand checked separately)
    "git",
    # Network diagnostics (read-only)
    "ifconfig", "netstat", "ss", "route",
    "dig", "nslookup", "host", "ping", "traceroute", "mtr",
    "curl",
    # System info
    "ps", "pgrep", "top", "htop", "who", "whoami", "w", "id", "groups",
    "uname", "hostname", "uptime", "date", "cal",
    "printenv", "locale",
    "which", "where", "type", "command",
    "sw_vers", "system_profiler", "sysctl", "vm_stat", "iostat",
    "lsof", "nettop", "arch", "getconf", "ulimit",
    # macOS (read-only; commands with write modes checked separately)
    "pbpaste", "plutil", "mdls", "mdfind", "dscacheutil",
    "klist", "log", "ioreg",
    "open",     # opens files/URLs, non-destructive
    "scutil",   # --dns/--proxy safe; --set blocked by flag check
    "defaults", # read safe; write/delete blocked by flag check
    "networksetup",  # list* safe; set* blocked by flag check
    # Navigation
    "cd",
    # Shell builtins (safe)
    "test", "[", "true", "false", "time",
    # Version / help
    "man", "info", "help",
}

# ── Git: write subcommands ───────────────────────────────────────────────────

GIT_WRITE_SUBCMDS = {
    "push", "commit", "merge", "rebase", "reset",
    "checkout", "switch", "restore", "clean",
    "rm", "mv", "add", "cherry-pick", "revert",
    "tag", "stash", "pull", "clone", "init",
    "submodule", "bisect", "apply", "am",
}

# ── Per-command destructive flags ────────────────────────────────────────────

DESTRUCTIVE_FLAGS = {
    "sed":  {"-i"},
    "gsed": {"-i"},
    "curl": {"-X", "--request", "-d", "--data", "--data-raw",
             "--data-binary", "-F", "--form", "-T", "--upload-file",
             "-o", "--output"},
    "scutil":       {"--set"},
    "defaults":     {"write", "delete", "rename", "import"},
    "networksetup": {"-setdnsservers", "-setwebproxy", "-setsearchdomains",
                     "-setftpproxy", "-setsocksfirewallproxy",
                     "-setairportpower", "-setv4off", "-setv6off",
                     "-setnetworkserviceenabled", "-ordernetworkservices",
                     "-setmanual", "-setdhcp", "-setbootp", "-setpppoepassword"},
}

# ─────────────────────────────────────────────────────────────────────────────


def respond(decision, reason=""):
    """Output JSON response for Claude Code hook."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))


def has_dangerous_pattern(command):
    """Check for patterns that must always be blocked."""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command):
            return True
    return False


def has_write_redirect(command):
    """Detect output redirection, ignoring safe stderr redirects."""
    c = re.sub(r"2>\s*/dev/null", "", command)
    c = re.sub(r"&>\s*/dev/null", "", c)
    c = re.sub(r"2>&\d", "", c)
    return ">" in c


def extract_cmd(part):
    """Extract command name and args, skipping env var assignments."""
    tokens = part.split()
    if not tokens:
        return None, []
    idx = 0
    for i, t in enumerate(tokens):
        if re.match(r'^[A-Za-z_]\w*=', t):
            idx = i + 1
        else:
            break
    if idx >= len(tokens):
        return None, []
    cmd = tokens[idx].split("/")[-1]
    return cmd, tokens[idx + 1:]


def git_is_safe(args):
    """Check git subcommand is read-only."""
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ("-C", "-c", "--git-dir", "--work-tree"):
            skip = True
            continue
        if a.startswith("-"):
            continue
        return a not in GIT_WRITE_SUBCMDS
    return True


def has_destructive_flag(cmd, args):
    """Check if a safe command has flags that make it destructive."""
    if cmd not in DESTRUCTIVE_FLAGS:
        return False
    bad = DESTRUCTIVE_FLAGS[cmd]
    for a in args:
        if a in bad:
            return True
        # Handle combined flags like -iE for sed
        if cmd in ("sed", "gsed") and a.startswith("-") and "i" in a:
            return True
    return False


def is_readonly(command):
    """Determine if a command is safe to auto-approve.

    Returns: (bool, str) - (is_safe, reason)
    """
    # Phase 1: Deny-first — check for universally dangerous patterns
    if has_dangerous_pattern(command):
        return False, "dangerous pattern detected"

    # Phase 2: Check for output redirection
    if has_write_redirect(command):
        return False, "output redirection detected"

    # Phase 3: Split into segments and check each one
    # Split by &&, ||, ;  (pipe | is handled separately below)
    chain_parts = re.split(r"\s*(?:&&|\|\||;)\s*", command)

    for chain in chain_parts:
        chain = chain.strip()
        if not chain:
            continue

        # Split pipes within this chain segment
        pipe_parts = re.split(r"\s*\|\s*", chain)

        for part in pipe_parts:
            part = part.strip().strip("()")
            if not part:
                continue

            cmd, args = extract_cmd(part)
            if cmd is None:
                continue

            # Check deny lists first
            if cmd in WRAPPER_COMMANDS:
                return False, f"wrapper/exec command: {cmd}"
            if cmd in DESTRUCTIVE_COMMANDS:
                return False, f"destructive command: {cmd}"

            # Check allowlist
            if cmd not in SAFE_COMMANDS:
                return False, f"unknown command: {cmd}"

            # Git subcommand check
            if cmd == "git" and not git_is_safe(args):
                return False, "git write subcommand"

            # Per-command destructive flags
            if has_destructive_flag(cmd, args):
                return False, f"destructive flag on {cmd}"

    return True, "all commands are read-only"


def main():
    try:
        data = json.load(sys.stdin)
        command = data.get("tool_input", {}).get("command", "")
        if not command:
            return

        safe, reason = is_readonly(command)
        if safe:
            respond("allow", reason)
        # If not safe, output nothing — fall through to normal permission prompt
    except Exception:
        pass  # On error, fall through silently


if __name__ == "__main__":
    main()
