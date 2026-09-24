---
name: bugfix
description: Defect or broken behavior — reproduction test first, then fix, then verification.
modeSlugs:
  - lieutenant
---

# Bugfix

Defect or broken behavior — a reproduction test is required before the fix, then verification.

## Workflow

`code (failing reproduction test first → fix → nested verify) → final verify`

1. Dispatch `code` with the defect description and relevant evidence.
2. `code` writes a failing reproduction test first.
3. `code` applies the minimal fix, then runs nested verify.
4. Dispatch a final end-to-end `verify`.

## Type-Specific Rules

- Reproduction test must fail before the fix and pass after.
- Minimal fix — no unrelated refactoring.

## Failure Recovery

| Situation | Action |
|-----------|--------|
| Obvious failure at final verify or nested gate | `code → verify` |
| Unclear failure at final verify or nested gate | `verify` |
| Verify finds implementation cause at final verify or nested gate | `code → verify` |
| Verify finds design issue or task outgrows scope at final verify or nested gate | Report to captain for re-classification |
