# Development

This document covers generation, verification, and release workflows for contributors.

## Makefile Targets

```bash
make help              # Show all available targets
```

### Verification and Linting

| Target | What it does |
|--------|-------------|
| `make check-py` | Validate `modes.json` (structural + round-trip fidelity) and lint `scripts/` and `skills/` with ruff |
| `make verify` | Alias of `check-py` (legacy name, Python-only) |

### Artifact Generation

| Target | What it does |
|--------|-------------|
| `make zoo` | Generate Zoo Code artifacts into `output/zoo/` |
| `make kilo` | Generate Kilo Code artifacts into `output/kilo/` |
| `make opencode` | Generate OpenCode artifacts into `output/opencode/` |
| `make manifest` | Generate `output/install-manifest.json` |
| `make all` | Generate all three tool artifact trees plus the install manifest |
| `make clean` | Remove `output/` |

### Legacy Zoo Install Targets

| Target | What it does |
|--------|-------------|
| `make install-zoo-local` | Install zoo skills and agents locally (project root) |
| `make install-zoo-local-skills` | Install zoo skills locally |
| `make install-zoo-local-agents` | Install zoo agents locally (`.roomodes`) |
| `make install-zoo-global` | Install zoo skills and agents globally (`~/.roo/` + Zoo Code globalStorage merge) |
| `make install-zoo-global-skills` | Install zoo skills globally |
| `make install-zoo-global-agents` | Install zoo agents globally — overwrites `~/.roo/custom_modes.yaml` and **merges** into Zoo Code globalStorage |

> ⚠️ **Overwrite warning:** `install-zoo-global-agents` **overwrites** `~/.roo/custom_modes.yaml` with the generated modes. Any existing global modes not present in the generated file will be lost. The CLI installer (`.venv/bin/python scripts/install.py install zoo --global`) **merges** instead — use it for production installs.
>
> **Zoo Code globalStorage:** If `~/.config/Code/User/globalStorage/zoocodeorganization.zoo-code/settings/` exists, the target also **merges** generated modes into `custom_modes.yaml` in that directory (matching slugs replaced, foreign entries kept, new slugs appended). If the directory is absent, a skip notice is printed and the target exits successfully. Override the destination with `make install-zoo-global-agents ZOO_GLOBALSTORAGE=/path/to/custom_modes.yaml`.

### OpenCode Install Targets

| Target | What it does |
|--------|-------------|
| `make install-opencode-global` | Install opencode agents and skills globally. Agents copy correctly to `$OPENCODE_CONFIG_HOME/opencode/agents/*.md` (the agent glob `output/opencode/agents/*.md` matches the generator output). Skills target `$OPENCODE_CONFIG_HOME/opencode/skills/<name>/SKILL.md`, but the skill copy step globs the flat `output/opencode/skill/*.md` path while the generator emits `output/opencode/skill/<name>/SKILL.md`, so the glob matches no files and the target copies no skills. `$OPENCODE_CONFIG_HOME` defaults to `$XDG_CONFIG_HOME` or `~/.config` (see the OpenCode section in [`docs/architecture.md`](../docs/architecture.md)). Use the CLI installer (`.venv/bin/python scripts/install.py install opencode --global`) for opencode skill installation. |

> The CLI installer (`.venv/bin/python scripts/install.py install opencode --global`) emits the same directory-form skills (`~/.config/opencode/skills/<name>/SKILL.md`) that OpenCode discovers.

## verify.py Checks

[`scripts/verify.py`](../scripts/verify.py) validates `modes.json`, performs a round-trip fidelity check, and verifies OpenCode agent frontmatter:

1. **Structural validation** — valid JSON, required top-level keys (`customModes`, `skills`), required mode keys (`slug`, `name`, `description`, `roleDefinition`, `whenToUse`, `customInstructions`, `groups`, `source`), unique slugs matching `^[a-z0-9-]+$`, `customInstructions` must be `agents/<slug>.md` referencing an existing non-empty file, skill file existence, and no duplicate skill names across flat/directory forms.
2. **Round-trip check** — resolves `agents/<slug>.md` references, generates zoo output, parses it back, and verifies mode data round-trips losslessly against the resolved file contents.
3. **OpenCode agent mode check** — generates opencode agent artifacts and asserts each agent's frontmatter contains `mode: all`. Agents with `mode: subagent` are invisible in opencode's TUI picker.
4. **OpenCode agent model check** — generates opencode agent artifacts to a temp dir, reads [`models/mapping.yaml`](../models/mapping.yaml), and asserts each agent with a mapping entry carries a `model: litellm/<id>` frontmatter field matching the mapping. The check also asserts field position: frontmatter keys must start with `description`, `mode`, then `model`, then `permission` (when present). Agents whose slug has no mapping entry legitimately carry no `model` field and are skipped.

## Smoke Tests

| Script | What it covers |
|--------|---------------|
| [`scripts/smoke-test.sh`](../scripts/smoke-test.sh) | Installer against temporary `$HOME` dirs — dry-run, real install, collision prompts, abort, piped stdin, `--yes` overwrite, EOF non-zero exit, and double-install merge idempotency (no duplicate slugs) |
| [`scripts/smoke-test-double-install.sh`](../scripts/smoke-test-double-install.sh) | Double-installs into a seeded `$HOME` and asserts no duplicate slugs, correct `replaced`/`kept` counts, foreign-mode order, repeat-install stability, and the empty-`customModes` edge case |

## Packaging and Release

Releases run through the [`release` skill](../skills/release/SKILL.md), whose helper [`skills/release/release.py`](../skills/release/release.py) automates preflight, version checks, tagging, and the GitHub release.
