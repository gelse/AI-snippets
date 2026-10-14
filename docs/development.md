# Development

This document covers generation, verification, and release workflows for contributors.

## Makefile Targets

```bash
make help              # Show all available targets
```

### Verification and Linting

| Target | What it does |
|--------|-------------|
| `make check-py` | Validate `modes.json` (structural + round-trip fidelity) and `harnesses.json` (schema), and lint `scripts/` and `skills/` with ruff |
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
| `make install-opencode-global` | Install opencode agents and skills globally. Agents copy to `$OPENCODE_CONFIG_HOME/opencode/agents/*.md`; skills copy to `$OPENCODE_CONFIG_HOME/opencode/skills/<name>/SKILL.md` in directory form, companion files alongside. `$OPENCODE_CONFIG_HOME` defaults to `$XDG_CONFIG_HOME` or `~/.config` (see the OpenCode section in [`docs/architecture.md`](../docs/architecture.md)). |

> The CLI installer (`.venv/bin/python scripts/install.py install opencode --global`) emits the same directory-form skills (`~/.config/opencode/skills/<name>/SKILL.md`) that OpenCode discovers.

## verify.py Checks

[`scripts/verify.py`](../scripts/verify.py) validates `modes.json` and `harnesses.json`, performs a round-trip fidelity check, and verifies OpenCode agent frontmatter and body composition:

1. **Structural validation** — valid JSON, required top-level keys (`customModes`, `skills`, `permissions`), required mode keys (`slug`, `name`, `description`, `roleDefinition`, `whenToUse`, `customInstructions`, `groups`, `source`), unique slugs matching `^[a-z0-9-]+$`, `customInstructions` must be `agents/<slug>.md` referencing an existing non-empty file, a `permissions` entry for every non-deprecated mode (exactly the keys `edit`, `shell`, `read`, `glob`, `grep`, `skill`, `task`, `lsp`, `question`, `external_directory`, `doom_loop`, keyed in that canonical row order, each value an `allow`/`ask`/`deny` effect or a non-empty pattern map of such effects — `plan`/`review-code` `shell` are per-command pattern maps, `question`/`doom_loop` are scalar-only as upstream `actionOnly` — and no `permissions` key naming a deprecated or unknown slug), skill file existence, and no duplicate skill names across flat/directory forms.
2. **harnesses.json schema check** — validates root-level `harnesses.json`: top-level keys exactly `zoo`/`kilo`/`opencode`, each value is a dict with exactly the key `subtaskInstructions`, value is a list of strings, zoo/kilo empty, opencode non-empty.
3. **Round-trip check** — resolves `agents/<slug>.md` references, generates zoo output, parses it back, and verifies mode data round-trips losslessly against the resolved file contents.
4. **OpenCode agent mode check** — generates opencode agent artifacts and asserts each agent's frontmatter contains `mode: <instantiation>` (defaulting to `all`), per `modes.json.instantiation`. Agents with `mode: subagent` are invisible in opencode's TUI picker.
5. **OpenCode agent model check** — generates opencode agent artifacts to a temp dir, reads [`models/mapping.yaml`](../models/mapping.yaml), and asserts each agent with a mapping entry carries a `model: litellm/<id>` frontmatter field matching the mapping. The check also asserts field position: frontmatter keys must start with `description`, `mode`, then `model`, then `permission` (the v1 map, always present). Agents whose slug has no mapping entry legitimately carry no `model` field and are skipped.
6. **OpenCode agent permissions check** — generates opencode agent artifacts to a temp dir and asserts each agent's `permission` frontmatter is the v1 permission map — action name to effect, or action name to per-command pattern map — with exactly the keys `edit`, `bash`, `read`, `glob`, `grep`, `skill`, `task`, `lsp`, `question`, `external_directory`, `doom_loop` (`modes.json` vocabulary `shell`/`task` emitted under the runtime names `bash`/`task`). Values are `allow`/`ask`/`deny` effects or non-empty pattern maps of such effects; `question` and `doom_loop` are upstream `actionOnly` and accept scalar effects only (`translate_opencode_permissions` raises `TypeError` on a map there); the inert v2 `permissions` list is rejected. The emitted map must equal the translation of the mode's `modes.json.permissions` row through `translate_opencode_permissions` (round-trip), and the last-match-wins semantics must hold: `edit: allow` with a `fileRegex`-scoped group emits `{'*': 'deny', '*.md': 'allow'}` (broad deny first, scoped allow second); `edit: deny`/`ask` or no scoped group emits the scalar effect; `shell` pattern maps pass through in author order (broad `*` deny first, scoped allows after). The human-readable verdict over all agents lives in [`docs/opencode-target-drift.md`](../docs/opencode-target-drift.md).
7. **OpenCode subtask-block check** — regenerates opencode agents to a temp dir and asserts every emitted `output/opencode/agents/<slug>.md` body contains a `## Starting Subtasks` heading whose paragraph text exactly equals `"\n\n".join(harnesses.json["opencode"].subtaskInstructions)` (round-trip from the config), positioned between the role line and the resolved `agents/<slug>.md` stub instructions.

## Smoke Tests

| Script | What it covers |
|--------|---------------|
| [`scripts/smoke-test.sh`](../scripts/smoke-test.sh) | Installer against temporary `$HOME` dirs — dry-run, real install, collision prompts, abort, piped stdin, `--yes` overwrite, EOF non-zero exit, and double-install merge idempotency (no duplicate slugs) |
| [`scripts/smoke-test-double-install.sh`](../scripts/smoke-test-double-install.sh) | Double-installs into a seeded `$HOME` and asserts no duplicate slugs, correct `replaced`/`kept` counts, foreign-mode order, repeat-install stability, and the empty-`customModes` edge case |
| [`scripts/smoke-test-opencode-install.sh`](../scripts/smoke-test-opencode-install.sh) | `make opencode` + `make install-opencode-global` into an isolated `$OPENCODE_CONFIG_HOME` — asserts no `cp` errors, agents under `opencode/agents/`, every generated skill as `opencode/skills/<name>/SKILL.md` with companion side files alongside, and every installed agent carrying a v1 `permission` map with at least one `allow` effect, the four new actions (`lsp`, `question`, `external_directory`, `doom_loop`) present and well-formed, and no inert v2 `permissions` list (skipped when the repo venv is absent) |

## Packaging and Release

Releases run through the [`release` skill](../skills/release/SKILL.md), whose helper [`skills/release/release.py`](../skills/release/release.py) automates preflight, version checks, tagging, and the GitHub release.
