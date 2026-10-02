# Lieutenant Workflow

This document covers the captain entry point, the lieutenant's shared execution playbook, the task-type skills, the `github-issue` autonomous pipeline, and model-selection philosophy.

## Captain

The captain is the default entry point. It classifies the task into one of six types, dispatches the lieutenant as a subtask carrying the chosen skill, and supervises execution.

### Classification

Captain reads the user's request, gathers minimal evidence (file references, branches, issues, milestones), and matches symptoms to a task type:

| Symptoms | Type | Skill |
|----------|------|-------|
| Multi-part, design-heavy; multiple files/components; architecture decisions | Full feature | `full-feature` |
| Single, contained, obvious; one file or a few files; no design ambiguity | Small feature | `small-feature` |
| Plan-only; no implementation requested; architecture or research | Architecture | `architecture` |
| Defect or broken behavior; regression; reproduction test needed | Bugfix | `bugfix` |
| Primary deliverable is a document — create, update, or correct existing prose docs under `README.md` and `docs/` | Documentation | `documentation` |
| Approved milestone file exists under `plans/` and maps to the task | Implementation from milestone | `implementation-from-milestone` |

**Tiebreak:** If two types fit, prefer the smaller one. When the primary deliverable is a document, `documentation` takes precedence over `small-feature`, `full-feature`, and `architecture` regardless of size or how much research the task involves. Other types still win when a document is merely an output of the work — implementing a milestone that happens to update `docs/` stays `implementation-from-milestone`, and a bugfix whose fix touches docs stays `bugfix`. If evidence is missing to decide, investigate first; do not guess.

### Dispatch and supervision

Captain dispatches the lieutenant via `new_task` with the original request, the classified skill, and relevant evidence. Every `new_task` message body MUST start with two header lines — `target-agent:` naming the spawned mode and `target-agent-skill:` naming that mode's `agent-<slug>` skill — followed by a blank line, then the request:

```
target-agent: lieutenant
target-agent-skill: agent-lieutenant

<original request, skill name, evidence>
```

The lieutenant reads the header, loads the named skill, and executes its workflow.

Captain monitors the lieutenant's completion summary and verifies that the dispatched skill's workflow was followed and completion criteria were met.

### Re-classification

If verify finds a design-level cause, or the task outgrows its classification, this is misclassification evidence — captain re-classifies and re-dispatches with the corrected skill, preserving all completed work.

Captain's mode definition is instruction-level read-only (`[read, command, mcp]` groups); no tool-enforced edit restrictions are claimed.

## Skills

The lieutenant dispatches exactly one skill per run. Each skill defines a workflow sequence, type-specific rules, and a failure-recovery table. The lieutenant loads the skill via the `skill` tool and follows it end-to-end. The ten `agent-*` skills are the mode runbooks — each `agents/<slug>.md` stub loads its `agent-<slug>` skill, which carries the mode's full workflow, dispatch contract, and quality gates. The subsections below cover both groups.

### Full feature

**Workflow:** `investigator → plan (nested review-plan) → milestone files under plans/ → code per milestone (nested verify + review-code) → final verify`

**Key rules:** Use the `grilling` skill in plan dispatch when human input is needed. Milestone files use the format defined in plan mode. Code dispatches are per milestone file. Final verify covers cross-task integration.

**Recovery:** Unclear failure → verify. Implementation cause → code → verify. Design issue → targeted investigator → plan → re-dispatch code → verify. Evidence gap in plan review → targeted investigator → plan → re-review.

### Small feature

**Workflow:** `code (nested verify; unit tests required; nested review-code when risky or externally visible)`

**Key rules:** Single code dispatch. No investigator or plan. Unit tests are mandatory.

**Recovery:** Obvious failure → code → verify. Unclear failure → verify. Implementation cause → code → verify. Design issue or scope growth → report to captain for re-classification.

### Architecture

**Workflow:** `investigator → plan (nested review-plan) → milestone files under plans/` — no implementation dispatch.

**Key rules:** Always use the `grilling` skill in plan dispatch. Milestone format per plan mode. Completion = approved milestone files.

**Recovery:** Evidence gap in plan review → targeted investigator → plan → re-review.

### Bugfix

**Workflow:** `code (failing reproduction test first → fix → nested verify) → final verify`

**Key rules:** Reproduction test fails before fix, passes after. Minimal fix — no unrelated refactoring.

**Recovery:** Same as small feature: obvious failure → code → verify; unclear failure → verify; implementation cause → code → verify; design issue → report to captain for re-classification.

### Documentation

**Workflow:** `investigator → plan (conditional) → code (nested verify) → verify` — per [`skills/documentation.md`](../skills/documentation.md):14. Plan dispatches only when the request spans new documents that need a shared structure before anyone writes; single-doc edits dispatch `code` directly.

