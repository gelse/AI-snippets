# OpenCode target drift report

Comparison of the opencode workspace agents in `/home/werner/.config/opencode/agents/` against the source of truth in this repo (`modes.json` + `agents/*.md`), as of the current state of both trees.

**Methodology.** Frontmatter was parsed with `yaml.safe_load` on the block between the `---` delimiters and compared as parsed values (descriptions contain `": "` and may be YAML-quoted in the files). Body comparison resolves `customInstructions` from the repo's own `agents/<slug>.md` (not the workspace file) and mirrors the generator's fallback (`roleDefinition` alone when instructions are empty). Because the emitter writes `body + "\n"`, at most one file-final trailing newline was normalized on both sides before comparing. The `permission.edit: deny` check uses the same `has_edit_group` predicate as the generator. The `mode` check compares against `modes.json.instantiation`, defaulting to `"all"` when the field is absent.

## Per-file results

One line per non-deprecated mode; the four checks are description, mode, permission, body.

| Agent | Description | Mode | Permission | Body |
|---|---|---|---|---|
| `agents/captain.md` | ✓ | ✓ (`primary`) | ✓ | ✓ |
| `agents/lieutenant.md` | ✓ | ✓ (`all`) | ✓ | ✓ |
| `agents/investigator.md` | ✓ | ✓ (`all`) | ✓ | ✗ trailing newline |
| `agents/plan.md` | ✓ | ✓ (`all`) | ✓ | ✗ trailing newline |
| `agents/review-code.md` | ✓ | ✓ (`all`) | ✓ | ✗ trailing newline |
| `agents/security-review.md` | ✓ | ✓ (`all`) | ✓ | ✗ trailing newline |
| `agents/review-plan.md` | ✓ | ✓ (`all`) | ✓ | ✗ trailing newline |
| `agents/code.md` | ✓ | ✓ (`all`) | ✓ | ✓ |
| `agents/verify.md` | ✓ | ✓ (`subagent`) | ✓ | ✗ trailing newline |
| `agents/ask.md` | ✓ | ✓ (`all`) | ✓ | ✗ trailing newline |

All 10 workspace agent files exist. No description, mode, or permission drift anywhere.

## Summary

**Body — trailing newline only (7 files).** `investigator.md`, `plan.md`, `review-code.md`, `security-review.md`, `review-plan.md`, `verify.md`, `ask.md` differ from the regenerated body by exactly one trailing newline: the source `agents/<slug>.md` files in this repo end without a final newline, while the workspace files end with one (the emitter appends `"\n"`). The text content is otherwise byte-identical. `captain.md` and `code.md` match exactly because their source files do end with a newline.

**Description — none.** All 10 match `"{description} (Use when: {whenToUse})"` exactly.

**Mode — none.** All 10 match their `instantiation` value (`captain` → `primary`, `verify` → `subagent`, the rest → `all`).

**Permission — none.** `permission.edit: deny` is present exactly where `has_edit_group` is false, and absent everywhere else.

## Orchestrator: deleted by regeneration

`orchestrator` is marked `deprecated: true` in `modes.json` (with `groups: []`), and `emit_opencode()` skips deprecated modes. Regeneration would therefore **delete** `agents/orchestrator.md` from the workspace entirely — not shrink it. The distinction matters: no file is emitted for a deprecated mode, so the stale workspace copy is simply removed.

The stale workspace body is 8,078 characters. The body regeneration would produce from current source — `roleDefinition` plus the content of the repo's `agents/orchestrator.md` — is 154 characters. Neither body is ever written: the actual regeneration outcome is deletion of the file.

## Recommendation

Regenerate the workspace agents via `scripts/generate.py opencode --out /tmp/drift-check` and commit the result into `/home/werner/.config/opencode/agents/`: the only real drift is a cosmetic trailing-newline inconsistency caused by seven source agent files lacking a final newline, so fixing those seven source files (add a trailing newline) and re-emitting brings the workspace byte-identical to the generator output at near-zero cost, while options (b) and (c) either add machinery the drift does not justify or leave the newline inconsistency and the stale `orchestrator.md` in place.
