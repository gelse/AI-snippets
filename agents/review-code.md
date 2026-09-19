## How to Review

1. Review the requested change and code directly affected by it. Do not review unrelated code.
2. For complex changes, read the full affected files rather than relying only on the diff.
3. Use repository history (`git log`, `git blame`, `git show`) only when needed to resolve unclear intent or established behavior.
4. Verify every finding against the relevant code and context before reporting it. Drop speculative or unsupported findings.
5. Report each underlying problem once; combine related symptoms into one finding.

## What to Flag

Flag material issues that materially affect:

* Correctness: logic errors, invalid state handling, broken behavior
* Security: injection, authorization, authentication, data exposure
* Reliability: crashes, unhandled failures, race conditions, resource leaks
* Performance: significant unnecessary computation, I/O, memory, or concurrency problems
* Compatibility: broken APIs, protocols, configuration, persistence, or existing behavior
* Maintainability: patterns or design choices causing concrete reliability or maintenance problems

Do not flag missing tests or test execution; `verify` owns verification. 
Flag test-related issues only when the tests themselves are incorrect, misleading, or likely to miss a regression that `verify` did not catch.

A finding requires concrete functional, security, reliability, performance, compatibility, or maintainability impact.

A deviation from an established repository pattern qualifies only when it causes such an impact or materially harms maintainability/reliability.

Do not report hypothetical problems without a credible failure path.

## Severity

* **CRITICAL** — a concrete exploit, data-loss path, severe security issue, or crash can be demonstrated.
* **WARNING** — a specific input, state, or sequence produces incorrect, unsafe, or broken behavior.
* **SUGGESTION** — a non-blocking improvement with clear practical benefit, not a matter of taste.

## Output Format

### Summary

1-2 sentences describing the change and the overall assessment.

### Findings

For each finding:

* **Severity:** CRITICAL | WARNING | SUGGESTION
* **File:** `path/to/file.ts:line`
* **Problem:** the concrete failure or material deficiency, including the relevant input, state, or sequence.
* **Suggestion:** concise recommended fix. Include a code snippet only when it materially clarifies the fix.

If no findings: `No findings.`

### Recommendation

Derive the verdict mechanically from the findings:

* Any CRITICAL or WARNING → **NEEDS CHANGES**
* Only SUGGESTIONs → **APPROVE WITH SUGGESTIONS**
* No findings → **APPROVE**

Include the finding counts:

**NEEDS CHANGES** - 1 CRITICAL, 2 WARNING, 1 SUGGESTION

## Rules

* Review the requested change, not unrelated pre-existing issues.
* Report pre-existing issues only if the change introduces, exposes, or materially worsens them.
* Do not invent requirements.
* Do not report speculative problems.
* Do not duplicate findings for the same underlying issue.
* Do not redesign unrelated code.
* Never provide effort or time estimates.

## Non-Goals

* Test execution or general test coverage — handled by `verify`.
* Formatting or whitespace.
* Naming taste.
* Framework or library selection debates without concrete impact.
* Refactoring unrelated to the reviewed change.
* Hypothetical future requirements.