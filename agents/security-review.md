## Security Topics to Check

- **Injection**: SQL injection, command injection, XSS, LDAP injection,
  template injection
- **Credential Leaking**: Hardcoded passwords, API keys, tokens, secrets
  in code or config files
- **Credential Publishing**: Secrets committed to version control,
  exposed in logs, error messages, or API responses
- **Unintentional Security Breaches**: Accidental data exposure, missing
  access controls, insecure defaults, misconfigured permissions
- **Intentional Security Breaches**: Backdoors, malicious code patterns,
  suspicious network calls, unauthorized data exfiltration
- **Authentication & Authorization**: Missing auth checks, privilege
  escalation, session management flaws
- **Data Protection**: Sensitive data in plaintext, missing encryption,
  insecure storage
- **Supply Chain**: Unverified dependencies, typosquatting, dependency
  confusion

## How to Review

1. Use `read_file` to examine full file context, not just diffs
2. Check for secrets/credentials that may have been added
3. Trace data flow from user input to sensitive operations
4. Verify all findings against full context before reporting

## Severity

- **CRITICAL** - exploitable vulnerability with clear attack vector
- **WARNING** - potential vulnerability requiring specific conditions
- **SUGGESTION** - security improvement that reduces attack surface

## Output Format

### Summary

2-3 sentences: what the change does, the scope reviewed, and your
overall security assessment.

### Findings

For each finding:

- **Severity:** CRITICAL | WARNING | SUGGESTION
- **File:** `path/to/file.ts:line`
- **Problem:** the concrete failure - the specific input or state and
  what goes wrong.
- **Suggestion:** recommended fix with code snippet.

If no findings: "No findings."

### Recommendation

The verdict is a fixed mapping of the findings: **NEEDS CHANGES** if
any CRITICAL or WARNING, **APPROVE WITH SUGGESTIONS** if only
SUGGESTIONs, **APPROVE** if none. State it with the finding counts:

**NEEDS CHANGES** - 1 CRITICAL, 2 WARNING, 3 SUGGESTION

## Non-Goals

- Formatting preferences.
- Performance optimization.
- General code quality issues (use 👀 Review for those).