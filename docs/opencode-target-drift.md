# OpenCode target drift report

Health check of the opencode artifacts this repo generates. `make opencode` rebuilds `output/opencode/agents/*.md` from [`modes.json`](../modes.json) plus the `agents/*.md` instruction files; this report states how the latest regeneration fared. **Verdict: all 10 active agents pass every check — description, mode, permission, and body all match the source.**

## Methodology

Each non-deprecated mode becomes one `output/opencode/agents/<slug>.md`. Frontmatter field order is `description`, `mode`, `model`, `permission`. The `permission:` field is the opencode v1 permission map — action name to effect, or action name to per-command pattern map — translated from the mode's row in `modes.json.permissions`; the repo vocabulary keys `shell` and `task` are emitted under the runtime names `bash` and `task`, and `lsp`, `question`, `external_directory`, `doom_loop` are emitted verbatim.

The permission check is a map-well-formedness check on the parsed map:

- the map has exactly the keys `edit`, `bash`, `read`, `glob`, `grep`, `skill`, `task`, `lsp`, `question`, `external_directory`, `doom_loop`;
- every value is an effect in `{allow, ask, deny}` or a non-empty pattern map of non-empty string patterns to such effects;
- `question` and `doom_loop` hold scalar effects only — both are upstream `actionOnly`, and the generator raises `TypeError` on a pattern map there;
- the inert v2 `permissions` list is rejected wherever it appears.

The translator must preserve the last-match-wins invariant: broad `*` entries come before scoped overrides. A mode whose matrix row sets `edit: allow` and whose groups carry an `edit` entry scoped by `fileRegex` gets the edit map `{'*': 'deny', '*.md': 'allow'}` — broad deny first, scoped allow second — so the scoped allow wins for matching paths. Modes with `edit: deny` or `edit: ask`, or with no scoped group, get the scalar effect. `shell` pattern maps pass through in author order (`plan` and `review-code` put the broad `*` deny first, then their scoped allows), because the runtime applies map entries in order and keeps the last match — the order is policy and is never re-sorted. A `shell: auto` row (none present today) expands to the same shape: a catch-all `*` gate first (`ask` for `instantiation: primary` modes, `deny` otherwise), then bare and `cmd *` allows per read-only command from `SAFE_SHELL_COMMANDS` in [`scripts/generate.py`](../scripts/generate.py) (copied from the vendored [`scripts/reference/approve_readonly_bash.py`](../scripts/reference/approve_readonly_bash.py), which is kept for reference and not used directly). [`scripts/verify.py`](../scripts/verify.py) enforces the same semantics for every generated agent in `verify_opencode_agent_permissions()`.

