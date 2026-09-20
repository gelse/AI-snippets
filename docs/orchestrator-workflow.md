# Orchestrator Workflow

This document covers the orchestrator work loop, the `github-issue` autonomous pipeline, and model-selection philosophy.

## The Orchestrator's Work Loop

The orchestrator mode never writes code itself. It acts as a strategic coordinator, delegating every concrete action to a specialized subtask and retaining only orchestration-level context. Any agent can spawn nested sub-tasks via `new_task`, keeping review/verify context small by scoping it to individual tasks.

### Task-Type Workflows

The orchestrator selects a workflow based on the task type. Each row describes the full mode sequence for that branch.

| Task Type | Sequence |
|---|---|
| **Full feature** | `investigator → plan (nested review-plan) → milestone files under plans/ → code per milestone (nested verify + review-code) → final verify` |
| **Small feature** | `code (nested verify; unit tests required; nested review-code when risky or externally visible)` |
| **Architecture / planning** | `investigator → plan (nested review-plan) → milestone files under plans/` — no implementation dispatch |
| **Bugfix** | `code (failing reproduction test first → fix → nested verify) → final verify` |
| **Implementation from milestone** | `code per task directly from plans/<milestone>.md → final verify` — skip investigator/plan; milestone not yet reviewed → dispatch `plan` with the existing milestone file (plan runs its nested review-plan loop); milestone flawed mid-implementation → targeted investigator → plan (nested review-plan) → re-dispatch `code` |

Each task type has a distinct flow.

#### Full feature

A full-feature workflow runs investigation, planning with review, milestone creation, iterative code implementation, and final verification.

```mermaid
flowchart TD
    A[Investigate] --> B[Plan]
    B --> B1["review-plan loop\ndraft → revise until approved"]
    B1 --> C[Milestone files under plans/]
    C --> D[Code per milestone]
    D --> D1["nested verify + review-code"]
    D1 --> E{More milestones?}
    E -->|Yes| D
    E -->|No| F[Final verify]
```

#### Small feature

A small feature dispatches a single code task with mandatory unit tests; review-code runs when the change is risky or externally visible.

```mermaid
flowchart TD
    A[Code] --> B[nested verify]
    B --> C{Risky/external?}
    C -->|Yes| D[nested review-code]
    C -->|No| E[Done]
    D --> E
```

#### Architecture / planning

An architecture workflow produces milestone files under `plans/` without dispatching implementation.

```mermaid
flowchart TD
    A[Investigate] --> B[Plan]
    B --> B1["review-plan loop\ndraft → revise until approved"]
    B1 --> C[Milestone files under plans/]
```

#### Bugfix

A bugfix starts with a failing reproduction test, applies the fix, and runs nested and final verification.

```mermaid
flowchart TD
    A[Code] --> B[Failing reproduction test]
    B --> C[Fix]
    C --> D[nested verify]
    D --> E[Final verify]
```

#### Implementation from milestone

An implementation-from-milestone task executes tasks directly from a milestone file. Unreviewed milestones go through plan first; flawed milestones trigger targeted investigation and re-planning.

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

### Failure Recovery

Per-task failures are handled inside the `code` sub-task via nested quality gates. The orchestrator handles final-verify failures:

1. Obvious, in-scope failure → let `code` fix it.
2. Unclear or out-of-scope → dispatch `verify`.
3. `verify` finds implementation fix → dispatch `code`.
4. `verify` finds design issue or new evidence → targeted investigator → plan (nested review-plan) → re-dispatch `code`.
5. Requires human decision → escalate to user.
6. Re-verify after every fix.

## Milestones

Milestone files live in `plans/` (local, gitignored). Each file is one implementation-ready unit produced or revised by `plan`.

**File naming:** `plans/<kebab-case-name>.md`

**Structure per file:**

- **Goal** — concise outcome.
- **Design** — decisions and rationale.
- **Review verdict** — APPROVE / APPROVE WITH SUGGESTIONS / NEEDS CHANGES (set by nested review-plan).
- **Risks / Open Decisions** (optional) — open questions or decision points requiring user input.
- Per task:
  - **Files** — affected files.
  - **Changes** — exact changes.
  - **Dependencies** — ordering constraints.
  - **Acceptance** — observable criteria.
  - **Verification** — how verify runs (required, distinct from Acceptance).
  - **Non-goals** (optional) — explicit exclusions.

## End-to-End Autonomous Issue Resolution with `github-issue`

The [`github-issue`](../skills/github-issue.md) skill combines the orchestrator's loop with GitHub operations to resolve a GitHub issue completely autonomously — from intake to pull request.

