# Changelog

## [Unreleased]

### Added
- `install-manifest.json` emitter in [`generate.py`](scripts/generate.py) and a `manifest` Makefile target (included in `all`) — writes `output/install-manifest.json` declaring each tool's artifact source paths and local/global destinations for the installer CLI.
- `check-node` Makefile guard that prints a clear failure message when Node.js is not installed.
- Makefile `package-npx` target: generates all tool artifacts, builds the TypeScript package, copies `dist/release.js` into `skills-embedded/`, and produces a tarball in `dist/`.
- Makefile `package-npx-zoo`, `package-npx-kilo`, `package-npx-opencode`, `package-npx-claude` smoke-test targets that run a real install via the built package.
- `make verify` now includes a node-optional block: when both `node` and `npm` are available, it runs `tsc --noEmit`, `npm run build`, and a dry-run install; otherwise prints `SKIP: node not available`.

### Removed
- Legacy Makefile JS-only targets: `verify-js`, `zoo-js`, `kilo-js`, `opencode-js`, `claude-js`, `all-js`.
- `scripts/package.json` and `scripts/package-lock.json` — npm dependencies are now managed at the repo root.
+
### Added (package scaffold)
- npm package scaffold (`@gelse/ai-snippets` 0.1.0): tsup build emitting `dist/cli.js` and `dist/release.js`, prebuild step stages `skills-embedded/` from `output/`, `files` field ships only `dist/` + `skills-embedded/`.
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
