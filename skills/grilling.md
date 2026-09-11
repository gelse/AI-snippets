---
name: grilling
modeSlugs:
  - plan
  - review-plan
description: Use when the user wants to stress-test a plan, decision, or idea before building, or uses any 'grill' trigger phrase.
---

Interview the user relentlessly about every aspect of the plan, decision, or idea. Map it as a **design tree**: every decision branches into the decisions that hang off it.

The **frontier** is the set of decisions whose prerequisites are already settled: the questions you could ask now without guessing at answers you haven't heard yet. The frontier is your private working map, never shown to the user. A question whose answer depends on a question still open belongs to a later turn, not the frontier.

Ask exactly one question at a time — the most upstream frontier question — together with your recommended answer, then wait for the user's feedback before continuing. Each answer settles a decision and reshapes the tree: recompute the frontier before the next question.

Phrase every question to be intelligible on its own to the **user model**: your private picture of what this user already knows, seeded during the sweep and updated with each answer, never shown. The question's first sentence names the decision it puts to the user; any term or background the user hasn't demonstrated gets defined inside the question, and demonstrated knowledge goes unexplained. The user should be able to answer from the question alone — re-reading the plan is never a prerequisite for understanding what is being asked.

Spend the user's time efficiently: **sweep** first, ask second. Before the first question, sweep the environment for every fact the current frontier depends on, and keep sweeping uninterrupted until you can ask a run of questions back-to-back without pausing to look anything up. Finding facts is always your job, never the user's. Only when an answer opens a question whose facts are missing does a new sweep begin; then ask in runs again.

The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Confirm the shared understanding explicitly with the user before acting on it.
