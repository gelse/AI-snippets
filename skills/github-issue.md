---
name: github-issue
description: Solve a GitHub issue through orchestrated planning, implementation, verification, and pull-request creation.
modeSlugs:
  - orchestrator
argument-hint: issue-number
---

# GitHub Issue

Solve the specified GitHub issue completely and create a pull request.

## 1. Retrieve and Validate

Use `gh` for all GitHub operations.

Retrieve the specified issue from GitHub.

Read the issue, relevant comments, labels, and referenced issues/PRs as needed.

Determine whether the issue is sufficiently clear to implement.

If material ambiguity remains:

- stop immediately
- do not modify the repository
- report what is unclear and why
- do not guess requirements

Do not modify GitHub issue state unless explicitly required.

## 2. Create Feature Branch

After the issue is validated, create a dedicated feature branch for the issue.

Use a clear branch name that references the issue.

Do not implement changes before the feature branch exists.

## 3. Plan

Delegate the complete planning phase to `plan`.

The planner must investigate the repository, resolve relevant uncertainties, design the solution, and decompose it into ordered, implementation-ready tasks.

The planner is **strictly read-only** and must not modify the repository.

The returned plan is authoritative for implementation.

After the planner produces a plan, the orchestrator automatically reviews it using `review-plan`. If CRITICAL or WARNING findings are found, the plan is revised and re-reviewed until approved.

If the planner or reviewer identifies material ambiguity that cannot be resolved from available information, stop and escalate to the user.

## 4. Implement

Execute the planned tasks sequentially in dependency order.

For each task, delegate to `code` with only the context required for that task.

Require the task's definition of done and verification criteria to be satisfied before proceeding.

After each task completes, the orchestrator automatically dispatches `review-code` to review only the changes made by that task. If CRITICAL or WARNING findings are found, execution pauses and the user is escalated for guidance. Do not proceed to the next task until the user responds.

If implementation reveals that the plan is incomplete or incorrect:

1. stop the affected task
2. delegate reassessment to `plan`
3. update the plan
4. resume implementation only after the revised plan is accepted

Do not let a code agent silently redefine the solution or scope.

## 5. Verify

After all implementation tasks pass their individual code reviews, delegate final verification to `code`.

Verify:

- the issue is solved
- all acceptance criteria are satisfied
- relevant tests pass
- required tests exist
- the complete change integrates correctly
- no unnecessary or unrelated changes were introduced

For failures:

- let `code` fix straightforward, in-scope failures
- use `debug` for non-obvious failures
- return to `plan` if the solution itself is incorrect or incomplete
- escalate to the user when a decision cannot be resolved autonomously

Re-verify after every fix.

Do not repeatedly retry the same failed approach.

## 6. Commit, Push, and Create PR

Only after successful verification:

1. Review the complete diff.
2. Commit the implementation to the feature branch.
3. Push the branch to GitHub.
4. Create a pull request with `gh`.

The PR should:

- reference the GitHub issue
- briefly describe the implemented solution
- summarize relevant tests and verification
- mention relevant limitations or known issues

Do not modify or close the issue itself unless explicitly requested.

## 7. Report

Report only the final result:

- issue number and title
- feature branch
- implementation summary
- tests and verification
- commit
- pull request
- remaining limitations or known issues

Do not reproduce intermediate planner or agent reports.

## Rules

- Starting mode is always `orchestrator`.
- Use `gh` for GitHub operations.
- `planner` is strictly read-only.
- Implementation is delegated to `code`.
- `debug` is used only when diagnosis is needed.
- Keep changes within the issue's scope.
- Prefer the smallest correct implementation.
- Do not invent requirements.
- Do not perform unrelated refactoring.
- Do not modify GitHub issue state unless explicitly requested.
- Do not create the PR before successful verification.