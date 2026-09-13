---
name: release
description: Release the testing branch end-to-end — version bump, changelog, PRs to testing and main, and a GitHub release tagged on main.
modeSlugs:
  - orchestrator
argument-hint: "[version]"
---

# Release

Release the testing branch; releases are always tagged on main. All git/gh commands run in the target repo root.

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

## 4. Merge release PR (User)

**⏸ PAUSE GATE 2:** Present two options:
- "Merge successful, continue"
- "I have troubles, help me with: …"

**On trouble:** Diagnose with `git`/`gh` (CI logs via `gh pr checks`, PR state). Assist but do not tag.

**On success:** Continue to promote.

## 5. Promote (testing → main)

1. Create promotion PR: `gh pr create --base main --head testing` with title "Promote testing to main for v\<version\>" and body referencing the release PR.
2. **⏸ PAUSE GATE 3:** Present two options:
   - "Merge successful, continue"
   - "I have troubles, help me with: …"

**On trouble:** Diagnose with `git`/`gh` but do not tag. The promotion PR must be merged before finalizing.

**On success:** Continue to finalize.

## 6. Finalize

1. Run `release.py finalize --version X --notes FILE`.
2. Run `release.py post-verify --version X`.
3. Report: version, tagged commit, tag, release URL, included changes, verification performed, limitations.

## Rules

- Testing is the release source; main is the release target — releases are ALWAYS tagged on main, never on testing.
- Never overwrite an existing tag or release.
- Tagged commit = main HEAD after the testing→main promotion PR merge; main must contain testing HEAD.
- Never tag before the promotion PR is merged.
- Use `gh` for GitHub, `git` locally.
- Versions normalized: tags always `vX.Y.Z`.
- Stop on any inconsistency once anything is published.
- **Do not merge the release PR or the promotion PR yourself — the user merges both.**
