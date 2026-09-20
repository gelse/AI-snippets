---
name: small-feature
description: Single, contained, obvious change implemented in one code dispatch with mandatory unit tests.
modeSlugs:
  - orchestrator
---

# Small Feature

Single, contained, obvious change — one file or a few files; no design ambiguity, no investigation or planning phase.

## Workflow

`code (nested verify; unit tests required; nested review-code when risky or externally visible)`

1. Dispatch `code` with the exact scope and acceptance criteria.
2. `code` creates or extends unit tests for changed behavior (mandatory).
3. `code` owns nested verify and, when the change is risky or externally visible, nested review-code.

## Type-Specific Rules

- Single code dispatch — no investigator or plan dispatch.
- Unit tests are mandatory via the Implementation dispatch contract.
- Do not dispatch investigator or plan for this task type.

## Failure Recovery

| Situation | Action |
|-----------|--------|
| Obvious failure at final verify or nested gate | `code → verify` |
| Unclear failure at final verify or nested gate | `verify` |
| Verify finds implementation cause at final verify or nested gate | `code → verify` |
| Verify finds design issue or task outgrows scope at final verify or nested gate | Report to captain for re-classification |
