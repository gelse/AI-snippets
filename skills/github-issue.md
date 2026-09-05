---
name: github-issue
description: Resolve a GitHub issue end-to-end and open a PR.
modeSlugs:
  - orchestrator
argument-hint: issue-number
---

# GitHub Issue

Resolve the specified GitHub issue completely and open a pull request.

## 1. Retrieve and Validate

Use `gh` for all GitHub operations.

Retrieve the issue, its comments, labels, and referenced issues/PRs.

If material ambiguity remains, stop immediately — do not modify the repository, do not guess requirements, and report what is unclear.

Do not modify GitHub issue state unless explicitly required.

## 2. Create Feature Branch

After validation, create a feature branch referencing the issue.
Feature branch must start at the remote testing branch. Pull from remote if needed.

No implementation before the branch exists.

## 3. Execute standard workflow

Run the standard orchestrator workflow.

## 4. Commit, Push, and Create PR

After successful verification:

1. Review the complete diff.
2. Commit and push to the feature branch.
3. Create a PR to the testing branch with `gh`.

The PR must:

- reference the GitHub issue
- describe the implemented solution
- summarize tests and verification
- note limitations or known issues

Do not modify or close the issue unless explicitly requested.

## 5. Report

Report only the final result:

- issue number and title
- feature branch
- implementation summary
- tests and verification
- commit
- pull request
- limitations or known issues

## Rules

- Use `gh` for GitHub operations.
- Do not modify GitHub issue state unless explicitly requested.
- Keep changes within the issue's scope; prefer the smallest correct implementation.
- Do not invent requirements or perform unrelated refactoring.
- Do not create the PR before successful verification.
