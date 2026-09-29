---
name: documentation
description: Create, update, or correct prose documents — including existing docs gone stale against the code — under README.md and docs/.
modeSlugs:
  - lieutenant
---

# Documentation

Prose documents that explain the project to humans: `README.md` and everything under `docs/` — explainers, developer/contributor guides, how-tos, reference/FAQ. Covers creating new documents, updating existing ones, and correcting documents that went stale against the code. Out of scope: `CHANGELOG.md` and release notes (`release` owns those), milestone files under `plans/` (`architecture` owns those), in-source docstrings and code comments (a `code` concern).

## Workflow

`investigator → plan (conditional) → code (nested verify) → verify`

1. Dispatch `investigator` to ground the doc set in the code; it reports which claims each document must satisfy.
2. Dispatch `plan` only when the request spans new documents that need a shared structure agreed before anyone writes.
3. Dispatch `code` to write or update the Markdown applying the standard; `code` owns a nested verify checking every claim and link against the code.
4. Dispatch a final `verify` sweeping for cross-document inconsistency and stale content.

## Type-Specific Rules

- Every claim, code sample, command, link, and version reference is checked against the code before it ships.
- Updating stale docs is in scope — a document wrong against the code is a defect this skill fixes.
- Scope-out boundaries are binding: route `CHANGELOG.md` and release notes to `release`, milestone files under `plans/` to `architecture`, in-source docstrings and code comments to `code`.

## Standard

A document serves its reader when every unit — the section, paragraph, sentence, or code sample that carries one message — meets four criteria:

- **True** — every claim, code sample, command, link, and version reference checked against the code it describes. Wrong-but-elegant is the worst outcome: it spends a reader's trust.
- **Runnable** — the reader can act end to end: prerequisites, working directory, step order, expected result all stated; no step that only works if you already know the step you skipped.
- **Calibrated** — assumes exactly the reader profile: define what the profile lacks before use, leave out what it has. Inherited deliberately from `writing-for-humans` so the two standards do not drift.
- **Navigable** — the reader finds the fact they came for: the title promises the content, headings are scannable, cross-references land where the fact actually lives.

## Write

A gate on every document you produce:

1. **Fix the reader** — settle from the task the reader profile: who reads this document, what they know, what they want to know.
2. Draft inverted: the fact the reader came for leads each unit; detail they may skip lives at the tail.
3. Grade every unit against all four criteria. Fails one? Rewrite until it passes, or cut.

**Completion criterion:** the reader profile is declared, and every unit of the delivered document passes all four criteria graded against it.

## Review

Scope is the set of documents the surrounding task is about. Inherit it from the task and declare it in the report's first line, together with the reader profile the grading uses. The inventory is exhaustive over the declared scope: no sampling.

Classify every unit by the **first** bucket it fails:

1. **INACCURATE** — fails True: a claim, sample, command, link, or version reference does not match the code it describes.
2. **UNRUNNABLE** — fails Runnable: the reader cannot act end to end.
3. **MISCALIBRATED** — fails Calibrated: the unit leans on knowledge the profile lacks, or re-explains what the profile has.
4. **UNFINDABLE** — fails Navigable: the reader cannot find the fact they came for.
5. **KEEP** — fails none.

A **finding** is any non-KEEP bucket; KEEP units are counted, not reported.

1. Build the inventory: every unit in scope, at paragraph granularity. State the total.
2. Classify each unit into exactly one bucket with a one-clause reason naming the criterion it betrays.
3. Give every finding a disposition: replacement text meeting the standard, or delete.

**Completion criterion:** every unit carries exactly one bucket and a one-clause reason, every finding carries a disposition, and the per-bucket counts sum to the inventory total.

### Default rendering

- Open with `Reader: …` and `Scope: …`.
- Per file or section, one entry per finding: `location` — bucket — short quote — problem — proposed rewrite (or "delete").
- Close with `Total: N units in scope`, per-bucket counts, and a statement that the counts sum to the total.
- Clean files get one "clean" line.

## Failure Recovery

| Situation | Action |
|-----------|--------|
| Obvious failure at final verify or nested gate | `code → verify` |
| Unclear failure at final verify or nested gate | `verify` |
| Verify finds an inaccuracy or broken reference at final verify or nested gate | `code → verify` |
| Verify finds design issue or task outgrows scope at final verify or nested gate | Report to captain for re-classification |
