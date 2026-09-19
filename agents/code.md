## Task Execution

- Implement only the assigned task.
- Treat the task's context, definition of done, and non-goals as authoritative.
- Inspect only relevant repository files, dependencies, and tests.
- Follow existing architecture, patterns, and conventions.
- Prefer the smallest correct change.
- Do not expand scope or perform unrelated refactoring.
- Do not silently change architectural decisions from the plan.
- If implementation reveals a material flaw in the task or plan, stop and report it.

## Tests

- Add or update tests required by the task.
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

Keep the completion summary concise; do not repeat the task or provide implementation narrative.
