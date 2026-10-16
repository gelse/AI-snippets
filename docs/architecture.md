# Architecture

This document covers the generation pipeline, install manifest, and installer mechanics for AI-Snippets.

## Source of Truth: modes.json

[`modes.json`](../modes.json) is the single source of truth for all mode definitions. It contains:

- `customModes` — array of mode objects, each with `slug`, `name`, `description`, `roleDefinition`, `whenToUse`, `customInstructions` (a repo-relative path `agents/<slug>.md` resolved at generation time), `instantiation` (one of `primary`, `subagent`, `all`; defaults to `all` in opencode frontmatter and controls whether the agent appears in opencode's TUI picker), `groups`, `source`
- `permissions` — per-mode permission matrix keyed by slug: 11 keys per row (`edit`, `shell`, `read`, `glob`, `grep`, `skill`, `task`, `lsp`, `question`, `external_directory`, `doom_loop`), each an `allow`/`ask`/`deny` effect or a per-command pattern map (`plan`/`review-code` `shell`); `shell` also accepts the scalar `auto`, which [`scripts/generate.py`](../scripts/generate.py) expands at emit time into a safe-command pattern map (see the OpenCode section below); `question`/`doom_loop` are scalar-only (upstream `actionOnly`)
- `skills` — array of skill objects, each with `name` and `file` (path to the runbook)

Agent instruction files live in `agents/<slug>.md` — one file per mode, no frontmatter, source-only content inlined verbatim at generation time.

Each `agents/<slug>.md` is a minimal stub, not a full instruction file: it names the mode's `agent-<slug>` skill and lists the mode's tools.

The full runbook — workflow, dispatch contract, quality gates — lives in `skills/agent-<slug>.md`; at runtime the mode loads that skill via the `skill` tool instead of carrying its own instructions.

Skills support two layout forms:

| Form          | `file` value             | When to use                                                                            |
| ------------- | ------------------------ | -------------------------------------------------------------------------------------- |
| **Flat**      | `skills/<name>.md`       | Simple skills with just a runbook (e.g. `github-issue`)                                |
| **Directory** | `skills/<name>/SKILL.md` | Skills with companion files (scripts, configs) alongside the runbook (e.g. `release/`) |

Both forms emit identically to all tools. `scripts/verify.py` enforces that only one form exists per skill name and rejects duplicates or coexistence.

## Source of Truth: harnesses.json

[`harnesses.json`](../harnesses.json) is a second build-time source, parallel to `modes.json`: it carries per-harness configuration of prose blocks injected into emitted agent bodies. Today only `opencode` carries content — a `## Starting Subtasks` section telling every emitted opencode agent to use the `task` tool for subtasks; `zoo` and `kilo` are present-and-empty. The schema is exactly three top-level keys (`zoo`, `kilo`, `opencode`), each a dict with the key `subtaskInstructions` (a list of instruction strings).

## Generation Pipeline

```
modes.json + agents/<slug>.md + models/mapping.yaml (+ harnesses.json for opencode)
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

| Artifact | Emitted                       | Tool expects                                                                                                                                                                                                                                                                               |
| -------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Modes    | `output/zoo/.roomodes`        | Project root as `.roomodes` or merged into `~/.roo/custom_modes.yaml`                                                                                                                                                                                                                      |
| Skills   | `output/zoo/skills/<name>.md` | CLI installer: `.roo/skills/<name>.md` (local) or `~/.roo/skills/<name>.md` (global). Makefile targets: `.roo/skills/<name>/SKILL.md` (local) or `~/.roo/skills/<name>/SKILL.md` (global) — each flat file is wrapped into a directory form so companion files ship alongside the runbook. |

### Kilo Code

| Artifact | Emitted                        | Tool expects                                                             |
| -------- | ------------------------------ | ------------------------------------------------------------------------ |
| Modes    | `output/kilo/.kilocodemodes`   | Project root as `.kilocodemodes` or `~/.config/kilo/agent/*.md` (global) |
| Skills   | `output/kilo/skills/<name>.md` | `.kilo/skills/<name>.md` (local) or `~/.kilo/skills/<name>.md` (global)  |

### OpenCode

OpenCode scans config directories for `{agent,agents}/**/*.md` and `{skill,skills}/**/SKILL.md` — both singular and plural directory names are accepted.

The global config directory follows the XDG Base Directory specification: `$XDG_CONFIG_HOME/opencode/` if `XDG_CONFIG_HOME` is set, otherwise `~/.config/opencode/`. The `install-opencode-global` Makefile target respects this via the `OPENCODE_CONFIG_HOME` variable.

Generated agent `.md` files include YAML frontmatter with `mode: <instantiation>` (defaulting to `all`), which makes each agent available both as a subagent and in the primary TUI picker. Agents with `mode: subagent` are filtered out of the TUI picker by opencode. When a slug appears in [`models/mapping.yaml`](../models/mapping.yaml), a `model: litellm/<id>` field is inserted between `mode` and `permission`. The frontmatter's `permission` field is the opencode v1 permission map translated from the mode's `modes.json.permissions` row — 11 keys (`edit`, `bash`, `read`, `glob`, `grep`, `skill`, `task`, `lsp`, `question`, `external_directory`, `doom_loop`), each an `allow`/`ask`/`deny` effect or a per-command pattern map — with `shell`/`task` emitted under the runtime names `bash`/`task`; [`scripts/verify.py`](../scripts/verify.py) asserts the model field is present, matches the mapping, and occupies that position, and checks the permission map's shape and translation fidelity.

When a mode's `shell` value is the scalar `auto` (valid for `shell` only — the translator raises `ValueError` on `auto` anywhere else), the emitter expands it into a `bash` pattern map: a catch-all `'*'` gate first (`ask` when the mode's `instantiation` is `primary`, `deny` for every other instantiation, since those run headless as subagents), then `allow` patterns for the read-only command list — bare `cmd` and `cmd *` per command — so read-only commands run without friction while everything else hits the gate. Entry order is the last-match-wins policy, exactly like hand-written `shell` pattern maps. The command list (`SAFE_SHELL_COMMANDS` in [`scripts/generate.py`](../scripts/generate.py)) is copied from [`scripts/reference/approve_readonly_bash.py`](../scripts/reference/approve_readonly_bash.py), a vendored upstream hook kept for reference only and not used directly; upstream's deny lists (`DESTRUCTIVE_COMMANDS`, `WRAPPER_COMMANDS`, `DANGEROUS_PATTERNS`) are deliberately not implemented because their commands are absent from the allow list and so fall through to the catch-all gate.

Every emitted agent body also carries a `## Starting Subtasks` block, read from `harnesses.json["opencode"].subtaskInstructions` (list items joined with a blank line). The block sits between the role line and the resolved `agents/<slug>.md` stub instructions; `scripts/verify.py` asserts the heading, the exact paragraph text, and the position on every regenerated agent.

| Artifact | Emitted                                 | Tool expects                                                                                                   |
| -------- | --------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Agents   | `output/opencode/agents/*.md`           | `.opencode/agents/*.md` (local) or `$OPENCODE_CONFIG_HOME/opencode/agents/*.md` (global)                       |
| Skills   | `output/opencode/skill/<name>/SKILL.md` | `.opencode/skills/<name>/SKILL.md` (local) or `$OPENCODE_CONFIG_HOME/opencode/skills/<name>/SKILL.md` (global) |

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
