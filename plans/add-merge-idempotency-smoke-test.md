# Add slug-uniqueness regression gate to smoke test

## Goal

Add a regression gate to [`scripts/smoke-test.sh`](scripts/smoke-test.sh) that would have caught the merge-duplication defect.
The smoke test currently has no slug-uniqueness assertion.

## Changes

1. **Add `TMP_HOME6=""`** to the trap cleanup list and initializer block ([`scripts/smoke-test.sh:28–32`](scripts/smoke-test.sh:28)).

2. **New step** after Step 6 ([`scripts/smoke-test.sh:201`](scripts/smoke-test.sh:201)):
   `── 7. Merge idempotency: double install, no duplicate slugs ──`

   1. `TMP_HOME6="$(mktemp -d)"; mkdir -p "$TMP_HOME6/.roo"`.

   2. Pre-seed `$TMP_HOME6/.roo/custom_modes.yaml` with one foreign mode:

      ```yaml
      customModes:
      - slug: my-foreign-mode
        name: my-foreign-mode
        description: Foreign user mode for smoke test
        roleDefinition: You are a foreign test mode.
      ```

   3. Run `HOME="$TMP_HOME6" node "$CLI" install zoo --global --yes` twice, capturing the second run's output:

      ```bash
      OUTPUT2=$(HOME="$TMP_HOME6" node "$CLI" install zoo --global --yes 2>&1)
      ```

   4. Extract slugs:

      ```bash
      MODES_FILE="$TMP_HOME6/.roo/custom_modes.yaml"
      SLUGS=$(grep -E '^[[:space:]]*(- )?slug:' "$MODES_FILE" \
        | sed -E 's/^[[:space:]]*(- )?slug:[[:space:]]*//' | tr -d '"')
      ```

   5. Assertions (each with a distinct FAIL message, `exit 1`):

      | Check | Message |
      |-------|---------|
      | `SLUGS` line-count == 12 | Expected 12 slugs after double install |
      | `echo "$SLUGS" \| sort \| uniq -d` is empty | Duplicate slugs detected after double install |
      | `grep -qx 'my-foreign-mode'` in `SLUGS` | Foreign mode `my-foreign-mode` missing from modes file |
      | `OUTPUT2` contains `Kept user slugs: my-foreign-mode` | Kept-user-slugs line missing foreign mode |
      | `Replaced slugs:` line exists in `OUTPUT2` and does NOT contain `my-foreign-mode` | Foreign mode incorrectly listed as replaced |

3. **Update header comment list** ([`scripts/smoke-test.sh:5–12`](scripts/smoke-test.sh:5)) with:

   ```
   # - Double install into same HOME yields no duplicate slugs (merge idempotency)
   ```

## Dependencies

The merge fix ([fix-merge-duplication.md](fix-merge-duplication.md)) — on unfixed code the duplicate-count assertion fails, proving the gate works.

## Acceptance

- Full smoke test passes on fixed code with all 7 steps.
- `bash scripts/smoke-test.sh` → exit 0, prints "All smoke tests passed".

## Verification

```bash
bash scripts/smoke-test.sh
```

Third-install spot-check still yields 12 unique slugs (idempotent under N repetitions).

## Risks

Bash slug-extraction regex assumes block-mapping `slug:` keys — holds for both PyYAML and bundled `yaml` output.
Flow-style would break the regex (acceptable, guarded by this very test if the emitter changes).
