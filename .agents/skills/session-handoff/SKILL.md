---
name: session-handoff
description: Produce a structured, chat-only end-of-session handoff when the user asks for a session handoff, wrap-up, handoff summary, or continuity summary before clearing context or starting a fresh agent session.
---

# Session handoff

Produce a context-handoff artifact for the next agent, not a stakeholder status
report. Make the next session able to continue from the summary alone.

Follow the repository's
[shared operating model](../../../docs/agent-operating-model.md). Do not copy
general project guidance into the handoff; reference the authoritative file
when it is relevant.

## Build the handoff

1. Review the available conversation from the full session, not only the most
   recent turns.
2. Collect state from session evidence in this order:
   - Active plans, task lists, or plan files used during the session.
   - Decisions made and files created or modified during the session.
   - Background processes, development servers, worktrees, and branches started
     or opened during the session.
   - Verification commands already run and their observed results.
   - Persistent notes or memory files explicitly read or written in the
     session.
   - Deferred work and questions that remain unanswered.
3. Use conversation and tool state already available. Do not run broad
   filesystem searches or inspect Git history merely to reconstruct the
   session.
4. Mark unavailable or uncertain state as `unknown`. Never infer identifiers,
   paths, commands, results, or process state.
5. Return the handoff in chat only. Do not create a handoff file or update
   persistent memory.

## Output format

Use exactly this structure:

```text
# Session Handoff — <one-line title>

## Where it started
<Two or three sentences describing the request and material constraints.>

## Decisions locked + what shipped
- <Decision or change> — <reason and location>

## Key files for next session
- `<absolute path>` — <why to read it>
- Plan file: `<absolute path>` or `none`
- Persistent notes touched: `<absolute paths>`, `none`, or `unknown`

## Running state
- Background processes: <identifier, purpose, and known stop command> or `none`
- Dev servers / ports: <URL and port> or `none`
- Open worktrees / branches: <paths and names> or `none`

## Verification — how to confirm things still work
- `<command>` — <observed or expected result>

## Deferred + open questions
- Deferred: <item and reason> or `none`
- Open: <question and context> or `none`

## Pick up here
<One or two sentences naming the most likely next action.>
```

## Quality and safety rules

- Keep every section, using `none` or `unknown` when appropriate.
- Use absolute paths for files when the path is known. Do not fabricate an
  absolute path from an uncertain location.
- Put a plan file first in `Key files for next session` when a plan drove the
  work.
- Include background-process identifiers and stop commands only when observed.
- Distinguish commands already run from commands recommended for the next
  session.
- Keep the tone terse and factual. Do not add praise, emojis, or a
  retrospective.
- Do not recommend work beyond the single `Pick up here` action.
- Do not include secrets, credentials, tokens, or sensitive environment
  values.
- Do not write to tool-specific handoff, plan, or memory directories.

## Avoid

- Summarizing only the last few turns.
- Re-auditing the repository to compensate for missing session context.
- Presenting planned work as shipped work.
- Omitting empty sections.
- Listing relative file paths when an absolute path is known.
- Inventing process state, verification results, or unresolved decisions.