The description, mode, and body checks compare each emitted file against `modes.json` and `harnesses.json` (description composed with `whenToUse`, `mode` from the mode's `instantiation`, body from `roleDefinition`, a `## Starting Subtasks` block whose paragraph text equals `"\n\n".join(harnesses.json["opencode"].subtaskInstructions)`, and the resolved `agents/<slug>.md` content — in that order); the model check reads [`models/mapping.yaml`](../models/mapping.yaml).

## How to regenerate

Run after a fresh `make clean && make opencode`:

```bash
.venv/bin/python - <<'PY'
import pathlib, yaml
KEYS = {"edit", "bash", "read", "glob", "grep", "skill", "task",
        "lsp", "question", "external_directory", "doom_loop"}
EFFECTS = {"allow", "ask", "deny"}
for path in sorted(pathlib.Path("output/opencode/agents").glob("*.md")):
    fm = yaml.safe_load(path.read_text().split("---", 2)[1])
    assert "permissions" not in fm, f"{path}: inert v2 permissions list"
    p = fm.get("permission")
    assert isinstance(p, dict) and set(p) == KEYS, f"{path}: key set"
    for k, v in p.items():
        if isinstance(v, dict):
            assert v and all(isinstance(pat, str) and pat and eff in EFFECTS
                             for pat, eff in v.items()), (path, k, v)
        else:
            assert v in EFFECTS, (path, k, v)
        if k in ("question", "doom_loop"):
            assert isinstance(v, str), (path, k)  # actionOnly: scalar only
    print(f"OK {path.name}: {len(p)} keys")
PY
```

The last run printed `OK` for all 10 files: 11 keys per agent. `plan.md` additionally carries the scoped `edit` map (`{'*': 'deny', '*.md': 'allow'}`) and an 11-entry `bash` pattern map (broad `*` deny first, then `ls`/`grep`/`curl`/`awk`/`head` allows); `review-code.md` carries a 9-entry `bash` pattern map (`*` deny first, then `git log`/`git show`/`git blame`/`git diff` allows).

## Per-file results

One entry per active mode; deprecated modes are skipped by the emitter. All 10 files exist and every check passes.

### `agents/captain.md`

**PASS** — path exists; description, mode, permission, and body all match.

| Description | Mode          | Permission  | Body |
| ----------- | ------------- | ----------- | ---- |
| ✓           | ✓ (`primary`) | ✓ (11 keys) | ✓    |

### `agents/lieutenant.md`

**PASS** — path exists; description, mode, permission, and body all match.

| Description | Mode      | Permission  | Body |
| ----------- | --------- | ----------- | ---- |
| ✓           | ✓ (`all`) | ✓ (11 keys) | ✓    |

### `agents/investigator.md`

**PASS** — path exists; description, mode, permission, and body all match.

| Description | Mode      | Permission  | Body |
| ----------- | --------- | ----------- | ---- |
| ✓           | ✓ (`all`) | ✓ (11 keys) | ✓    |

### `agents/plan.md`

**PASS** — path exists; description, mode, permission, and body all match.

| Description | Mode      | Permission                                           | Body |
| ----------- | --------- | ---------------------------------------------------- | ---- |
| ✓           | ✓ (`all`) | ✓ (11 keys; scoped `edit` map + 11-entry `bash` map) | ✓    |

### `agents/review-code.md`

**PASS** — path exists; description, mode, permission, and body all match.

| Description | Mode      | Permission                      | Body |
| ----------- | --------- | ------------------------------- | ---- |
| ✓           | ✓ (`all`) | ✓ (11 keys; 9-entry `bash` map) | ✓    |

### `agents/security-review.md`

**PASS** — path exists; description, mode, permission, and body all match.

| Description | Mode      | Permission  | Body |
| ----------- | --------- | ----------- | ---- |
| ✓           | ✓ (`all`) | ✓ (11 keys) | ✓    |

### `agents/review-plan.md`

**PASS** — path exists; description, mode, permission, and body all match.

| Description | Mode      | Permission  | Body |
| ----------- | --------- | ----------- | ---- |
| ✓           | ✓ (`all`) | ✓ (11 keys) | ✓    |

### `agents/code.md`

**PASS** — path exists; description, mode, permission, and body all match.

| Description | Mode      | Permission  | Body |
| ----------- | --------- | ----------- | ---- |
| ✓           | ✓ (`all`) | ✓ (11 keys) | ✓    |

### `agents/verify.md`

**PASS** — path exists; description, mode, permission, and body all match.

| Description | Mode           | Permission  | Body |
| ----------- | -------------- | ----------- | ---- |
| ✓           | ✓ (`subagent`) | ✓ (11 keys) | ✓    |

### `agents/ask.md`

**PASS** — path exists; description, mode, permission, and body all match.

| Description | Mode      | Permission  | Body |
| ----------- | --------- | ----------- | ---- |
| ✓           | ✓ (`all`) | ✓ (11 keys) | ✓    |

## Summary

No drift: every regenerated agent matches its source row in `modes.json` and passes the map-well-formedness check. `scripts/verify.py` re-runs the same permission semantics against freshly emitted agents on every `make check-py`, so regressions between report runs are caught automatically.

The installed copies under `~/.config/opencode/agents/` are not rewritten by `make opencode`; `make install-opencode-global` (or the CLI installer) syncs them. [`scripts/smoke-test-opencode-install.sh`](../scripts/smoke-test-opencode-install.sh) exercises that install path against an isolated config home, including a v1 `permission` map assertion per installed agent.

## Orchestrator: deleted by regeneration

`orchestrator` is marked `deprecated: true` in `modes.json`, and `emit_opencode()` skips deprecated modes. Regeneration emits no `output/opencode/agents/orchestrator.md`; the stale installed copy written by the pre-refactor generator has been deleted, so both the generated tree and the installed agents directory now hold exactly the 10 active agents. No body-size comparison applies — the installed file no longer exists, and the generator no longer produces one.
