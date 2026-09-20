---
name: full-feature
description: Multi-part, design-heavy work requiring investigation, planning, implementation, and verification.
modeSlugs:
  - orchestrator
---

# Full Feature

Multi-part, design-heavy work requiring investigation, planning, iterative code implementation, and final verification.

## Workflow

`investigator → plan (nested review-plan) → milestone files under plans/ → code per milestone (nested verify + review-code) → final verify`

1. Dispatch `investigator` with the user request and relevant constraints.
2. Dispatch `plan` with the investigation evidence; use the `grilling` skill when human input is needed. `plan` runs its nested `review-plan` loop and produces milestone files under `plans/`.
3. Dispatch `code` for each milestone file; `code` uses the milestone's `Verification` and `Non-goals` fields as its dispatch contract. `code` owns nested verify and review-code gates.
4. Dispatch a final end-to-end `verify` after all milestones are implemented.

## Type-Specific Rules

- Always use the `grilling` skill in plan dispatch when human input is needed.
- Milestone files use the milestone format defined in plan mode.
- Code dispatches are per milestone file — one `code` sub-task per file.
- Final end-to-end `verify` covers cross-task integration and regressions.

## Failure Recovery

| Situation | Action |
|-----------|--------|
| Unclear failure at final verify | `verify` |
| Verify finds implementation cause | `code → verify` |
| Verify finds design issue | targeted investigator → plan (nested review-plan) → re-dispatch code → verify |
| Plan review finds evidence gap | targeted investigator → plan (nested review-plan) → re-review |
