---
name: implementation-from-milestone
description: Execute tasks directly from an approved or unreviewed milestone file under plans/.
modeSlugs:
  - orchestrator
---

# Implementation from Milestone

Execute tasks directly from a milestone file under `plans/`. Skip investigator/plan when the milestone is already reviewed; route through plan when it is not.

## Workflow

`code per task directly from plans/<milestone>.md → final verify`

1. If the milestone is not yet reviewed → dispatch `plan` with the existing milestone file (plan runs its nested review-plan loop).
2. If the milestone is approved → dispatch `code` for each task using the milestone's `Verification` and `Non-goals` fields as the dispatch contract.
3. If the milestone is flawed mid-implementation → targeted investigator → plan (nested review-plan) → re-dispatch code.
4. Dispatch a final end-to-end `verify` after all tasks.

## Type-Specific Rules

- Milestone format per plan mode.
- Code uses the milestone's `Verification` and `Non-goals` fields as its dispatch contract — no plan round-trip.
- Final end-to-end `verify` covers cross-task integration and regressions.

## Failure Recovery

| Situation | Action |
|-----------|--------|
| Obvious failure at final verify or nested gate | `code → verify` |
| Unclear failure at final verify or nested gate | `verify` |
| Verify finds implementation cause at final verify or nested gate | `code → verify` |
| Verify finds design issue at final verify or nested gate | targeted investigator → plan (nested review-plan) → re-dispatch code → verify |