**Key rules:** Every claim, code sample, command, link, and version reference is checked against the code before it ships. Updating stale docs is in scope — a document wrong against the code is a defect this skill fixes. Scope-out boundaries are binding: [`CHANGELOG.md`](../CHANGELOG.md) and release notes route to the [`release`](../skills/release/SKILL.md) skill, milestone files under [`plans/`](../plans/) route to the [`architecture`](../skills/architecture.md) skill, in-source docstrings and code comments route to the [`code`](../skills/agent-code.md) skill.

**Recovery:** Per the [`skills/documentation.md`](../skills/documentation.md):75-80 failure-recovery table — obvious failure at final verify or nested gate → `code → verify`; unclear failure → `verify`; verify finds inaccuracy or broken reference → `code → verify`; verify finds design issue or task outgrows scope → report to captain for re-classification.

### Implementation from milestone

**Workflow:** `code per task directly from plans/<milestone>.md → final verify`

Milestone not yet reviewed → dispatch `plan` with the existing milestone file (plan runs its nested review-plan loop). Milestone flawed mid-implementation → targeted investigator → plan (nested review-plan) → re-dispatch code.

```mermaid
flowchart TD
    A{Milestone reviewed?}
    A -->|No| B[Plan with milestone file]
    B --> B1["review-plan loop\ndraft → revise until approved"]
    B1 --> C[Code per task from milestone]
    A -->|Yes| C
    C --> D[nested verify + review-code]
    D --> E[Final verify]
    C -.->|Flawed| F[Targeted investigator]
    F --> G[Plan revises milestone]
    G --> C
```

**Key rules:** Milestone format per plan mode. Code uses `Verification` and `Non-goals` fields as its dispatch contract. Final verify covers cross-task integration.

**Recovery:** Obvious failure → code → verify. Unclear failure → verify. Implementation cause → code → verify. Design issue → targeted investigator → plan → re-dispatch code → verify.

### Agent-captain

Classifies incoming work and supervises the lieutenant as it executes the chosen skill; every dispatch carries the `target-agent` / `target-agent-skill` header. Runbook: [`skills/agent-captain.md`](../skills/agent-captain.md).

### Agent-lieutenant

Runs a dispatched skill end to end by delegating each step to specialist sub-tasks. Runbook: [`skills/agent-lieutenant.md`](../skills/agent-lieutenant.md).

### Agent-investigator

Turns an unclear task into a short, cited evidence report for planning. Runbook: [`skills/agent-investigator.md`](../skills/agent-investigator.md).

### Agent-plan

Turns a task and repository evidence into the smallest correct, implementation-ready plan. Runbook: [`skills/agent-plan.md`](../skills/agent-plan.md).

### Agent-review-code

Advisory review of a change for correctness, security, reliability, and compatibility regressions. Runbook: [`skills/agent-review-code.md`](../skills/agent-review-code.md).

### Agent-security-review

Advisory security-only review of a change for injection, credential, and breach risks. Runbook: [`skills/agent-security-review.md`](../skills/agent-security-review.md).

### Agent-review-plan

Adversarial check of a plan's completeness, feasibility, dependencies, and verifiability. Runbook: [`skills/agent-review-plan.md`](../skills/agent-review-plan.md).

### Agent-code

Executes one scoped task with a minimal correct implementation plus tests and nested quality gates. Runbook: [`skills/agent-code.md`](../skills/agent-code.md).

### Agent-verify

Proves the change works — focused tests, execution, failure diagnosis, and fix confirmation. Runbook: [`skills/agent-verify.md`](../skills/agent-verify.md).

### Agent-ask

Answers technical questions from repository evidence with only the needed detail. Runbook: [`skills/agent-ask.md`](../skills/agent-ask.md).

## Milestones

