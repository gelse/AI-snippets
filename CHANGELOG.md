# Changelog

## [Unreleased]

## [0.3.0] - 2026-10-02

### Fixed
- [`docs/development.md`](docs/development.md) CLI-installer note states the CLI emits directory-form skills that OpenCode discovers; the [`scripts/smoke-test.sh`](scripts/smoke-test.sh) post-overwrite assertion comment references the generated `output/` tree.
- OpenCode skill emitter dir form: [`generate.py`](scripts/generate.py) emitted flat `output/opencode/skill/<name>.md` files — a latent pre-existing bug, since OpenCode only discovers `{skill,skills}/**/SKILL.md` and silently ignored the flat output. Skills are now written as `output/opencode/skill/<name>/SKILL.md` (frontmatter and body unchanged), matching what OpenCode discovers.

### Changed
- Agent/skill refactor: each active mode's `agents/<slug>.md` instruction file is reduced to a stub that names its `agent-<slug>` runbook skill, and ten new `skills/agent-<slug>.md` skills carry the full workflows; `modes.json` wires the two together. [`docs/architecture.md`](docs/architecture.md) documents the stub/runbook split and the opencode dir-form emitter, [`docs/lieutenant-workflow.md`](docs/lieutenant-workflow.md) documents the dispatch header and the ten mode runbooks, and [`README.md`](README.md) reflects the new counts and layout.
- Dispatch contract: the `target-agent` / `target-agent-skill` header every `new_task` dispatch must carry is specified in the matching runbook skills — [`skills/agent-captain.md`](skills/agent-captain.md) and [`skills/agent-lieutenant.md`](skills/agent-lieutenant.md).

### Added
- `scripts/install.py` — Python installer mirroring the deleted TS CLI: plan-then-execute, collision prompts `[o]verwrite/[s]kip/[a]bort` (files and directories), `--yes`/`--dry-run`, `--global|--local`, `--skills-only|--agents-only`, interactive wizard, summary lines (`INSTALL SUMMARY` / `DRY RUN SUMMARY (no files were written)`, `Installed/updated:`, `Skipped:`, `Merged:`, `Replaced slugs:`, `Kept user slugs:`, `Nothing to install.`), and the non-TTY stdin contract. Reads `output/install-manifest.json` (emit via `make manifest` / `make all`).
- `scripts/merge-modes.py` minimal refactor — extract importable `merge(gen_path, dest_path) -> tuple[list[str], list[str], list[str]]` returning replaced/kept/added slug lists; `main()` is now a thin wrapper that keeps the existing CLI output and exit behavior byte-identical so the Makefile subprocess call still works.
- `scripts/smoke-test.sh` and `scripts/smoke-test-double-install.sh` rewritten to invoke the Python installer via `.venv/bin/python`; `count_slugs_yaml()` swapped for a PyYAML one-liner.
- `Dockerfile` and `docker-compose.yml` for running the generators on hosts without Python 3.11. Base image `python:3.11-slim`, in-image venv at `/opt/venv` (avoids host venv shadowing under the compose bind mount), `make` available, `pyyaml`+`ruff` pre-installed. Default compose service bind-mounts host `./output` so generated artifacts persist on the host.
- Claude Code is documented in [`README.md`](README.md) as a research-phase target that is not officially supported; the install manifest does not list it as an installable tool.

### Removed
- npm publishing: the `npm-publish` GitHub Actions workflow (`.github/workflows/npm-publish.yml`) and `docs/npm-trusted-publishing.md` are removed, along with the release skill's Publish phase — `release.py finalize` (GitHub release + tag on `main`) is now the sole release automation.
- npm packaging + npx install path: `package.json`, `package-lock.json`, `tsconfig.json`, `tsup.config.ts`, the `src/` TypeScript sources, `scripts/stage-embedded.mjs`, `skills/release/release.ts`, `skills/release/tsconfig.json`, and the Makefile `NODE`/`NPM`/`NPM_STAMP` variables, `check-node`, and `package-npx*` targets. The `skills-embedded/` staging tree and `.npm-stamp` are gone. `make verify` is now a thin alias of `make check-py`.

## [0.2.0] - 2026-09-29

### Fixed
- Duplicate entries when re-installing zoo global modes: [`mergeModesYaml()`](src/merge.ts) replaced the stale-index `existingSlugs` splice with a single-pass `filter()` by slug, so repeated installs no longer duplicate generated slugs and pre-existing duplicates are cleaned up.
- OpenCode skills documentation: [`docs/architecture.md`](docs/architecture.md) and [`README.md`](README.md) claimed OpenCode expects flat `skills/<name>.md` files. OpenCode's skill discovery only matches `{skill,skills}/**/SKILL.md` (per-name directory containing `SKILL.md`), so the documented destination now reflects the directory form.
- `make install-opencode-global` now honors `XDG_CONFIG_HOME` instead of assuming `~/.config`.

