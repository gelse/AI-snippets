---
name: release
description: Release the current testing branch end-to-end — version bump, changelog, PR, and GitHub release.
modeSlugs:
  - orchestrator
argument-hint: "[version]"
---

# Release

Release the current testing branch. All git/gh commands run in the target repo root.

**Invocation:** `release.py` lives beside this SKILL.md. Run it with `.venv/bin/python skills/release/release.py` from the target repo root (tomllib requires Python ≥ 3.11).

## 1. Preflight

Run `release.py preflight [--version X]`. On failure: report and stop.

## 2. Propose

Run `release.py changes` to draft commit/PR summaries. From the draft, propose a version — use the argument if given, otherwise derive from the last tag and changelog content.

**⏸ PAUSE GATE 1:** Ask the user to confirm the proposed version and CHANGELOG section. Adjust or proceed on confirmation.

## 3. Prepare

1. Create release branch: `git checkout -b release/<version> origin/testing`
2. **Edit release files directly** (no code subtask): update `pyproject.toml` version and prepend the CHANGELOG.md section.
3. Run `release.py check-version --version X` to validate.
4. Delegate diff review to `review-code` (CRITICAL/WARNING findings must be fixed and re-reviewed).
5. Delegate test run to `verify`.
6. Push branch: `git push -u origin release/<version>`.
7. Create PR: `gh pr create --base testing --head release/<version>` with notes from the changelog draft.

## 4. Merge (User)

**⏸ PAUSE GATE 2:** Present two options:
- "Merge successful, continue"
- "I have troubles, help me with: …"

**On trouble:** Diagnose with `git`/`gh` (CI logs via `gh pr checks`, PR state). Assist but do not tag.

**On success:** Continue to finalize.

## 5. Finalize

1. Run `release.py finalize --version X --notes FILE`.
2. Run `release.py post-verify --version X`.
3. Report: version, tagged commit, tag, release URL, included changes, verification performed, limitations.

## Rules

- Testing is the release source; never release dirty or unsynced trees.
- Never overwrite an existing tag or release.
- Use `gh` for GitHub, `git` locally.
- Tagged commit = testing HEAD after PR merge.
- Versions normalized: tags always `vX.Y.Z`.
- Stop on any inconsistency once anything is published.
- **Do not merge the release PR yourself — the user merges.**
