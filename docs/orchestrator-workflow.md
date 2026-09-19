# Orchestrator Workflow

This document covers the orchestrator work loop, the `github-issue` autonomous pipeline, and model-selection philosophy.

## The Orchestrator's Work Loop

The orchestrator mode never writes code itself. It acts as a strategic coordinator, delegating every concrete action to a specialized subtask and retaining only orchestration-level context. Any agent can now spawn nested sub-tasks via `new_task`, keeping review/verify context small by scoping it to individual tasks.

```mermaid
flowchart TD
    A["1. Investigate\nDispatch investigator subtask"] --> B["2. Plan\nDispatch plan subtask with report"]

    subgraph plan_loop["Plan (nested review loop)"]
        B --> C["Plan drafts plan"]
        C --> C1["Spawn nested review-plan"]
        C1 -->|Findings| C2["Revise plan"]
        C2 --> C1
        C1 -->|Approved| C3["Return approved plan + verdict"]
    end

    C3 --> E["3. Track\nMirror tasks into todo list"]
    E --> F["4. Dispatch code per task"]

    subgraph code_gate["Code task (nested gates)"]
        F --> F1["Implement task"]
        F1 --> F2["Spawn nested verify"]
        F2 -->|Fail| F3["Fix and re-verify"]
        F3 --> F2
        F2 -->|Pass| F4{"Risky/external?"}
        F4 -->|Yes| F5["Spawn nested review-code"]
        F5 -->|CRITICAL/WARNING| F6["Fix, re-verify, re-review"]
        F6 --> F5
        F5 -->|Clean| F7["Report gate results"]
        F4 -->|No| F7
    end

    F7 --> G{"More tasks?"}
    G -->|Yes| F
    G -->|No| K["5. Final verify\nDispatch verify subtask"]
    K -->|Fail| L["Failure handling tree"]
    L -->|Implementation cause| F
    L -->|Design cause| A
    L -->|Verify and fix| K
    K -->|Pass| M["6. Synthesize\nCollect summaries → report"]
```

### Step-by-step

| Step | Dispatched by | Mode(s) delegated to | Purpose |
|------|--------------|---------------------|---------|
| **Investigate** | orchestrator | `investigator` | Produce an investigation report with repository evidence, file references, and resolved open questions |
| **Plan** | orchestrator | `plan` | Use the investigation report to design solution, decompose into ordered implementation tasks |
| **Plan Review** | *plan (nested)* | `review-plan` | Plan spawns its own review loop; orchestrator receives only the approved plan + verdict |
| **Track** | orchestrator | *(internal)* | Mirror plan tasks into the todo list; respect dependency order |
| **Dispatch code** | orchestrator | `code` | Spawn a subtask per implementation task with scope, context, definition of done |
| **Per-task verify** | *code (nested)* | `verify` | Code spawns scoped verify for its task; fixes and re-runs until clean |
| **Per-task review** | *code (nested)* | `review-code` | For non-trivial/risky changes, code spawns scoped review; resolves findings before completing |
| **Final verify** | orchestrator | `verify` | End-to-end cross-task verification after all tasks complete |
| **Synthesize** | orchestrator | *(internal)* | Collect all subtask summaries into a final human-readable report |

### Mode State Diagram

The diagram below shows the workflow as states grouped per mode; `plan` and `code` own their nested review gates, while the orchestrator dispatches and routes between modes.

```mermaid
stateDiagram-v2
    state "orchestrator" as ORCH {
        [*] --> Investigate
        Investigate --> Dispatch_Plan
        Dispatch_Plan --> Track_Todos
        Track_Todos --> Dispatch_Code
        Dispatch_Code --> More_Tasks
        More_Tasks --> Dispatch_Code : more
        More_Tasks --> Final_Verify : done
        Final_Verify --> Synthesize : pass
        Final_Verify --> Failure : fail
        Failure --> Dispatch_Code : impl fix
        Failure --> Dispatch_Plan : design cause
        Failure --> Final_Verify : re-verify
        Synthesize --> [*]
    }

    state "investigator" as INV {
        Evidence --> Evidence_Done
        Evidence_Done --> [*]
    }

    state "plan" as PLAN {
        Draft --> Review_Loop
        Review_Loop --> Revise : findings
        Revise --> Review_Loop
        Review_Loop --> Plan_Approved : approved
        Plan_Approved --> [*]
    }

    state "review-plan" as REVIEW_PLAN {
        Review_Plan_Start --> RP_Check
        RP_Check --> RP_Done
        RP_Done --> [*]
    }

    state "code" as CODE {
        Implement --> Nested_Verify
        Nested_Verify --> Nested_Verify : fail
        Nested_Verify --> Check_Risky : pass
        Check_Risky --> Nested_Review : risky
        Check_Risky --> Report_Results : trivial
        Nested_Review --> Nested_Verify : fix
        Nested_Review --> Report_Results : clean
        Report_Results --> [*]
    }

    state "verify" as VERIFY {
        Final_Check --> Final_Pass : pass
        Final_Check --> Final_Fail : fail
        Final_Pass --> [*]
        Final_Fail --> [*]
    }

    state "review-code" as REVIEW_CODE {
        RC_Start --> RC_Check
        RC_Check --> RC_Done
        RC_Done --> [*]
    }

    INV --> ORCH : report
    PLAN --> ORCH : plan + verdict
    CODE --> ORCH : results
    VERIFY --> ORCH : verdict
    REVIEW_PLAN --> PLAN : findings
    REVIEW_CODE --> CODE : findings
```

