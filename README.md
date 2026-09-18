# AI-Snippets

One command installs 11 agent modes and 4 skills into Zoo Code, Kilo Code, OpenCode, or Claude Code. Modes give your coding agent specialized subagents — orchestrator, planner, reviewer, verifier, and more. Skills are reusable workflow runbooks that drive end-to-end autonomous pipelines.

## Quick Start

```bash
npx @gelse/ai-snippets install <tool> [flags]
```

**Tools:** `zoo`, `kilo`, `opencode`, `claude`

| Flag | Effect |
|------|--------|
| `--global` (default) | Install to the tool's global config directory |
| `--local` | Install to the local (project-level) config directory |
| `--skills-only` | Install only skills, skip agent modes |
| `--agents-only` | Install only agent modes, skip skills |
| `--dry-run` | Show what would be installed without writing files |
| `--yes` / `-y` | Overwrite existing files without prompting |
| `--help` / `-h` | Show help |

Running without arguments launches an **interactive wizard** — pick a tool, choose scope, confirm.

**Collision handling:** When a destination file already exists, the installer prompts `[o]verwrite / [s]kip / [a]bort`. `--yes` implies overwrite. On non-TTY (piped/redirected stdin), EOF or empty answer aborts with exit code 1 — use `--yes` for scripted installs.

### Build from Source

```bash
git clone https://github.com/gelse/ai-snippets.git && cd ai-snippets
npm install && npm run build
node dist/cli.cjs install <tool> [options]
```

## What You Get

### 11 Agent Modes

| Mode | Purpose |
|------|---------|
| `orchestrator` | Coordinate tasks across specialized modes with minimal unnecessary work |
| `investigator` | Gather repository evidence for planning |
| `plan` | Design implementation-ready plans from repository evidence |
| `review-code` | Review code changes locally |
| `review-plan` | Review implementation plans for completeness, feasibility, and correctness |
| `security-review` | Security-focused review of code changes |
| `code` | Write, modify, and refactor code |
| `verify` | Test, verify, and diagnose software |
| `ask` | Answer technical questions and explain concepts |
| `architect` | Deprecated — use `plan` instead |
| `debug` | Deprecated — use `verify` instead |

### 4 Skills

| Skill | Purpose |
|-------|---------|
| [`github-issue`](skills/github-issue.md) | End-to-end GitHub issue → PR via `gh`, orchestrator-driven |
| [`grilling`](skills/grilling.md) | Plan stress-testing Q&A before building |
| [`writing-for-humans`](skills/writing-for-humans.md) | Prose standard + review buckets for human-readable docs |
| [`release`](skills/release/SKILL.md) | Testing-branch release workflow with helper scripts |

## Per-Tool Install Paths

The installer writes to these locations depending on tool and scope:

| Tool | Agents (global) | Agents (local) | Skills (global) | Skills (local) |
|------|----------------|----------------|-----------------|----------------|
| **zoo** | `~/.roo/custom_modes.yaml` (merged) | `.roomodes` | `~/.roo/skills/<name>/SKILL.md` | `.roo/skills/<name>/SKILL.md` |
| **kilo** | `~/.config/kilo/agent/` (individual `.md` files) | `.kilocodemodes` | `~/.kilo/skills/<name>/SKILL.md` | `.kilo/skills/<name>/SKILL.md` |
| **opencode** | `~/.config/opencode/agents/*.md` | `.opencode/agents/*.md` | `~/.config/opencode/skills/<name>/SKILL.md` | `.opencode/skills/<name>/SKILL.md` |
| **claude** | `~/.claude/agents/*.md` | `.claude/agents/*.md` | `~/.claude/skills/<name>/SKILL.md` | `.claude/skills/<name>/SKILL.md` |

Directory-form skills (like `release`) also ship companion files (scripts, configs) alongside the runbook.

### Merge Safety (Zoo Global)

When installing zoo globally, `~/.roo/custom_modes.yaml` is **merged**, not overwritten. The installer parses the YAML preserving comments, `---` separators, and sibling keys. Modes with matching slugs are replaced, duplicates are removed, foreign (non-ai-snippets) modes are kept, and new modes are appended. A missing destination file is treated as a plain copy.

> ⚠️ The legacy Makefile target `install-zoo-global-agents` **overwrites** `custom_modes.yaml`. Use the CLI installer instead — see [docs/development.md](docs/development.md) for details.

## How It Works

`modes.json` is the single source of truth for all mode definitions. A Python generator ([`scripts/generate.py`](scripts/generate.py)) emits per-tool formats plus an [`install-manifest.json`](scripts/generate.py) that drives the installer. The installer reads the manifest, computes a plan with `[create]/[update]/[merge]/[overwrite]` labels, and executes it with collision handling.

→ Full details: [docs/architecture.md](docs/architecture.md)

## More Documentation

| Document | What it covers |
|----------|---------------|
| [docs/architecture.md](docs/architecture.md) | Generation pipeline, manifest, installer merge/collision mechanics, per-tool emitted formats |
| [docs/orchestrator-workflow.md](docs/orchestrator-workflow.md) | Orchestrator work loop, github-issue pipeline, model-selection philosophy |
| [docs/development.md](docs/development.md) | Makefile targets, verify.py checks, smoke tests, build, packaging |
| [docs/npm-trusted-publishing.md](docs/npm-trusted-publishing.md) | npm OIDC trusted publishing setup |

## Contributing

See [docs/development.md](docs/development.md) for build instructions, test targets, and contribution workflow. The Makefile provides `make verify` (lint + typecheck + build + dry-run), `make all` (generate all tool artifacts), and `make package-npx` (full npm pack).

---

## License

See [LICENSE](LICENSE).
