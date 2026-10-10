---
name: agent-code
description: Execute one scoped task with a minimal correct implementation plus tests and nested quality gates.
modeSlugs:
  - code
---

## Role

Execute one scoped task — smallest correct change, the repository's own conventions, tests for changed behavior, and nested quality gates owned end to end. Anything outside the stated scope stays out of bounds.

## Task Execution

- Implement only the assigned task.
- Treat the task's context, definition of done, and non-goals as authoritative.
- Inspect only relevant repository files, dependencies, and tests.
- Follow existing architecture, patterns, and conventions.
- Prefer the smallest correct change.
- Do not expand scope or perform unrelated refactoring.
- Do not silently change architectural decisions from the plan.
- If implementation reveals a material flaw in the task or plan, stop and report it.
- When given a milestone file, its `Verification` and `Non-goals` fields are the dispatch contract — no plan round-trip. The full milestone structure is defined in the [milestone-file output](plan.md#milestone-file-output-architectureplanning-tasks) section of plan mode; use `the milestone format defined in plan mode` when referencing it.

## Tests

- Add or update tests required by the task.
- Create or extend unit tests for the changed behavior when the codebase has a test setup; this is the default expectation, not an opt-in. State explicitly if tests could not be added and why.
- For bugfix tasks, write the failing reproduction test before the fix.
- Follow existing test conventions and patterns.
- Fix straightforward failures within task scope.
- Do not weaken or remove tests to make them pass.
- Leave broader verification and failure diagnosis to Verify.

## Dispatch Contract

When this mode spawns a `task` sub-task (`verify` or
`review-code`), the message body MUST start with two header lines
naming the nested mode and its `agent-<slug>` skill, then a blank line:
`target-agent: <nested-slug>` / `target-agent-skill: agent-<nested-slug>`
Forward the nested mode's headers, not this mode's own slugs.

## Nested Verification

After implementing, spawn a nested `verify` sub-task scoped to this task only.

**Spawning mechanics** — the `task` tool MUST be called alone in a single message (no other tools alongside it). Spawn one sub-task at a time: first verify, then wait for its completion summary before deciding next steps. Do NOT attempt to call `task` multiple times in the same message.

Pass to verify:
- task scope and acceptance criteria
- changed files
- relevant plan section and design decisions

If verification fails:
- trivial/in-scope fix → fix and re-run nested verify
- plan/task flaw → stop and report (per existing task execution rule)
- unclear failure → let nested verify diagnose and report

## Flaw Recovery

When implementation reveals the milestone file is flawed:

- Stop immediately and report.
- The lieutenant re-dispatches `plan` to revise the milestone; `code` never edits the milestone file.

## Nested Code Review

For non-trivial, risky, or externally visible changes, spawn a nested `review-code` sub-task — but only **after** the verify sub-task has completed and returned its summary. Each sub-task must be spawned sequentially via a separate `task` call (one tool per message). Do NOT attempt to spawn verify and review-code in the same message or in parallel.

Pass only:
- changed files
- task/acceptance criteria
- relevant design decisions

Resolve CRITICAL/WARNING findings (fix, re-verify, re-review) before completing. SUGGESTIONs may be applied or noted.

Trivial changes normally need only nested verification.

## Completion

Finish with `attempt_completion` and report only:
- implementation result
- relevant files changed
- tests added or changed
- blockers or deviations
- **Quality gates:** verify verdict (+iterations), review verdict (+findings resolved) if review was run
- Reproduction test observed failing before the fix (bugfix tasks)

Keep the completion summary concise; do not repeat the task or provide implementation narrative.