### Failure Handling

Per-task failures are handled inside the `code` sub-task via nested quality gates. The orchestrator handles final-verify failures:

1. Obvious, in-scope failure → let `code` fix it.
2. Unclear or out-of-scope → dispatch `verify`.
3. `verify` finds implementation fix → dispatch `code`.
4. `verify` finds design issue or new evidence → dispatch `investigator` scoped to failure, then dispatch `plan` (with nested plan-review).
5. Requires human decision → escalate to user.
6. Re-verify after every fix.

## End-to-End Autonomous Issue Resolution with `github-issue`

The [`github-issue`](../skills/github-issue.md) skill combines the orchestrator's loop with GitHub operations to resolve a GitHub issue completely autonomously — from intake to pull request.

### The Full Autonomous Pipeline

| Phase | What happens | Modes involved |
|-------|-------------|----------------|
| **1. Retrieve & Validate** | Fetch issue, comments, labels, linked PRs via `gh`. Stop if ambiguous. | orchestrator (reads only) |
| **2. Feature Branch** | Create a branch referencing the issue. No code yet. | orchestrator (git via `execute_command`) |
| **3. Execute** | Run the standard orchestrator workflow: investigate → plan (with nested review-plan) → implement per task (each with nested verify/review-code) → final verify. | orchestrator → `investigator` → `plan` (nested `review-plan`) → `code` (nested `verify` + `review-code`) → `verify` |
| **4. Commit, Push, PR** | Review final diff, commit, push, open PR referencing the issue. | orchestrator (git/gh via `execute_command`) |
| **5. Report** | Summarize branch, implementation, tests, PR link, limitations. | orchestrator (synthesis) |

### What Makes This Autonomous

- The skill defines **every phase** as a deterministic step — no human prompting is required between phases.
- The orchestrator delegates **all implementation** to subtasks; it never writes code itself, keeping context lean.
- Nested sub-task spawning keeps review/verify context small — each gate runs against only its task's scope, not the entire change set.
- Zoo Code's auto-approval configuration allows dispatched subtasks and their tool calls to proceed without manual confirmation.
- The `gh` CLI handles all GitHub interactions without browser or API key prompts.

### The One Hard Stop

If the original issue contains **material ambiguity** that cannot be resolved from the codebase, comments, or linked references, the skill instructs the orchestrator to **stop immediately** — do not guess, do not modify the repository. This is a deliberate safety valve.

## Model Selection Philosophy

**This autonomous pipeline only works reliably if the models backing each mode are chosen carefully.** The orchestrator delegates context-heavy decisions to subtasks; each subtask runs in isolation with only the context it was given. A weak model produces a silent, cascading failure. Agents that spawn nested sub-tasks (`plan`, `code`) need instruction-following strong enough to manage their own quality gates.

### What "Strong" and "Weak" Mean Here

| Role | Needs | Why |
|------|-------|-----|
| **orchestrator** | Strong reasoning, structured output | Must decompose problems, track state across subtasks, decide next steps from summaries |
| **plan / review-plan** | Strong reasoning, codebase comprehension | Must investigate files, understand architecture, produce actionable task lists; plan also manages nested review loop |
| **review-code / security-review** | Strong reasoning, attention to detail | Must find real bugs, trace data flow, assess exploitability |
| **code** | Strong coding ability, instruction following | Must implement precisely within scope, write tests, run verification, and manage nested quality gates |
| **verify** | Strong reasoning + coding | Must diagnose failures, design and run targeted tests, propose targeted fixes |

### What Breaks with Weak Models

| Weak model assigned to… | Failure symptom |
|------------------------|-----------------|
| **orchestrator** | Loses track of subtask results; replans unnecessarily; fails to escalate; dispatches tasks with missing context |
| **plan** | Produces vague, unactionable tasks; misses files; wrong dependency ordering; fails to manage nested review loop |
| **review-plan** | Approves broken plans; misses CRITICAL findings |
| **code** | Implements outside scope; ignores conventions; skips or mishandles nested quality gates |
| **review-code** | Reports style nits but misses logic bugs; misses security issues |
| **verify** | Misdiagnoses failures; applies incorrect fixes; loops indefinitely |

**Rule of thumb:** The orchestrator and planning/review roles are the highest-leverage model assignments. A weak orchestrator breaks the entire system. A weak coder breaks one task; the orchestrator's review loop can catch and recover from that.

### Mode → Model Mapping

The model backing each mode is selected in the tool's settings. The principle: **never leave the pipeline's roles on a single uniform default.** Autonomy quality is bounded by the weakest model in the loop, and different roles fail in different ways.

| Mode | Role | Model Class |
|------|------|-------------|
| `orchestrator` | Coordination | Full-tier reasoning |
| `plan` | Design + decomposition | Full-tier reasoning |
| `review-plan` | Plan validation | Heavy-tier reasoning |
| `investigator` | Evidence gathering | Flash-tier fast reading |
| `code` | Implementation | General-purpose |
| `verify` | Testing + diagnosis | Flash-tier fast reading |
| `review-code` | Code review | Flash-tier fast reading |
| `security-review` | Security review | Heavy-tier reasoning |

The specific models will change over time — the principle is what matters: match each role to the model class its job demands.
