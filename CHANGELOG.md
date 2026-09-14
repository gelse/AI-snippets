# Changelog

## [Unreleased]

### Added
- Node.js counterparts (`*.mjs`) for all release scripts: `scripts/generate.mjs`, `scripts/verify.mjs`, `skills/release/release.mjs`.
- `scripts/package.json` with `yaml` (eemeli) dependency — auto-installed by the `*-js` Makefile targets via `npm install`.
- Makefile `-js` targets: `verify-js`, `zoo-js`, `kilo-js`, `opencode-js`, `claude-js`, `all-js` — run the same validation and generation using Node.js ≥ 18 (requires `npm install` in `scripts/`, handled automatically).
- `check-node` Makefile guard that prints a clear failure message when Node.js is not installed.

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
