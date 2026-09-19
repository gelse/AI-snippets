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

## Completion

Finish with `attempt_completion` and report only:
- implementation result
- relevant files changed
- tests added or changed
- blockers or deviations

Keep the completion summary concise; do not repeat the task or provide implementation narrative.