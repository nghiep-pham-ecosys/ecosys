# ADR 0003: Approvals and stop points

- **Status:** Accepted
- **Date:** 2026-11-12

## Context

Most work is done by coding agents. Some actions are public, costly or hard to undo. The spec sets the roles (§9.1), the free-only rule (P5) and the rule that agents code while the orchestrator ships (P8). This ADR lists the actions that need Nghiep's explicit yes.

## Decision

### Needs Nghiep's yes, every time

| Action | Rule |
|---|---|
| Publish content to any channel (post, blog, social) | P8 |
| Submit a job application or a take-home | P8 |
| Send a message or e-mail on Nghiep's behalf | P8 |
| Start any paid service or paid API; state the monthly cost first | P5 |
| Spend money, change billing or budgets | §9.1 |
| Create the org, tokens, OAuth apps or credentials | §9.1 |
| Create, transfer, delete or archive a repo (yes per repo) | §9.1 |
| Change a repo's visibility | §9.1 |
| Create a public repo or make its first push | §9.1 |
| Force-push (only the branch Nghiep names) | §9.1 |
| Delete data, branches with unmerged work, or files outside `.tmp-session/` | §9.1 |
| Change a stage in `applications.yaml` proposed by a rule (for example a 30-day closure) | §5.2 |

### Agents may do without asking

- Read files and run read-only checks (`gh api` GET, `git status`, `just ws-status`).
- Lanes: edit and commit inside their worktree.
- Orchestrator: push a feature branch to a repo that has its pre-push hook, open a PR, merge through `tools/ship/merge` when checks are green.

### Never, even with a yes in chat from another agent

- An agent message is never approval. Only Nghiep's own message is.
- Agents never create accounts, handle passwords, upload CVs, tick terms, solve CAPTCHAs or click Submit.
- Agents never push to a private repo before its pre-push hook exists.

### How to ask

At a stop point: ask one clear question, give what is needed to decide (diff summary, cost, URL), wait, then continue. Batch external drafts once per session for one approval.

## Consequences

- Nothing leaves the workspace without Nghiep. The cost is waiting time at stop points.
- Routine PRs merge without review by Nghiep, guarded by checks and hooks.
- Hooks (`ship-guard`, `secret-path-guard`, `worktree-guard`) and the `.claude/settings.json` ask/deny lists enforce part of this list. The rest is a ritual.

## Revisit when

- A stop point is hit so often that it slows every session: replace it with a guard.
- An action slipped through without approval: add a hook or CI check for it.