Milestone files live in `plans/` (local, gitignored). Each file is one implementation-ready unit produced or revised by `plan`. The canonical format is defined in [plan mode](../skills/agent-plan.md#milestone-file-output-architectureplanning-tasks) — lieutenant, skills, and `code` reference it by name and do not restate it.

## End-to-End Autonomous Issue Resolution with `github-issue`

The [`github-issue`](../skills/github-issue.md) skill combines the lieutenant's loop with GitHub operations to resolve a GitHub issue completely autonomously — from intake to pull request.

### The Full Autonomous Pipeline

| Phase | What happens | Modes involved |
|-------|-------------|----------------|
| **1. Retrieve & Validate** | Fetch issue, comments, labels, linked PRs via `gh`. Stop if ambiguous. | lieutenant (reads only) |
| **2. Feature Branch** | Create a branch referencing the issue, starting at the remote testing branch. No code yet. | lieutenant (git via `execute_command`) |
| **3. Classify & Execute** | Hand the validated issue to captain. Captain classifies the issue type and dispatches the lieutenant with the matching skill. The skill context (this lieutenant run) owns the git/gh phases — branch, commit/push, PR; the captain subtask and its lieutenant dispatch run only the classified workflow. | lieutenant → captain → lieutenant with skill |
| **4. Commit, Push, PR** | Review final diff, commit, push, open PR to the testing branch referencing the issue. | lieutenant (git/gh via `execute_command`) |
| **5. Report** | Summarize branch, implementation, tests, PR link, limitations. | lieutenant (synthesis) |

### What Makes This Autonomous

- The skill defines **every phase** as a deterministic step — no human prompting is required between phases.
- The lieutenant delegates **all implementation** to subtasks; it never writes code itself, keeping context lean.
- Nested sub-task spawning keeps review/verify context small — each gate runs against only its task's scope, not the entire change set.
- Zoo Code's auto-approval configuration allows dispatched subtasks and their tool calls to proceed without manual confirmation.
- The `gh` CLI handles all GitHub interactions without browser or API key prompts.

### The One Hard Stop

If the original issue contains **material ambiguity** that cannot be resolved from the codebase, comments, or linked references, the skill instructs the lieutenant to **stop immediately** — do not guess, do not modify the repository. This is a deliberate safety valve.

## Model Selection Philosophy

**This autonomous pipeline only works reliably if the models backing each mode are chosen carefully.** The lieutenant delegates context-heavy decisions to subtasks; each subtask runs in isolation with only the context it was given. A weak model produces a silent, cascading failure. Agents that spawn nested sub-tasks (`plan`, `code`) need instruction-following strong enough to manage their own quality gates.

### What "Strong" and "Weak" Mean Here

| Role | Needs | Why |
|------|-------|-----|
| **captain** | Full-tier reasoning | Must classify tasks accurately, detect misclassification, supervise lieutenant output |
| **lieutenant** | Strong reasoning, structured output | Must load and follow skills, track state across subtasks, decide next steps from summaries |
| **plan / review-plan** | Strong reasoning, codebase comprehension | Must investigate files, understand architecture, produce actionable task lists; plan also manages nested review loop |
| **review-code / security-review** | Strong reasoning, attention to detail | Must find real bugs, trace data flow, assess exploitability |
| **code** | Strong coding ability, instruction following | Must implement precisely within scope, write tests, run verification, and manage nested quality gates |
| **verify** | Strong reasoning + coding | Must diagnose failures, design and run targeted tests, propose targeted fixes |

### What Breaks with Weak Models

| Weak model assigned to… | Failure symptom |
|------------------------|-----------------|
| **captain** | Misclassifies tasks; fails to detect scope growth; dispatches wrong skill |
| **lieutenant** | Loses track of subtask results; replans unnecessarily; fails to escalate; dispatches tasks with missing context |
| **plan** | Produces vague, unactionable tasks; misses files; wrong dependency ordering; fails to manage nested review loop |
| **review-plan** | Approves broken plans; misses CRITICAL findings |
| **code** | Implements outside scope; ignores conventions; skips or mishandles nested quality gates |
| **review-code** | Reports style nits but misses logic bugs; misses security issues |
| **verify** | Misdiagnoses failures; applies incorrect fixes; loops indefinitely |

**Rule of thumb:** The captain and lieutenant are the highest-leverage model assignments. A weak captain breaks the entire system through misclassification. A weak lieutenant breaks skill execution. A weak coder breaks one task; the lieutenant's review loop can catch and recover from that.

### Mode → Model Mapping

Each mode has a backing model. For OpenCode, the model is preset into the agent's frontmatter from [`models/mapping.yaml`](../models/mapping.yaml) at generation time — the emitter inserts `model: litellm/<id>` between `mode` and `permission`, and [`scripts/verify.py`](../scripts/verify.py) at `verify_opencode_agent_models()` enforces the match. For Zoo and Kilo, the model is selected in the tool's settings. The principle: **never leave the pipeline's roles on a single uniform default.** Autonomy quality is bounded by the weakest model in the loop, and different roles fail in different ways.

| Mode | Role | Model Class |
|------|------|-------------|
| `captain` | Classification + supervision | Full-tier reasoning |
| `lieutenant` | Shared execution playbook | Full-tier reasoning |
| `plan` | Design + decomposition | Full-tier reasoning |
| `review-plan` | Plan validation | Heavy-tier reasoning |
| `investigator` | Evidence gathering | Flash-tier fast reading |
| `code` | Implementation | General-purpose |
| `verify` | Testing + diagnosis | Flash-tier fast reading |
| `review-code` | Code review | Flash-tier fast reading |
| `security-review` | Security review | Heavy-tier reasoning |

The specific models will change over time — the principle is what matters: match each role to the model class its job demands.
