# Architecture

This document covers the generation pipeline, install manifest, and installer mechanics for AI-Snippets.

## Source of Truth: modes.json

[`modes.json`](../modes.json) is the single source of truth for all mode definitions. It contains:

- `customModes` — array of mode objects, each with `slug`, `name`, `description`, `roleDefinition`, `whenToUse`, `customInstructions` (a repo-relative path `agents/<slug>.md` resolved at generation time), `instantiation` (one of `primary`, `subagent`, `all`; defaults to `all` in opencode frontmatter and controls whether the agent appears in opencode's TUI picker), `groups`, `source`
- `skills` — array of skill objects, each with `name` and `file` (path to the runbook)

Agent instruction files live in `agents/<slug>.md` — one file per mode, no frontmatter, source-only content inlined verbatim at generation time.

Each `agents/<slug>.md` is a minimal stub, not a full instruction file: it names the mode's `agent-<slug>` skill and lists the mode's tools.

The full runbook — workflow, dispatch contract, quality gates — lives in `skills/agent-<slug>.md`; at runtime the mode loads that skill via the `skill` tool instead of carrying its own instructions.

Skills support two layout forms:

| Form | `file` value | When to use |
|------|-------------|-------------|
| **Flat** | `skills/<name>.md` | Simple skills with just a runbook (e.g. `github-issue`) |
| **Directory** | `skills/<name>/SKILL.md` | Skills with companion files (scripts, configs) alongside the runbook (e.g. `release/`) |

Both forms emit identically to all tools. `scripts/verify.py` enforces that only one form exists per skill name and rejects duplicates or coexistence.

## Generation Pipeline

```
modes.json + agents/<slug>.md
    │
    ▼
scripts/generate.py <tool|manifest>
    │
    ├── output/zoo/          .roomodes + skills/<name>.md
    ├── output/kilo/         .kilocodemodes + skills/<name>.md
    ├── output/opencode/     agents/*.md + skill/<name>/SKILL.md
    └── output/install-manifest.json
```

Each tool subcommand emits the native format for that tool. `manifest` emits the install manifest that maps source artifacts to their destination paths per tool and scope.

## Install Manifest

`install-manifest.json` is a per-tool mapping of every artifact to its source and destination paths. The installer reads this manifest to know what to write and where.

Generated `output/` files are not committed — regenerate with `make all`.

## Per-Tool Emitted Formats

### Zoo Code

| Artifact | Emitted | Tool expects |
|----------|---------|-------------|
| Modes | `output/zoo/.roomodes` | Project root as `.roomodes` or merged into `~/.roo/custom_modes.yaml` |
| Skills | `output/zoo/skills/<name>.md` | CLI installer: `.roo/skills/<name>.md` (local) or `~/.roo/skills/<name>.md` (global). Makefile targets: `.roo/skills/<name>/SKILL.md` (local) or `~/.roo/skills/<name>/SKILL.md` (global) — each flat file is wrapped into a directory form so companion files ship alongside the runbook. |

### Kilo Code

| Artifact | Emitted | Tool expects |
|----------|---------|-------------|
| Modes | `output/kilo/.kilocodemodes` | Project root as `.kilocodemodes` or `~/.config/kilo/agent/*.md` (global) |
| Skills | `output/kilo/skills/<name>.md` | `.kilo/skills/<name>.md` (local) or `~/.kilo/skills/<name>.md` (global) |

### OpenCode

OpenCode scans config directories for `{agent,agents}/**/*.md` and `{skill,skills}/**/SKILL.md` — both singular and plural directory names are accepted.

The global config directory follows the XDG Base Directory specification: `$XDG_CONFIG_HOME/opencode/` if `XDG_CONFIG_HOME` is set, otherwise `~/.config/opencode/`. The `install-opencode-global` Makefile target respects this via the `OPENCODE_CONFIG_HOME` variable.

Generated agent `.md` files include YAML frontmatter with `mode: <instantiation>` (defaulting to `all`), which makes each agent available both as a subagent and in the primary TUI picker. Agents with `mode: subagent` are filtered out of the TUI picker by opencode. When a slug appears in [`models/mapping.yaml`](../models/mapping.yaml), a `model: litellm/<id>` field is inserted between `mode` and `permissions`; [`scripts/verify.py`](../scripts/verify.py) asserts the field is present, matches the mapping, and occupies that position.

| Artifact | Emitted | Tool expects |
|----------|---------|-------------|
| Agents | `output/opencode/agents/*.md` | `.opencode/agents/*.md` (local) or `$OPENCODE_CONFIG_HOME/opencode/agents/*.md` (global) |
| Skills | `output/opencode/skill/<name>/SKILL.md` | `.opencode/skills/<name>/SKILL.md` (local) or `$OPENCODE_CONFIG_HOME/opencode/skills/<name>/SKILL.md` (global) |

The skill emitter now writes this directory form directly — the flat-output bug is fixed in this release, so the emitted source matches what OpenCode discovers.

## Installer Plan and Execution

The installer (`scripts/install.py`) follows a two-phase plan-execute pattern:

1. **Plan phase:** Reads the manifest and destination filesystem. For each artifact, prints a plan with labels:
   - `[create]` — new file, no collision
   - `[update]` — existing file, content differs
   - `[merge]` — zoo global modes YAML merge
   - `[overwrite]` — existing file, `--yes` implied

2. **Execute phase:** Writes files with collision prompts:
   - `[o]verwrite / [s]kip / [a]bort` for each collision
   - Non-TTY (piped stdin): EOF or empty answer aborts with exit code 1
   - `--yes` flag skips prompts and overwrites

3. **Summary:** Prints counts — installed, skipped, merged, replaced, kept.

## Zoo Global Merge

When installing zoo globally, `~/.roo/custom_modes.yaml` is merged (not overwritten):

- YAML is parsed preserving sibling keys
- Modes with matching slugs are replaced
- Duplicates are removed
- Foreign (non-ai-snippets) modes are preserved
- New modes are appended
- Missing destination file → plain copy

Comments and `---` separators are not preserved: the merged file is re-emitted by `yaml.safe_dump` in block style. The merge logic lives in `scripts/merge-modes.py`.
