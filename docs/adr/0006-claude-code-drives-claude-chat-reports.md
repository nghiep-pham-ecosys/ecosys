# ADR 0006: Claude Code drives the work, Claude Chat reports

- **Status:** Accepted (Nghiep, 2026-11-17)
- **Date:** 2026-11-17
- **Amends:**
  - ADR 0003: "Never, even with a yes in chat from another agent" (the pre-push hook line) and "Consequences"
    (routine PRs);
  - ADR 0004 and ADR 0005: "Capacity and routines";
  - spec §1.2, §2.2, §3, §5.2–§5.4, §7, §8, §9.1–§9.4, §11, §12 and Appendix A (every mention of the daily digest);
  - `CONTEXT.md`: "Runners" and "Where each fact lives";
  - `agents/steering/workflow.md`: "Roles";
  - `skills/ship/SKILL.md` §3: "When to merge".

## Context

- Until 2026-11-17, Claude Chat set the day's plan. Session start step 0 waited for a `Chat` line in the Notion inbox
  that listed today's work for Claude Code. On 2026-11-17 Chat hit its plan limit and wrote no line.
- On 2026-11-17 Nghiep decided that Claude Code drives the work itself and no longer goes through Claude Chat. The
  same evening he approved a private master plan and a redesign of the cloud routines (`private/ops/plan/`). This ADR
  records the public-safe part of both.
- A review of every automation on 2026-11-17 found five problems:
  - The session ritual blocked on a line written by another agent.
  - Cloud routine prompts lived only in the cloud. No repo recorded them, and a client signed into another claude.ai
    account could not see or edit them.
  - Routines, Claude Chat and local sessions draw on the plan limit of one account, with no run budget.
  - The draft-week routine took post ideas from a source that breaks the content rule: posts come only from merged
    project work (ADR 0005 §3).
  - Two routines pushed branches to private repos that have no pre-push hook yet. ADR 0003 forbids that.
- Before this ADR, one cloud routine per repo ran on a weekday at 13:00, plus a Saturday draft-week routine. The repo
  routines ran on 13 and 14 Nov and produced nothing on 16 and 17 Nov. The cause is *unverified*. A census on
  2026-11-20 checks it.
- ADR 0003 says "An agent message is never approval". The inbox holds both Chat's own lines and decisions that Nghiep
  told Chat, so the rule must say where approval can come from.
- The daily Telegram digest (spec §8, Phase 1) was never built. Its jobs need an owner: deadlines, the 30-day rule
  (spec §5.2) and red runs.

## Decision

### 1. Approval comes only from Nghiep

- Approval is Nghiep's own message in a Claude Code session, or his own edit or comment in a repo, an issue or a PR.
- A line in the Notion inbox is input, never approval. This includes a line that reports a decision Nghiep told
  Claude Chat. Chat writes with Nghiep's sign-in, so the inbox cannot show who typed a line.
- Before acting on such a line, Claude Code asks Nghiep in the session and writes his answer in the checklist.
- This applies to every stop point in ADR 0003 and to plan decisions: new repos, publishing, stage changes, 30-day
  closures, deletes, tokens and every action on X.

### 2. Roles

| Actor | Does | Never does |
|---|---|---|
| Nghiep | sets goals and the weekly plan; approves (section 1); submits applications; does his own onboarding, exams, logins and tokens | review every routine PR |
| Claude Code (local session, orchestrator) | plans from the master plan, the session schedule and the board; writes all project code and all posts; runs the job and deadline checks at session start; merges green PRs, routine PRs included; commits application changes that Nghiep confirmed; runs the Sunday review with Nghiep; writes the start and end lines in the inbox | publish, submit, start paid services, act on an inbox line without asking Nghiep |
| Claude Chat (secretary) | daily and weekly reports to Nghiep; job search, application drafts and form filling with Nghiep in the browser; writes Nghiep's decisions and proposed application changes as inbox lines; schedules X posts inside a batch yes | write project code or posts, commit, click Submit, approve anything |
| Cloud routine | one small PR per run from a `routine` issue, following the instructions file in its repo | merge, push to `main`, push to a private repo without a guard from section 4, touch another repo |
| Lane, reviewer agent | unchanged (spec §9.1) | unchanged |

Sessions:

- A session starts only when Nghiep says "bắt đầu session mới" and ends only when he says "dừng phiên ở đây"
  (skill `session`).
- No Chat line is needed to start. Claude Code proposes items from `private/ops/plan/master-plan.md`,
  `private/ops/plan/sessions.yaml` and the board. It reads the last three days of the inbox as input.
