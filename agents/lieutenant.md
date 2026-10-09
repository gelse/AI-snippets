## Skill

Load skill `agent-lieutenant` via the `skill` tool. The skill holds the
full runbook (role, workflow, dispatch contract, quality gates, hard
constraints).

## Dispatch Header

Every `task` dispatch — including every nested spawn — MUST start
with the `target-agent: <nested-slug>` and `target-agent-skill:
agent-<nested-slug>` header lines (full contract in the skill runbook).

## Tools

- **Skills:** full-feature, small-feature, architecture, bugfix,
  implementation-from-milestone, github-issue, release, grilling,
  writing-for-humans, documentation
- **MCP servers:** (all configured MCP servers)
- **Groups:** read, command, mcp
