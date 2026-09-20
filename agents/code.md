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

## Nested Verification

After implementing, spawn a nested `verify` sub-task scoped to this task only.

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
- The orchestrator re-dispatches `plan` to revise the milestone; `code` never edits the milestone file.

## Nested Code Review

For non-trivial, risky, or externally visible changes, spawn a nested `review-code` sub-task.

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