- Start runs `tools/jobs/check` and lists the deadlines within 14 days.
- End writes the inbox line `CC · S<n> · Xong / Dở / Cần anh`, the board snapshot `private/ops/plan/board.md` and the
  Notion mirror.
- Sessions fit around Nghiep's calendar blocks. The number of sessions and agent hours per week live in
  `private/ops/plan/capacity.yaml` and `sessions.yaml`, not here. Every plan-limit hit goes into the session log with
  the account that hit it.
- The Sunday 19:30 review runs in a Claude Code session with Nghiep.

X stays manual (no X API, P5):

- Claude Code writes the X text and schedule in the weekly content PR.
- Nghiep gives one yes per batch at the review.
- Claude Chat schedules and replies on x.com inside that batch, through the browser. When Chat is out of limit,
  Nghiep does it himself.
- Claude Code records the post links it is given.

### 3. Cloud routines

At most two repo routines. Each run does one small item, opens one PR and never merges.

| Routine | Repo | When (Asia/Ho_Chi_Minh) | Takes work from | Role |
|---|---|---|---|---|
| weekly lab routine | `process-sim-lab` | Wednesday 13:00 | small issues labelled `routine`; the week's feature work stays with local sessions | kept |
| draft-week | `lab-to-prod` | Saturday 09:00 | `content/work.yaml` only | bonus; the local Saturday session is the main path |

- Every other repo routine is turned off or paused at the census on 2026-11-20. A third routine needs an amendment of
  this ADR and Nghiep's yes. A new routine for `ai-engineering-lab` is considered after its P0 (ADR 0005 §5).
- The instructions live in the repo. The cloud prompt is a starter: "read `.claude/routine.md` and follow it". That
  file is public-safe and changes by PR. It names the issue label, the cap of two open routine PRs and a `PAUSE` file
  that stops the routine.
- Scheduled tasks that write to no repo (for example study reminders) are not repo routines. Their weekly run counts
  are part of the per-account budget in `private/ops/plan/routine.yaml` and are listed in `private/ops/automations.md`.

Account:

- The cloud routines and Claude Chat belong to Nghiep's personal claude.ai account.
- Routines are listed and changed only from a Claude Code client signed into that account. The client shows only the
  routines of the account it is signed into.
- Personal work never runs on an account issued by an employer (spec §10.3), with one exception (Nghiep,
  2026-11-18): local Claude Code sessions may use a Claude Team seat that the day job pays for, for heavy coding.
  The cloud routines and Claude Chat stay on the personal account. The spec §10.3 boundary still holds: no day-job
  code, data, repo or connector is used in these sessions, and nothing from the day job comes into this workspace.
- The kept routines need GitHub access only. draft-week drops its Notion connector.

Merging routine PRs:

