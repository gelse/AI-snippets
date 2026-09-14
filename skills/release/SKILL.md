---
name: release
description: Release the testing branch end-to-end — version bump, changelog, PRs to testing and main, and a GitHub release tagged on main.
modeSlugs:
  - orchestrator
argument-hint: "[version]"
---

# Release

Release the testing branch; releases are always tagged on main. All git/gh commands run in the target repo root.

**Invocation:** `release.py` lives beside this SKILL.md. Run it with `.venv/bin/python skills/release/release.py` from the target repo root (tomllib requires Python ≥ 3.11). A Node.js alternative `release.mjs` ships alongside with identical CLI semantics — run it with `node skills/release/release.mjs <subcommand>` (Node.js ≥ 18, zero dependencies). If neither script is available (missing venv/Python < 3.11, no Node.js, or not shipped), run the manual fallback in section 7.

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

## 7. Fallback: no release.py

If `release.py` cannot run — missing venv, Python < 3.11, script not shipped — execute each subcommand manually with the equivalent commands below. All commands run in the target repo root.

### Critical invariants

- Tag **ALWAYS** `vX.Y.Z` on `origin/main` HEAD — never on testing.
- Never overwrite an existing tag or release.
- Never tag before the promotion PR is merged.
- `pyproject.toml` version **must match** the tag.

### Manual commands by subcommand

**preflight** `[--version X]`

```sh
test -z "$(git status --porcelain)"                         # clean tree
test "$(git branch --show-current)" = "testing"             # on testing
git fetch --all --tags
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/testing)" # HEAD == origin/testing
git rev-parse origin/main                                   # origin/main exists
git merge-base --is-ancestor origin/main origin/testing     # main ancestor of testing
git tag -l 'v[0-9]*.[0-9]*.[0-9]*'                         # list release tags
```

If `--version X` given, additionally:

```sh
git tag -l vX.Y.Z                                      # must be empty
git ls-remote --tags origin vX.Y.Z                      # must be empty
gh release view vX.Y.Z                                 # must fail
grep '^version' pyproject.toml                          # read current version
```

**changes** `[--base TAG]`

```sh
git log TAG..HEAD --oneline --no-decorate               # commits since last tag (omit range for first release)
gh pr list --state merged --base testing --json number,title  # merged PRs for changelog draft
```

**check-version** `--version X.Y.Z`

```sh
# X.Y.Z must be strictly greater than last tag (version-tuple compare)
git tag -l 'v[0-9]*.[0-9]*.[0-9]*' | sort -V | tail -1 # last tag
# Tag must be absent from remote:
git ls-remote --tags origin vX.Y.Z                      # must be empty
```

**finalize** `--version X --notes FILE`

```sh
git fetch origin
git merge-base --is-ancestor origin/testing origin/main # testing contained in main
git diff --quiet HEAD                                   # clean tree
git checkout main && git pull --ff-only
grep '^version' pyproject.toml                          # must match vX.Y.Z
TARGET=$(git rev-parse origin/main)
git tag -a vX.Y.Z "$TARGET" -m "Release vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z --target "$TARGET" --title "Release vX.Y.Z" --notes-file FILE
```

**post-verify** `--version X`

```sh
git fetch origin
# Tag (peeled) must point at origin/main HEAD:
test "$(git ls-remote origin "refs/tags/vX.Y.Z^{}" | cut -f1)" = "$(git rev-parse origin/main)"
git merge-base --is-ancestor origin/testing origin/main # testing in main
gh release view vX.Y.Z                                 # must succeed
test "$(git branch --show-current)" = "main"            # on main
test -z "$(git status --porcelain)"                     # clean tree
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" # HEAD == origin/main
```

## Rules

- Testing is the release source; main is the release target — releases are ALWAYS tagged on main, never on testing.
- Never overwrite an existing tag or release.
- Tagged commit = main HEAD after the testing→main promotion PR merge; main must contain testing HEAD.
- Never tag before the promotion PR is merged.
- Use `gh` for GitHub, `git` locally.
- Versions normalized: tags always `vX.Y.Z`.
- Stop on any inconsistency once anything is published.
- **Do not merge the release PR or the promotion PR yourself — the user merges both.**
