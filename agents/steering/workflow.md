# Workflow

How work moves in this workspace. Details live in the skills named here.

## Roles (spec §9.1)

| Actor | Does | Never does |
|---|---|---|
| Nghiep | sets goals and weekly plans; approves anything in ADR 0003 | review every routine PR |
| Orchestrator (main session) | plans, runs lanes, merges through `tools/ship/merge`, verifies, writes logs | publish, submit, start paid services, transfer repos without a yes |
| Lane (subagent) | codes and tests in its worktree, commits locally, returns a structured result | push, merge, open PRs, run workflows, write to external tools |
| Reviewer agent | read-only review of a diff (privacy or correctness lens) | edit code |

## Session

- **Start** (skill `session`): read the newest memory block and last session log in `private/ops`, check reality with `just ws-status` and open PRs, report drift, read the lessons for the areas you will touch, propose 3–5 items within budget, then write `.tmp-session/checklist.md`.
- **During:** keep the checklist live. Put lessons in `.tmp-session/lessons-pending.md` as soon as a root cause is found.
- **End:** settle board items with evidence, move lessons, batch external drafts for one approval, write the session log, leave every repo on a clean `main`, remove worktrees, give three lines: done / left and why / where to start next.

## Lanes

- One lane = one issue = one worktree at `.tmp-session/wt/<session>-<lane>/` on branch `<type>/<n>-<slug>` from `origin/main`.
- Use lanes only for independent parallel work. Plan limits are the real constraint.
- Brief every lane with the template in spec Appendix C. The lane returns JSON:
  `{ready, blocked_reason, branch, commits, summary, followups, lessons}`.

## Ship (skill `ship`)

1. Branch → PR with a conventional title → checks green (`ci-result`, `pr-title`).
2. Merge only with `tools/ship/merge`: it refuses drafts, conflicts and red, pending or missing checks, reads checks twice, then squash-merges with `--match-head-commit`.
3. Verify on `main` (CI green; deployed thing returns what it should).
4. Done = verified, with an evidence link on the board item. Status is set by hand, never by a commit keyword.

## Board

- One org Project, "Ecosys board". One issue = one PR or one 1–3 h task. Recurring work = one weekly item.
- Personal items (applications, money, health) are issues in private `ops`, never in a public repo.
- Respect WIP limits from `capacity.yaml`. A new item waits in `Next` until a slot frees.

## Lessons (skill `lessons`)

- Write a lesson when a root cause is found, not at the end of the week.
- Each lesson has a Guard (what now prevents it) and Seen (dates it happened).
- A lesson seen twice becomes a hook, a CI check or a test (P7).