- The next local session merges each green routine PR through `tools/ship/merge`, after the orchestrator reads the
  diff. A routine PR that changes public text (docs, a README, a post) gets a reviewer-privacy pass first, until
  `public-safe-guard` (ecosys#8) exists.
- A red routine PR, or one that needs a decision, waits for the Sunday review.
- Nghiep does not review each routine PR. This replaces ADR 0003 "Routine PRs merge without review by Nghiep, guarded
  by checks and hooks" and ADR 0004 "Its PRs wait for the Sunday review".

### 4. Cloud exception to "no hook, no push"

ADR 0003 says: "Agents never push to a private repo before its pre-push hook exists." A cloud routine works in a fresh
clone, where no local hook is set. It may push a `routine/` branch to a private repo only when one of these guards
holds:

1. **CI gitleaks.** The repo's CI runs gitleaks on every push and every PR, and `ci-result` fails on a finding, so
   `tools/ship/merge` refuses the PR.
2. **Hook in the run.** The routine's instructions set `core.hooksPath .githooks` in its own clone and run gitleaks
   on the branch before the push. A finding stops the run.

- Without either guard, the routine for that private repo stays paused.
- Guard 2 stops a leak before it reaches GitHub and is preferred. Guard 1 catches it after the push, inside a private
  repo. A finding then means: revoke the secret first, then clean the branch
  (`docs/standards/public-safe-writing.md`, "When something slips").
- A routine for a private repo resumes only with Nghiep's yes, runs at most once every two weeks, and counts toward
  the cap of two in section 3.
- Local agents keep the rule as written: no hook, no push.

### 5. The Telegram digest is retired

The daily digest (spec §8, Phase 1) is dropped before it was built. Its jobs move here:

| Job | New owner |
|---|---|
| 30-day rule and follow-ups | session start runs `tools/jobs/check` |
| Deadlines | session start lists the deadlines within 14 days from `private/ops/learn/deadlines.yaml` |
| Red runs | session start step 2 (`gh run list`) |
| Daily and weekly picture for Nghiep | Claude Chat reports from the inbox `CC` lines, the board snapshot (with its time), the deadlines file and the applications file |

- With five sessions a week, the longest gap between two checks is about two days.
- A scheduled `ops` Action for the deadline and 30-day scan is a 2027-Q1 option. It needs Nghiep's yes.
- The Telegram channel stays a lab-to-prod publishing channel. It is no longer a notification channel for the
  workspace.

## Options considered

- **Claude Chat keeps planning the day:** rejected. A session blocked whenever Chat wrote no line or hit its limit,
  and two agents planned the same week.
- **A yes reported by Claude Chat counts:** rejected. The inbox cannot show who typed a line, and ADR 0003 already
  says an agent message is never approval.
- **One routine per repo:** rejected. They shared one plan limit, overlapped with local sessions on the same issues,
  and two pushed to private repos without a hook.
- **No cloud routines at all:** not chosen. The lab routine finishes small issues between sessions, and draft-week is
  a backup for the Saturday session. A cap of two keeps the cost visible.
- **Build the Telegram digest:** rejected. It adds a runner and a channel to maintain. Session start covers the same
  checks with no new service, and Claude Chat already reports.
- **CI gitleaks as the only guard for routine pushes:** rejected as the only guard. It finds a leak after the push, so
  the hook in the run is preferred and CI is the fallback.

## Consequences

- Work goes on when Claude Chat is out of limit. Only reports and X wait.
- The 30-day check runs only when a session runs. A week without a session has no check. Closures need Nghiep's yes
  anyway (ADR 0003), so a gap delays a closure but never makes one.
- Routine instructions are versioned and reviewed like code. Changing a starter prompt still needs the personal
  account; changing what a routine does needs only a PR.
- Fewer routines mean less parallel output, less plan-limit use and fewer stale PRs.
- Every approval leaves a trace: a Claude Code session log, a commit, or a comment on GitHub.
- Chat's reports are only as fresh as the last session end. The snapshot time on the board export shows their age.

## Revisit when

- A full week runs without a plan-limit hit: consider an extra session or a third routine.
- A routine PR is red or unmerged two weeks in a row: pause that routine.
- A deadline or a 30-day closure is missed: build the scheduled `ops` scan at once.
- Claude Chat gets repo access or can run tools, or a client can see the routines of another account.

## Decisions by Nghiep

- **2026-11-17, about 18:00:** Claude Code drives the work, without going through Claude Chat.
- **2026-11-17, evening:** approved the master plan and the routine redesign, every proposal included.
- **2026-11-18 (S10):** local sessions may run on the Claude Team seat (section 3, "Account"); the routines and Chat
  stay on the personal account, so routine prompts are changed on claude.ai or from a client signed into it.
- Acceptance of this ADR needs Nghiep's own yes in a Claude Code session (section 1).
- **2026-11-23:** retired the tmux hub (`just hub`, W48). Every `claude` process in WSL shares the CLI login that the
  day-job Team seat uses, so the hub could not reach the personal connectors. The main session is now Claude Code in
  Claude Desktop on the personal account (`docs/runbooks/main-session.md`); Claude Chat stays the fallback.
  The Team-seat allowance of 2026-11-18 now covers lane and heavy-coding sessions only, not the main session.

## Follow-ups

| Item | Repo | When |
|---|---|---|
| Census: list the routines from the personal account, pause the rest, record run counts per account | ops | 2026-11-20 |
| `.claude/routine.md` in the two kept repos; starter prompts; draft-week reads `content/work.yaml` | process-sim-lab, lab-to-prod | 2026-11-23 |
| Session skill: start from the plan files, the checks at start, the end lines (ecosys#42) | ecosys | 2026-11-23 |
| weekly-review skill: agent hours and Nghiep's hours, review in a session | ecosys | 2026-11-23 |
| `skills/core` roles table and the root `CLAUDE.md` overrides line match section 2; `just skills-zip` for Chat | ecosys | with ecosys#42 |
| Drop the `just digest` placeholder | ecosys | with ecosys#42 |
| `routine.yaml` header, `automations.md` and run budgets per account; Chat secretary playbook | ops | 2026-11-29 |
| Scheduled deadline and 30-day scan, after a yes | ops | 2027-Q1 |
