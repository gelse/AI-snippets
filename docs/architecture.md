# Architecture

This document covers the generation pipeline, install manifest, and installer mechanics for `@gelse/ai-snippets`.

## Source of Truth: modes.json

[`modes.json`](../modes.json) is the single source of truth for all mode definitions. It contains:

- `customModes` — array of mode objects, each with `slug`, `name`, `description`, `roleDefinition`, `whenToUse`, `customInstructions` (a repo-relative path `agents/<slug>.md` resolved at generation time), `groups`, `source`
- `skills` — array of skill objects, each with `name` and `file` (path to the runbook)

Agent instruction files live in `agents/<slug>.md` — one file per mode, no frontmatter, source-only content inlined verbatim at generation time.

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
    ├── output/opencode/     agents/*.md + skill/<name>.md
    ├── output/claude/       agents/*.md + skills/<name>/SKILL.md
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
| Skills | `output/zoo/skills/<name>.md` | `.roo/skills/<name>.md` (local) or `~/.roo/skills/<name>.md` (global) |

### Kilo Code

| Artifact | Emitted | Tool expects |
|----------|---------|-------------|
| Modes | `output/kilo/.kilocodemodes` | Project root as `.kilocodemodes` or `~/.config/kilo/agent/*.md` (global) |
| Skills | `output/kilo/skills/<name>.md` | `.kilo/skills/<name>.md` (local) or `~/.kilo/skills/<name>.md` (global) |

### OpenCode

OpenCode scans config directories for `{agent,agents}/**/*.md` and `{skill,skills}/**/SKILL.md` — both singular and plural directory names are accepted.

| Artifact | Emitted | Tool expects |
|----------|---------|-------------|
| Agents | `output/opencode/agents/*.md` | `.opencode/agents/*.md` (local) or `~/.config/opencode/agents/*.md` (global) |
| Skills | `output/opencode/skill/<name>.md` | `.opencode/skills/<name>.md` (local) or `~/.config/opencode/skills/<name>.md` (global) |

### Claude Code

| Artifact | Emitted | Tool expects |
|----------|---------|-------------|
| Agents | `output/claude/agents/*.md` | `.claude/agents/*.md` (local) or `~/.claude/agents/*.md` (global) |
| Skills | `output/claude/skills/<name>/SKILL.md` | `.claude/skills/<name>/SKILL.md` (local) or `~/.claude/skills/<name>/SKILL.md` (global) |

Directory-form skills ship companion files (scripts, configs) alongside the runbook in all tools.

## Installer Plan and Execution

The installer (`src/installer.ts`) follows a two-phase plan-execute pattern:

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

- YAML is parsed preserving comments, `---` separators, and sibling keys
- Modes with matching slugs are replaced
- Duplicates are removed
- Foreign (non-ai-snippets) modes are preserved
- New modes are appended
- Missing destination file → plain copy

The merge logic lives in `src/merge.ts`.
