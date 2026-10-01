# AI-Snippets

One command installs 13 agent modes (10 active + 3 deprecated gatekeepers) and 20 skills (10 existing + 10 `agent-*` runbook skills) into Zoo Code, Kilo Code, or OpenCode. Captain is the default entry point — it classifies tasks and dispatches the lieutenant with the matching skill. Modes give your coding agent specialized subagents — lieutenant, planner, reviewer, verifier, and more. Skills are reusable workflow runbooks that drive end-to-end autonomous pipelines.

> **Note:** Claude Code is currently a research-phase target and is NOT officially supported.

## Quick Start

```bash
npx @gelse/ai-snippets install <tool> [flags]
```

**Tools:** `zoo`, `kilo`, `opencode`

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
npm install
make all        # generate output/ artifacts — npm run build fails without them
npm run build
node dist/cli.cjs install <tool> [options]
```

## What You Get

### 13 Agent Modes

| Mode | Purpose | Runbook |
|------|---------|---------|
| `captain` | Classify tasks and dispatch the lieutenant with the matching skill — default entry point | [`agent-captain`](skills/agent-captain.md) |
| `lieutenant` | Execute the dispatched skill's workflow through shared dispatch contracts | [`agent-lieutenant`](skills/agent-lieutenant.md) |
| `investigator` | Gather repository evidence for planning | [`agent-investigator`](skills/agent-investigator.md) |
| `plan` | Design implementation-ready plans from repository evidence | [`agent-plan`](skills/agent-plan.md) |
| `review-code` | Review code changes locally | [`agent-review-code`](skills/agent-review-code.md) |
| `review-plan` | Review implementation plans for completeness, feasibility, and correctness | [`agent-review-plan`](skills/agent-review-plan.md) |
| `security-review` | Security-focused review of code changes | [`agent-security-review`](skills/agent-security-review.md) |
| `code` | Write, modify, and refactor code | [`agent-code`](skills/agent-code.md) |
| `verify` | Test, verify, and diagnose software | [`agent-verify`](skills/agent-verify.md) |
| `ask` | Answer technical questions and explain concepts | [`agent-ask`](skills/agent-ask.md) |
| `architect` | Deprecated — aborts and directs you to `plan` | — |
| `debug` | Deprecated — aborts and directs you to `plan` | — |
| `orchestrator` | Deprecated — aborts and directs you to `lieutenant` | — |

### 20 Skills

| Skill | Purpose |
|-------|---------|
| [`github-issue`](skills/github-issue.md) | End-to-end GitHub issue → PR via `gh`, lieutenant-driven |
| [`full-feature`](skills/full-feature.md) | Multi-part design-heavy work: investigate → plan → milestones → code → verify |
| [`small-feature`](skills/small-feature.md) | Single contained change: code with mandatory unit tests |
| [`architecture`](skills/architecture.md) | Plan-only output producing milestone files under plans/ |
| [`bugfix`](skills/bugfix.md) | Defect fix: reproduction test first → fix → verify |
| [`implementation-from-milestone`](skills/implementation-from-milestone.md) | Execute tasks directly from a milestone file — unreviewed milestones route through plan first |
| [`grilling`](skills/grilling.md) | Plan stress-testing Q&A before building |
| [`writing-for-humans`](skills/writing-for-humans.md) | Prose standard and review criteria for human-readable writing |
| [`documentation`](skills/documentation.md) | Human-facing prose deliverables: docs, READMEs, release notes, specs |
| [`release`](skills/release/SKILL.md) | Testing-branch release workflow with helper scripts |
| [`agent-captain`](skills/agent-captain.md) | Runbook for the `captain` mode — classifies tasks and supervises the lieutenant |
| [`agent-lieutenant`](skills/agent-lieutenant.md) | Runbook for the `lieutenant` mode — runs the dispatched skill end to end via sub-tasks |
| [`agent-investigator`](skills/agent-investigator.md) | Runbook for the `investigator` mode — cited evidence reports for planning |
| [`agent-plan`](skills/agent-plan.md) | Runbook for the `plan` mode — smallest correct, implementation-ready plan |
| [`agent-review-code`](skills/agent-review-code.md) | Runbook for the `review-code` mode — advisory correctness and security review |
| [`agent-security-review`](skills/agent-security-review.md) | Runbook for the `security-review` mode — security-only advisory review |
| [`agent-review-plan`](skills/agent-review-plan.md) | Runbook for the `review-plan` mode — adversarial check of plan completeness and feasibility |
| [`agent-code`](skills/agent-code.md) | Runbook for the `code` mode — one scoped task, tests, nested quality gates |
| [`agent-verify`](skills/agent-verify.md) | Runbook for the `verify` mode — proves the change works via tests and diagnosis |
| [`agent-ask`](skills/agent-ask.md) | Runbook for the `ask` mode — answers technical questions from repository evidence |

## Per-Tool Install Paths

The Makefile install targets and CLI installer write to these locations depending on tool and scope. OpenCode skills require the directory form (`<name>/SKILL.md`); the generator emits that form (the flat-output emitter bug was fixed this release), and the Makefile targets install it directly.

| Tool | Agents (global) | Agents (local) | Skills (global) | Skills (local) |
|------|----------------|----------------|-----------------|----------------|
| **zoo** | `~/.roo/custom_modes.yaml` (overwritten) + Zoo Code globalStorage `custom_modes.yaml` (merged) | `.roomodes` | `~/.roo/skills/<name>.md` | `.roo/skills/<name>.md` |
| **kilo** | `~/.config/kilo/agent/` (individual `.md` files) | `.kilocodemodes` | `~/.kilo/skills/<name>.md` | `.kilo/skills/<name>.md` |
| **opencode** | `~/.config/opencode/agents/*.md` | `.opencode/agents/*.md` | `~/.config/opencode/skills/<name>/SKILL.md` | `.opencode/skills/<name>/SKILL.md` |

Directory-form skills (like `release`) also ship companion files (scripts, configs) alongside the runbook.

### Merge Safety (Zoo Global)

When installing zoo globally, the CLI installer **merges** `~/.roo/custom_modes.yaml`, not overwrites. The installer parses the YAML preserving comments, `---` separators, and sibling keys. Modes with matching slugs are replaced, duplicates are removed, foreign (non-ai-snippets) modes are kept, and new modes are appended. A missing destination file is treated as a plain copy.

The legacy Makefile target `install-zoo-global-agents` **overwrites** `~/.roo/custom_modes.yaml` but also **merges** into the Zoo Code globalStorage `custom_modes.yaml` (matching slugs replaced, foreign entries kept, new slugs appended). If the globalStorage directory is absent, a skip notice is printed and the target exits successfully. Override with `make install-zoo-global-agents ZOO_GLOBALSTORAGE=/path/to/custom_modes.yaml`. See [docs/development.md](docs/development.md) for details.

## How It Works

`modes.json` is the single source of truth for all mode definitions. Each mode's `customInstructions` is a repo-relative path `agents/<slug>.md` resolved at generation time by [`scripts/generate.py`](scripts/generate.py), which emits per-tool formats plus an `install-manifest.json` that maps every artifact to its destination paths and drives the installer. Each `agents/<slug>.md` is a minimal stub that names the mode's `agent-<slug>` runbook skill; at runtime the mode loads that skill and follows its full workflow — the stub carries no instructions of its own. The installer reads the manifest, computes a plan with `[create]/[update]/[merge]/[overwrite]` labels, and executes it with collision handling.

→ Full details: [docs/architecture.md](docs/architecture.md)

## More Documentation

| Document | What it covers |
|----------|---------------|
| [docs/architecture.md](docs/architecture.md) | Generation pipeline, manifest, installer merge/collision mechanics, per-tool emitted formats |
| [docs/lieutenant-workflow.md](docs/lieutenant-workflow.md) | Captain classification, lieutenant skills, milestones, github-issue pipeline, model-selection philosophy |
| [docs/development.md](docs/development.md) | Makefile targets, verify.py checks, smoke tests, build, packaging |

## Contributing

See [docs/development.md](docs/development.md) for build instructions, test targets, and contribution workflow. The Makefile provides `make verify` (lint + typecheck + build + dry-run), `make all` (generate all tool artifacts), and `make package-npx` (full npm pack).

---

## License

See [LICENSE](LICENSE).