### Added
- `make install-opencode-global` (new) installs agents and skills globally in the layout OpenCode discovers (`~/.config/opencode/skills/<name>/SKILL.md`); note the CLI installer still emits flat skills, which OpenCode ignores.
- `scripts/smoke-test-double-install.sh` — double-install regression test asserting 14 slugs (13 generated + 1 foreign), no duplicates, correct `replaced`/`kept`, preserved foreign order, repeat-install stability, and the empty-`customModes` edge case.
- Step 7 in `scripts/smoke-test.sh` — inline merge-idempotency gate: double install into a seeded `$HOME` must yield 14 unique slugs with the foreign mode kept and never listed as replaced.
- `install-manifest.json` emitter in [`generate.py`](scripts/generate.py) and a `manifest` Makefile target (included in `all`) — writes `output/install-manifest.json` declaring each tool's artifact source paths and local/global destinations for the installer CLI.
- `check-node` Makefile guard that prints a clear failure message when Node.js is not installed.
- Makefile `package-npx` target: generates all tool artifacts, builds the TypeScript package, copies `dist/release.js` into `skills-embedded/`, and produces a tarball in `dist/`.
- Makefile `package-npx-zoo`, `package-npx-kilo`, `package-npx-opencode`, `package-npx-claude` smoke-test targets that run a real install via the built package.
- `make verify` now includes a node-optional block: when both `node` and `npm` are available, it runs `tsc --noEmit`, `npm run build`, and a dry-run install; otherwise prints `SKIP: node not available`.
- `captain` mode — classification and supervision entry point that routes work to the appropriate mode and skill; the default entry point, referenced by the `lieutenant` agent.
- Five task-type skills — `full-feature`, `small-feature`, `bugfix`, `architecture`, and `implementation-from-milestone` — workflow playbooks dispatched from `captain`.
- `documentation` skill for human-facing prose deliverables (documentation, READMEs, release notes, specs).
- `models/mapping.yaml` model mapping (v0.1) with generator support: OpenCode agents emit their mapped `model` and a `mode` field derived from the mode's `instantiation` value (defaulting to `all`).
- `docs/opencode-target-drift.md` — drift report comparing generated OpenCode targets against the installed baseline, with a clarified verdict format and corrected comparison baseline.

### Removed
- Legacy Makefile JS-only targets: `verify-js`, `zoo-js`, `kilo-js`, `opencode-js`, `claude-js`, `all-js`.
- `scripts/package.json` and `scripts/package-lock.json` — npm dependencies are now managed at the repo root.
- Legacy dual-stack JS scripts: `scripts/generate.mjs` and `scripts/verify.mjs` — Python equivalents (`generate.py`, `verify.py`) are the sole generators.

### Changed
- Mode instructions moved from embedded strings in `modes.json` to `agents/<slug>.md` files; generated output unchanged.
- README updated to Node-only documentation: removed dual-stack (JS/Python) prose, added `npx @gelse/ai-snippets install` usage section, updated workspace tree listing to reflect `src/`, root `package.json`, and `tsup.config.ts`.
- The `orchestrator` mode is deprecated in favour of the new `lieutenant` mode, which fills the same role (skill-driven workflow dispatch from `captain`). `orchestrator` now behaves as a gatekeeper that aborts and directs users to `lieutenant`. The OpenCode and Claude outputs omit deprecated modes, so their installed agent count is unchanged; `zoo` and `kilo` gain the new `lieutenant` mode alongside the deprecated `orchestrator` entry.
- `code` and `lieutenant` agents require nested sub-tasks (`new_task`) to be spawned sequentially, one at a time.
- `review-code` and `review-plan` no longer spawn further sub-tasks.
- `merge-modes.py` edge cases hardened.
- Documentation restructure: new `docs/architecture.md`, `docs/development.md`, and `docs/lieutenant-workflow.md` (renamed from `orchestrator-workflow`); README rewritten around the captain/skills layout; `github-issue` routed through `captain`.

### Added (package scaffold)
- npm package scaffold (`@gelse/ai-snippets` 0.1.0): tsup build emitting `dist/cli.cjs` (CommonJS, entry for the `ai-snippets` bin) and `dist/release.js` (ESM), with `yaml` bundled into the CLI so it runs from a bare tarball unpack; prebuild step stages `skills-embedded/` from `output/`, `files` field ships only `dist/` + `skills-embedded/`.
- Installer CLI (`ai-snippets install <tool>`): reads bundled `install-manifest.json` and embedded skills tree, installs modes and skills for zoo, kilo, opencode, and claude.
- Interactive wizard: launches when no tool is specified, walks through tool selection, scope, and confirmation.
- Collision prompts: overwrite / skip / abort when destination exists; `--yes` implies overwrite; `--dry-run` shows plan without writing.
- YAML merge for zoo global modes: `~/.roo/custom_modes.yaml` entries with matching slugs are replaced, user entries are preserved.
- Non-TTY stdin contract: EOF or empty answer on piped stdin aborts non-zero instead of defaulting to overwrite.
- Smoke test script (`scripts/smoke-test.sh`): covers dry-run, real install, collision prompts, abort, piped stdin, `--yes` overwrite, and EOF non-zero exit.

## [0.1.0] - 2026-09-13

Initial development release of the AI-snippets toolkit.

### Added
- `modes.json` mode definitions with `generate.py` generator and Makefile targets for Zoo, Claude Code, OpenCode, and Kilo Code deployment.
- Skills: `github-issue`, `grilling`, `writing-for-humans`, `release` (dual-form: markdown and directory with companion scripts).
- `release.py` CLI with `preflight`, `changes`, `check-version`, `finalize`, and `post-verify` subcommands, plus SKILL.md with pause gates.
- `verify.py` with dual-form skill validation and collision checks.

### Fixed
- `release.py` now tags the release on `main` (after promotion) instead of `testing`.
- Moved `finalize` ancestry guards before checkout so aborted runs leave the tree on the original branch.
