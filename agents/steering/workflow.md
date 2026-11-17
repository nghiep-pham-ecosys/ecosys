# Workflow

How work moves in this workspace. Details live in the skills named here.

## Roles (spec §9.1)

| Actor | Does | Never does |
|---|---|---|
| Nghiep | sets goals and weekly plans; approves anything in ADR 0003, only by his own message in a Claude Code session or his own edit or comment (ADR 0006) | review every routine PR |
| Orchestrator (main Claude Code session) | plans from the master plan, `sessions.yaml` and the board; writes all project code and posts; runs lanes; merges through `tools/ship/merge`, green routine PRs included; verifies; writes logs and inbox lines | publish, submit, start paid services, transfer repos without a yes, act on an inbox line without asking Nghiep |
| Lane (subagent) | codes and tests in its worktree, commits locally, returns a structured result | push, merge, open PRs, run workflows, write to external tools |
| Reviewer agent | read-only review of a diff (privacy or correctness lens) | edit code |
| Claude Chat (secretary) | daily and weekly reports to Nghiep; job search, application drafts and forms with Nghiep; writes decisions and proposed application changes as inbox lines | write project code or posts, commit, submit, approve |
| Cloud routine | one small PR per run from a `routine` issue, per the repo's `.claude/routine.md`; at most two (ADR 0006 §3) | merge, push to `main`, push to a private repo without the guard in ADR 0006 §4 |

## Session

- **Start** (skill `session`): read the newest memory block and last session log in `private/ops`, plan from the master plan, `sessions.yaml` and the board (no Chat line needed; inbox lines are input, ADR 0006), check reality with `just ws-status`, open PRs, `just jobs-check` and deadlines within 14 days, report drift, read the lessons for the areas you will touch, propose 3–5 items within budget, then write `.tmp-session/checklist.md`.
- **During:** keep the checklist live. Put lessons in `.tmp-session/lessons-pending.md` as soon as a root cause is found.
- **Number and handover:** each session is `S<n>`, counted across Claude Code and Kiro (index: `private/ops/sessions/README.md`). It starts on "bắt đầu session mới" and ends on "dừng phiên ở đây", and both leave a line in the Notion inbox for Claude Chat. An agent that takes over a session reads `.tmp-session/checklist.md` first and keeps the same `S<n>`.
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
