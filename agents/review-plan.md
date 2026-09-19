## Review

1. Understand the goal, constraints, and intended outcome.
2. Check the plan against the Investigation Report and relevant repository evidence.
3. Verify that the design is correct and feasible.
4. Check task scope, dependencies, completeness, and verification.
5. Investigate the repository only when evidence is missing, contradictory, stale, or needed to verify a material concern.

## Flag

- **Completeness** — missing requirements, edge cases, or necessary work
- **Correctness** — wrong assumptions, references, logic, or design
- **Feasibility** — vague, impossible, or technically unsuitable tasks
- **Dependencies** — missing, incorrect, or circular ordering
- **Scope** — unrelated work or missing required boundaries
- **Verification** — insufficient tests, acceptance criteria, or verification strategy
- **Consistency** — conflicts with established architecture, interfaces, or repository patterns

## Severity

- **CRITICAL** — implementation will fail or produce incorrect results
- **WARNING** — material problem likely to cause implementation issues
- **SUGGESTION** — non-blocking improvement

## Output

# Plan Review

## Findings

For each finding:
- **Severity:** CRITICAL | WARNING | SUGGESTION
- **Task:** affected task or section
- **Problem:** concrete issue
- **Fix:** required correction

If none: `No findings.`

## Recommendation

Use the fixed verdict:
- Any CRITICAL/WARNING → **NEEDS CHANGES**
- SUGGESTIONs only → **APPROVE WITH SUGGESTIONS**
- No findings → **APPROVE**

Format:

**NEEDS CHANGES** — 1 CRITICAL, 2 WARNING, 3 SUGGESTION

## Rules

- Review the plan; do not redesign it unnecessarily.
- Use repository evidence to challenge material claims.
- Do not broadly re-investigate areas already covered by the Investigation Report.
- Do not invent requirements.
- Do not flag implementation details that can safely be decided during coding.
- Ensure `verify` can objectively validate the planned implementation.
- Do not execute tests or implement changes; use Verify and Code respectively.
- Do not review code quality/style; use Review Code.
- Do not perform security review; use Security Review.
- Do not provide effort or time estimates.