# Fix stale-index splice in `mergeModesYaml()`

## Goal

Fix duplicate-entry corruption in [`mergeModesYaml()`](src/merge.ts:52) when re-installing generated modes.
Repeated installs duplicate generated slugs (11 → 17 with 5 duplicates: `investigator`, `review-code`, `review-plan`, `verify`, `architect`) while reporting all slugs as "replaced".

## Root cause

The splice loop at [`src/merge.ts:100–109`](src/merge.ts:100) uses indices from an `existingSlugs` Map captured before earlier splices. Each splice shifts remaining items, so later removals hit wrong positions.

## Changes

1. **Delete** the `existingSlugs` Map construction ([`src/merge.ts:87–94`](src/merge.ts:87)), the splice loop ([`100–109`](src/merge.ts:100)), and the `kept` loop over `existingSlugs` ([`112–114`](src/merge.ts:112)).

2. **Replace** with a single-pass filter plus file-order kept collection:

   ```ts
   // Remove existing entries whose slugs will be replaced by generated ones
   // (single pass — no stale indices; also removes pre-existing duplicates)
   seq.items = seq.items.filter((item) => {
     const slug = getSlugFromItem(item);
     if (slug !== null && generatedSlugs.has(slug)) {
       result.replaced.push(slug);
       return false;
     }
     return true;
   });

   // Track user entries that were kept (not in generated modes), in file order
   for (const item of seq.items) {
     const slug = getSlugFromItem(item);
     if (slug !== null) {
       result.kept.push(slug);
     }
   }
   ```

3. The `generatedSlugs` set ([`src/merge.ts:96`](src/merge.ts:96)) stays; the final append loop ([`117–123`](src/merge.ts:117)) and its `!result.replaced.includes(slug)` guard remain unchanged.

## Rationale

Predicate-based filter removes by content, not index — immune to shifting. YAMLSeq object identity is preserved so `String(doc)` serialization is unaffected.

Alternative (descending-index splice) rejected: it keeps the fragile index-map pattern.

## Dependencies

None.

## Acceptance

- Double install into a seeded `HOME` yields 12 slugs (11 generated + 1 foreign), no duplicates.
- `replaced` lists the 11 generated slugs.
- `kept` lists only foreign slugs.
- Foreign modes preserved in original order.

## Verification

```bash
npm run build && bash scripts/smoke-test.sh
```

(with new Step 7, separate file); manual slug count check 17 → 12.

## Post-fix guarantees

| Property | Guarantee |
|----------|-----------|
| Generated slugs | Each appears exactly once |
| Non-generated slugs | Preserved in original relative order |
| `replaced` | Contains all generated slugs |
| `kept` | Contains existing slugs not in generated set, in file order |
