---
name: writing-for-humans
description: Use when writing or editing prose artifacts meant for human readers — documentation, READMEs, reports, release notes, commit messages, wiki pages, specs, emails.
---

# Writing for Humans

One standard for every prose artifact a human reads, judged from one vantage: the **reader as they actually read**.

## The reader

Four facts, true of every human reader of every artifact:

- **Decides before reading** — judges the first few words, then invests only if they pay.
- **Carries only their own head** — none of the writer's context, none of the project's history.
- **Tracks one thread at a time.**
- **Pays per sentence** — every unit the text spends is billed to the reader's attention.

## The standard

A text earns its reader's attention when it serves the reader facts. A **unit** is any piece that carries a message — the text, a section, a paragraph, a sentence. Four criteria, each grounded in one reader fact, applied at every level:

- **Inverted pyramid** — the message leads the unit; what follows descends in importance, so a reader who stops early has already received the message.
- **Calibrated** — assumes exactly the reader's head: what the reader lacks is defined before use; what the reader already has stays out.
- **One message** — one message per unit, stated in the unit's first sentence; every sentence advances that message by cause, contrast, consequence, or refinement.
- **Load-bearing** — every unit earns its place: a unit the reader does not need bills attention for nothing.

The criteria grade against the **reader profile**: who this text's reader is, what they already know, and what they want to know.

## Write

A gate on every prose artifact you produce:

1. **Fix the reader** — settle from the task the reader profile: who reads this, what they know, what they want to know. The profile is the bar Calibrated grades against, and what Inverted pyramid ranks by: the reader's want decides what leads.
2. Draft inverted: front-load the message, order the rest by descending importance — detail the reader may skip lives at the tail.
3. Read the draft as the fixed reader. Fails a criterion? Rewrite until it passes, or cut.

**Completion criterion:** the reader profile is declared, and every unit of the delivered artifact passes all four criteria graded against it.

## Review

Scope is the set of units the surrounding task is about — the artifact just written, named files, a section. Inherit it from the task; where the task leaves it ambiguous, use your judgment and declare it in the report's first line, together with the reader profile the grading uses. The inventory is exhaustive over the declared scope: no sampling.

Classify every unit by the **first** bucket it fails:

1. **BURIED** — fails Inverted pyramid: the unit's message sits behind its lead-in.
2. **MISCALIBRATED** — fails Calibrated: the unit leans on knowledge the profile lacks, or re-explains what the profile has.
3. **SPLIT** — fails One message: the unit carries more than one message, states it past its first sentence, or holds a sentence that does not advance it.
4. **DEADWEIGHT** — fails Load-bearing: the unit bills attention for nothing the profile needs.
5. **KEEP** — fails none.

A **finding** is any unit bucketed BURIED, MISCALIBRATED, SPLIT or DEADWEIGHT; KEEP units are counted, not reported.

1. Build the inventory: every unit in scope, at paragraph granularity; an artifact shorter than a paragraph (a commit message, a tagline) inventories sentence by sentence. State the total.
2. Classify each unit into exactly one bucket by the ordered buckets above, with a one-clause reason naming the reader fact it betrays.
3. Give every finding a disposition: replacement text that meets the standard, or delete.

**Completion criterion:** every unit in the declared scope carries exactly one bucket and a one-clause reason, every finding carries a disposition, and the per-bucket counts sum to the inventory total.

The report is the deliverable; apply fixes only when the task asks.

### Default rendering

Use this unless the task dictates its own format:

- Open with `Reader: …` and `Scope: …`.
- Per file or section, one entry per finding: `location` — bucket — short quote — problem — proposed rewrite (or "delete").
- Close with `Total: N units in scope`, per-bucket counts, and a statement that the bucket counts sum to the total.
- Clean files get one "clean" line.
