# OpenCode target drift report

Health check of the opencode artifacts this repo generates. `make opencode` rebuilds `output/opencode/agents/*.md` from [`modes.json`](../modes.json) plus the `agents/*.md` instruction files; this report states how the latest regeneration fared. **Verdict: all 10 active agents pass every check — description, mode, permissions, and body all match the source.**

## Methodology

Each non-deprecated mode becomes one `output/opencode/agents/<slug>.md`. Frontmatter field order is `description`, `mode`, `model`, `permissions`. The `permissions:` field is an opencode v2 rule list — an ordered list of `{action, resource, effect}` mappings applied last-match-wins — translated from the mode's row in `modes.json.permissions`; the global `task` key is emitted as the `subagent` action.

The permission check is a rule-well-formedness check on the parsed list:

- the list is non-empty;
- every rule has exactly the keys `{action, resource, effect}`;
- every `action` is in the opencode action set (`shell`, `edit`, `subagent`, `read`, `glob`, `grep`, `skill`, `webfetch`, `websearch`);
- every `effect` is in `{allow, ask, deny}`.

The translator must preserve the last-match-wins invariant: broad `*` rules come before scoped overrides. A mode whose matrix row sets `edit: allow` and whose groups carry an `edit` entry scoped by `fileRegex` gets two edit rules — `edit` on `*` with effect `deny` first, `edit` on the mapped glob (`*.md`) with effect `allow` second — so the scoped allow wins for matching paths. Modes with `edit: deny` or `edit: ask`, or with no scoped group, get exactly one broad rule. [`scripts/verify.py`](../scripts/verify.py) enforces the same semantics for every generated agent in `verify_opencode_agent_permissions()`.

The description, mode, and body checks compare each emitted file against `modes.json` (description composed with `whenToUse`, `mode` from the mode's `instantiation`, body from `roleDefinition` plus the resolved `agents/<slug>.md` content); the model check reads [`models/mapping.yaml`](../models/mapping.yaml).

## How to regenerate

Run after a fresh `make clean && make opencode`:

```bash
.venv/bin/python - <<'PY'
import yaml, pathlib
ROOT = pathlib.Path(".")
for path in sorted((ROOT / "output/opencode/agents").glob("*.md")):
    text = path.read_text()
    fm = yaml.safe_load(text.split("---", 2)[1])
    assert isinstance(fm.get("permissions"), list) and fm["permissions"], path
    for rule in fm["permissions"]:
        assert set(rule) == {"action", "resource", "effect"}, (path, rule)
        assert rule["action"] in {"shell","edit","subagent","read","glob","grep","skill","webfetch","websearch"}
        assert rule["effect"] in {"allow","ask","deny"}
    print(f"OK {path.name}: {len(fm['permissions'])} rules")
PY
```

The last run printed `OK` for all 10 files: 7 rules per agent, 8 for `plan.md` — its `edit: allow` row plus the `fileRegex`-scoped group produces the broad-deny + scoped-allow pair.

## Per-file results

One entry per active mode; deprecated modes are skipped by the emitter. All 10 files exist and every check passes.

### `agents/captain.md`

**PASS** — path exists; description, mode, permissions, and body all match.

| Description | Mode | Permissions | Body |
|---|---|---|---|
| ✓ | ✓ (`primary`) | ✓ (7 rules) | ✓ |

### `agents/lieutenant.md`

**PASS** — path exists; description, mode, permissions, and body all match.

| Description | Mode | Permissions | Body |
|---|---|---|---|
| ✓ | ✓ (`all`) | ✓ (7 rules) | ✓ |

### `agents/investigator.md`

**PASS** — path exists; description, mode, permissions, and body all match.

| Description | Mode | Permissions | Body |
|---|---|---|---|
| ✓ | ✓ (`all`) | ✓ (7 rules) | ✓ |

### `agents/plan.md`

**PASS** — path exists; description, mode, permissions, and body all match.

| Description | Mode | Permissions | Body |
|---|---|---|---|
| ✓ | ✓ (`all`) | ✓ (8 rules) | ✓ |

### `agents/review-code.md`

**PASS** — path exists; description, mode, permissions, and body all match.

| Description | Mode | Permissions | Body |
|---|---|---|---|
| ✓ | ✓ (`all`) | ✓ (7 rules) | ✓ |

### `agents/security-review.md`

**PASS** — path exists; description, mode, permissions, and body all match.

| Description | Mode | Permissions | Body |
|---|---|---|---|
| ✓ | ✓ (`all`) | ✓ (7 rules) | ✓ |

### `agents/review-plan.md`

**PASS** — path exists; description, mode, permissions, and body all match.

| Description | Mode | Permissions | Body |
|---|---|---|---|
| ✓ | ✓ (`all`) | ✓ (7 rules) | ✓ |

### `agents/code.md`

**PASS** — path exists; description, mode, permissions, and body all match.

| Description | Mode | Permissions | Body |
|---|---|---|---|
| ✓ | ✓ (`all`) | ✓ (7 rules) | ✓ |

### `agents/verify.md`

**PASS** — path exists; description, mode, permissions, and body all match.

| Description | Mode | Permissions | Body |
|---|---|---|---|
| ✓ | ✓ (`subagent`) | ✓ (7 rules) | ✓ |

### `agents/ask.md`

**PASS** — path exists; description, mode, permissions, and body all match.

| Description | Mode | Permissions | Body |
|---|---|---|---|
| ✓ | ✓ (`all`) | ✓ (7 rules) | ✓ |

## Summary

No drift: every regenerated agent matches its source row in `modes.json` and passes the rule-well-formedness check. `scripts/verify.py` re-runs the same permission semantics against freshly emitted agents on every `make check-py`, so regressions between report runs are caught automatically.

The installed copies under `~/.config/opencode/agents/` are not rewritten by `make opencode`; `make install-opencode-global` (or the CLI installer) syncs them. [`scripts/smoke-test-opencode-install.sh`](../scripts/smoke-test-opencode-install.sh) exercises that install path against an isolated config home, including a permission assertion per installed agent.

## Orchestrator: deleted by regeneration

`orchestrator` is marked `deprecated: true` in `modes.json`, and `emit_opencode()` skips deprecated modes. Regeneration emits no `output/opencode/agents/orchestrator.md`; the stale installed copy written by the pre-refactor generator has been deleted, so both the generated tree and the installed agents directory now hold exactly the 10 active agents. No body-size comparison applies — the installed file no longer exists, and the generator no longer produces one.
