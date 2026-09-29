# Development

This document covers build, test, and packaging workflows for contributors.

## Makefile Targets

```bash
make help              # Show all available targets
```

### Verification and Linting

| Target | What it does |
|--------|-------------|
| `make check-py` | Validate `modes.json` (structural + round-trip fidelity) and lint `scripts/` and `skills/` with ruff — Python-only, no node required |
| `make verify` | Run `check-py`, then when both `node` and `npm` are on PATH: `tsc --noEmit`, `npm run build`, and a zoo dry-run install; otherwise print `SKIP: node not available` |

### Artifact Generation

| Target | What it does |
|--------|-------------|
| `make zoo` | Generate Zoo Code artifacts into `output/zoo/` |
| `make kilo` | Generate Kilo Code artifacts into `output/kilo/` |
| `make opencode` | Generate OpenCode artifacts into `output/opencode/` |
| `make claude` | Generate Claude Code artifacts into `output/claude/` |
| `make manifest` | Generate `output/install-manifest.json` |
| `make all` | Generate all four tool artifact trees plus the install manifest |
| `make clean` | Remove `output/` |

### npm Packaging

| Target | What it does |
|--------|-------------|
| `make package-npx` | Build and pack the npm package (generates artifacts, builds TS, copies `release.js` into embedded tool trees, produces tarball in `dist/`) |
| `make package-npx-zoo` | Smoke-test: install zoo via the built package |
| `make package-npx-kilo` | Smoke-test: install kilo via the built package |
| `make package-npx-opencode` | Smoke-test: install opencode via the built package |
| `make package-npx-claude` | Smoke-test: install claude via the built package |

### Legacy Zoo Install Targets

| Target | What it does |
|--------|-------------|
| `make install-zoo-local` | Install zoo skills and agents locally (project root) |
| `make install-zoo-local-skills` | Install zoo skills locally |
| `make install-zoo-local-agents` | Install zoo agents locally (`.roomodes`) |
| `make install-zoo-global` | Install zoo skills and agents globally (`~/.roo/` + Zoo Code globalStorage merge) |
| `make install-zoo-global-skills` | Install zoo skills globally |
| `make install-zoo-global-agents` | Install zoo agents globally — overwrites `~/.roo/custom_modes.yaml` and **merges** into Zoo Code globalStorage |

> ⚠️ **Overwrite warning:** `install-zoo-global-agents` **overwrites** `~/.roo/custom_modes.yaml` with the generated modes. Any existing global modes not present in the generated file will be lost. The CLI installer (`npx @gelse/ai-snippets install zoo --global`) **merges** instead — use it for production installs.
>
> **Zoo Code globalStorage:** If `~/.config/Code/User/globalStorage/zoocodeorganization.zoo-code/settings/` exists, the target also **merges** generated modes into `custom_modes.yaml` in that directory (matching slugs replaced, foreign entries kept, new slugs appended). If the directory is absent, a skip notice is printed and the target exits successfully. Override the destination with `make install-zoo-global-agents ZOO_GLOBALSTORAGE=/path/to/custom_modes.yaml`.

### OpenCode Install Targets

| Target | What it does |
|--------|-------------|
| `make install-opencode-global` | Install opencode agents and skills globally — agents to `~/.config/opencode/agents/*.md`, skills to `~/.config/opencode/skills/<name>/SKILL.md` (directory-form skills ship companion files alongside `SKILL.md`) |

> The CLI installer (`npx @gelse/ai-snippets install opencode --global`) writes skills as flat `~/.config/opencode/skills/<name>.md` files, which OpenCode does not discover — its skill pattern is `{skill,skills}/**/SKILL.md`, so skills must live in a per-name directory as `SKILL.md`. Use `make install-opencode-global` or move the emitted files accordingly.

## verify.py Checks

[`scripts/verify.py`](../scripts/verify.py) validates `modes.json`, performs a round-trip fidelity check, and verifies OpenCode agent frontmatter:

1. **Structural validation** — valid JSON, required top-level keys (`customModes`, `skills`), required mode keys (`slug`, `name`, `description`, `roleDefinition`, `whenToUse`, `customInstructions`, `groups`, `source`), unique slugs matching `^[a-z0-9-]+$`, `customInstructions` must be `agents/<slug>.md` referencing an existing non-empty file, skill file existence, and no duplicate skill names across flat/directory forms.
2. **Round-trip check** — resolves `agents/<slug>.md` references, generates zoo output, parses it back, and verifies mode data round-trips losslessly against the resolved file contents.
3. **OpenCode agent mode check** — generates opencode agent artifacts and asserts each agent's frontmatter contains `mode: all`. Agents with `mode: subagent` are invisible in opencode's TUI picker.

## Smoke Tests

| Script | What it covers |
|--------|---------------|
| [`scripts/smoke-test.sh`](../scripts/smoke-test.sh) | Installer against temporary `$HOME` dirs — dry-run, real install, collision prompts, abort, piped stdin, `--yes` overwrite, EOF non-zero exit, and double-install merge idempotency (no duplicate slugs) |
| [`scripts/smoke-test-double-install.sh`](../scripts/smoke-test-double-install.sh) | Double-installs into a seeded `$HOME` and asserts no duplicate slugs, correct `replaced`/`kept` counts, foreign-mode order, repeat-install stability, and the empty-`customModes` edge case |

## Build

The npm package is built with [tsup](https://tsup.egoist.dev/) and bundled into `dist/`.

```bash
npm install
npm run build   # stages skills-embedded/ from output/, then bundles dist/cli.cjs + dist/release.js
```

The prebuild step ([`scripts/stage-embedded.mjs`](../scripts/stage-embedded.mjs)) copies `output/` into `skills-embedded/`, which tsup bundles into the published package. You need `make all` to generate `output/` before `npm run build` will succeed.

`npm run build` produces:
- `dist/cli.cjs` — CommonJS entry point for the `ai-snippets` bin
- `dist/release.js` — ESM module for the release skill helper

## Packaging and Release

1. **Build:** `make package-npx` generates all artifacts, builds TypeScript, copies `release.js` into each embedded tool tree, and produces a tarball in `dist/`.
2. **Verify version:** `node -p "require('./package.json').version"` must match the tag.
3. **Tag and push:** `git tag vX.Y.Z && git push origin vX.Y.Z` triggers the CI publish workflow.
4. **OIDC publishing:** The workflow uses npm trusted publishing — no access token secret required. See [npm-trusted-publishing.md](npm-trusted-publishing.md) for the one-time setup.
