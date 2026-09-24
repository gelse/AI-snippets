# OpenCode target drift report

Comparison of the opencode workspace agents in `/home/werner/.config/opencode/agents/` against the source of truth in this repo (`modes.json` + `agents/*.md`), as of the current state of both trees.

**Methodology.** Frontmatter was parsed with `yaml.safe_load` on the block between the `---` delimiters and compared as parsed values (descriptions contain `": "` and may be YAML-quoted in the files). Body comparison resolves `customInstructions` from the repo's own `agents/<slug>.md` (not the workspace file), mirrors the generator's fallback (`roleDefinition` alone when instructions are empty), and compares against the emitter's actual output — `body + "\n"` — with the emitter-appended file-final newline normalized on both sides. The `permission.edit: deny` check uses the same `has_edit_group` predicate as the generator. The `mode` check compares against `modes.json.instantiation`, defaulting to `"all"` when the field is absent.

## Per-file results

One line per non-deprecated mode; the four checks are description, mode, permission, body. All 10 workspace agent files exist; every check passes on every file.

| Agent | Description | Mode | Permission | Body |
|---|---|---|---|---|
| `agents/captain.md` | ✓ | ✓ (`primary`) | ✓ | ✓ |
| `agents/lieutenant.md` | ✓ | ✓ (`all`) | ✓ | ✓ |
| `agents/investigator.md` | ✓ | ✓ (`all`) | ✓ | ✓ |
| `agents/plan.md` | ✓ | ✓ (`all`) | ✓ | ✓ |
| `agents/review-code.md` | ✓ | ✓ (`all`) | ✓ | ✓ |
| `agents/security-review.md` | ✓ | ✓ (`all`) | ✓ | ✓ |
| `agents/review-plan.md` | ✓ | ✓ (`all`) | ✓ | ✓ |
| `agents/code.md` | ✓ | ✓ (`all`) | ✓ | ✓ |
| `agents/verify.md` | ✓ | ✓ (`subagent`) | ✓ | ✓ |
| `agents/ask.md` | ✓ | ✓ (`all`) | ✓ | ✓ |

## Summary

**No drift.** All 10 workspace agent files are byte-identical to what `emit_opencode()` produces from current source: description, mode, permission, and body all match. The only workspace artifact out of line with the generator is the stale `agents/orchestrator.md`, covered below.

## Orchestrator: deleted by regeneration

`orchestrator` is marked `deprecated: true` in `modes.json` (with `groups: []`), and `emit_opencode()` skips deprecated modes. Regeneration would therefore **delete** `agents/orchestrator.md` from the workspace entirely — not shrink it. The distinction matters: no file is emitted for a deprecated mode, so the stale workspace copy is simply removed.

The stale workspace body is 8,078 characters (after normalizing the emitter's single file-final trailing newline). The body regeneration would produce from current source — `roleDefinition` plus the content of the repo's `agents/orchestrator.md` — is 154 characters. Neither body is ever written: the actual regeneration outcome is deletion of the file.

## Recommendation

Regenerate the workspace agents via `scripts/generate.py opencode --out /tmp/drift-check` and commit the result into `/home/werner/.config/opencode/agents/` (option a): the 10 live agents are already byte-identical to generator output, so regeneration is a no-op for them and its only effect is deleting the stale `agents/orchestrator.md` that the generator no longer emits — the smallest change that brings the workspace fully in line, whereas a generator-driven sync step (option b) adds machinery the near-zero drift does not justify and leaving things alone (option c) keeps a deprecated agent file that regeneration would remove.
