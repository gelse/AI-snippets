---
name: architecture
description: Plan-only output producing milestone files under plans/ — no implementation dispatch.
modeSlugs:
  - lieutenant
---

# Architecture

Plan-only output — architecture design, feasibility study, or research. Produces milestone files under `plans/` without dispatching implementation.

## Workflow

`investigator → plan (nested review-plan) → milestone files under plans/`

1. Dispatch `investigator` with the user request and relevant constraints.
2. Dispatch `plan` with the investigation evidence; always use the `grilling` skill in plan dispatch. `plan` runs its nested `review-plan` loop and produces milestone files under `plans/`.
3. Completion = approved milestone files under `plans/`.

## Type-Specific Rules

- Always use the `grilling` skill in plan dispatch.
- Milestone format per plan mode.
- No implementation dispatch — completion is approved milestone files.

## Failure Recovery

| Situation | Action |
|-----------|--------|
| Plan review finds evidence gap | targeted investigator → plan (nested review-plan) → re-review |