### The Full Autonomous Pipeline

| Phase | What happens | Modes involved |
|-------|-------------|----------------|
| **1. Retrieve & Validate** | Fetch issue, comments, labels, linked PRs via `gh`. Stop if ambiguous. | orchestrator (reads only) |
| **2. Feature Branch** | Create a branch referencing the issue, starting at the remote testing branch. No code yet. | orchestrator (git via `execute_command`) |
| **3. Execute** | Run the workflow matching the issue type: full feature for multi-part issues, bugfix (reproduction test first) for defect reports, milestone implementation when a matching milestone file exists in plans/. | orchestrator → selected workflow |
| **4. Commit, Push, PR** | Review final diff, commit, push, open PR to the testing branch referencing the issue. | orchestrator (git/gh via `execute_command`) |
| **5. Report** | Summarize branch, implementation, tests, PR link, limitations. | orchestrator (synthesis) |

### What Makes This Autonomous

- The skill defines **every phase** as a deterministic step — no human prompting is required between phases.
- The orchestrator delegates **all implementation** to subtasks; it never writes code itself, keeping context lean.
- Nested sub-task spawning keeps review/verify context small — each gate runs against only its task's scope, not the entire change set.
- Zoo Code's auto-approval configuration allows dispatched subtasks and their tool calls to proceed without manual confirmation.
- The `gh` CLI handles all GitHub interactions without browser or API key prompts.

### The One Hard Stop

If the original issue contains **material ambiguity** that cannot be resolved from the codebase, comments, or linked references, the skill instructs the orchestrator to **stop immediately** — do not guess, do not modify the repository. This is a deliberate safety valve.

## Model Selection Philosophy

**This autonomous pipeline only works reliably if the models backing each mode are chosen carefully.** The orchestrator delegates context-heavy decisions to subtasks; each subtask runs in isolation with only the context it was given. A weak model produces a silent, cascading failure. Agents that spawn nested sub-tasks (`plan`, `code`) need instruction-following strong enough to manage their own quality gates.

### What "Strong" and "Weak" Mean Here

| Role | Needs | Why |
|------|-------|-----|
| **orchestrator** | Strong reasoning, structured output | Must decompose problems, track state across subtasks, decide next steps from summaries |
| **plan / review-plan** | Strong reasoning, codebase comprehension | Must investigate files, understand architecture, produce actionable task lists; plan also manages nested review loop |
| **review-code / security-review** | Strong reasoning, attention to detail | Must find real bugs, trace data flow, assess exploitability |
| **code** | Strong coding ability, instruction following | Must implement precisely within scope, write tests, run verification, and manage nested quality gates |
| **verify** | Strong reasoning + coding | Must diagnose failures, design and run targeted tests, propose targeted fixes |

### What Breaks with Weak Models

| Weak model assigned to… | Failure symptom |
|------------------------|-----------------|
| **orchestrator** | Loses track of subtask results; replans unnecessarily; fails to escalate; dispatches tasks with missing context |
| **plan** | Produces vague, unactionable tasks; misses files; wrong dependency ordering; fails to manage nested review loop |
| **review-plan** | Approves broken plans; misses CRITICAL findings |
| **code** | Implements outside scope; ignores conventions; skips or mishandles nested quality gates |
| **review-code** | Reports style nits but misses logic bugs; misses security issues |
| **verify** | Misdiagnoses failures; applies incorrect fixes; loops indefinitely |

**Rule of thumb:** The orchestrator and planning/review roles are the highest-leverage model assignments. A weak orchestrator breaks the entire system. A weak coder breaks one task; the orchestrator's review loop can catch and recover from that.

### Mode → Model Mapping

The model backing each mode is selected in the tool's settings. The principle: **never leave the pipeline's roles on a single uniform default.** Autonomy quality is bounded by the weakest model in the loop, and different roles fail in different ways.

| Mode | Role | Model Class |
|------|------|-------------|
| `orchestrator` | Coordination | Full-tier reasoning |
| `plan` | Design + decomposition | Full-tier reasoning |
| `review-plan` | Plan validation | Heavy-tier reasoning |
| `investigator` | Evidence gathering | Flash-tier fast reading |
| `code` | Implementation | General-purpose |
| `verify` | Testing + diagnosis | Flash-tier fast reading |
| `review-code` | Code review | Flash-tier fast reading |
| `security-review` | Security review | Heavy-tier reasoning |

The specific models will change over time — the principle is what matters: match each role to the model class its job demands.
