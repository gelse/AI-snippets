# Changelog

## [0.1.0] - 2026-09-13

Initial development release of the AI-snippets toolkit.

### Added
- `modes.json` mode definitions with `generate.py` generator and Makefile targets for Zoo, Claude Code, OpenCode, and Kilo Code deployment.
- Skills: `github-issue`, `grilling`, `writing-for-humans`, `release` (dual-form: markdown and directory with companion scripts).
- `release.py` CLI with `preflight`, `changes`, `check-version`, `finalize`, and `post-verify` subcommands, plus SKILL.md with pause gates.
- `verify.py` with dual-form skill validation and collision checks.
