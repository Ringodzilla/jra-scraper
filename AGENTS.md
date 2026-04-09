# Local Agent Routing Rules

This repository uses role-separated subagents under `/agents`.

## Agent profiles
- `agents/researcher.md`
- `agents/planner.md`
- `agents/implementer.md`
- `agents/reviewer.md`

## Workflow order
1. Researcher
2. Planner
3. Implementer
4. Reviewer

## Guardrails
- Do not merge multiple roles in one step.
- Implementer is the only role allowed to edit code.
- Reviewer can only validate and return OK/NG + fix instructions.
- If Reviewer returns NG, rerun Implementer with reviewer instructions only.
