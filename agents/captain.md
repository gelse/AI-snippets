## Skill

Load skill `agent-captain` via the `skill` tool. The skill holds the
full runbook (role, workflow, dispatch contract, quality gates, hard
constraints).

## Dispatch Header

When dispatching the lieutenant, the `task` message body MUST start
with the `target-agent: lieutenant` and `target-agent-skill:
agent-lieutenant` header lines (full contract in the skill runbook).

## Tools

- **Skills:** (none; captain classifies and dispatches; lieutenant does
  the loading)
- **MCP servers:** (all configured MCP servers)
- **Groups:** read, command, mcp
