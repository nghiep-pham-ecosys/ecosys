---
name: core
description: Base rules for the nghiep-pham-ecosys personal workspace. Covers the hard rules and the guard behind each one, who does what (Nghiep, orchestrator, lanes, reviewers), sources of truth and their precedence, which skill to load when, the issue template and Definition of Ready, the lane brief template, and language rules. Use it when starting any task that has no obvious skill yet, when a rule or permission is unclear, when two sources disagree, when writing an issue, or when briefing a subagent or lane. It does not cover the session rituals (session), merging and Done (ship), the lesson format (lessons), the job pipeline (jobs) or the weekly plan (weekly-review).
---

# core

The stable rules for this workspace. Live state (open PRs, board items, applications) is never stored here: read it
from its source (§4).

## 1. Scope

- One person's workspace: areas `jobs`, `learn`, `content`, `lab`, `ecosys` (spec §3). The day job appears only as a
  weekly `work-block` time item.
- Root repo `ecosys` at the workspace root; every other repo is cloned under `meta/`, `private/` or `projects/` with its
  own `.git`. `repos.yaml` is the list. `CONTEXT.md` is the system map.
- Nghiep is mid-senior. Answer with the conclusion first, then the reason. No filler.
- Once a direction is approved, finish it. Decide small things and report them. Stop only for a real block: a stop
  point in §2, money, credentials, or a decision only Nghiep can make.

## 2. Hard rules (MUST)

Each rule names what enforces it. A rule without a guard is a ritual step with an owner.

| # | Rule | Guard |
|---|---|---|
| 1 | Start sessions at the workspace root. Read `CONTEXT.md`, then the target repo's `CLAUDE.md`. | ritual: `session` start |
| 2 | Plan within the area budgets and WIP limits of `private/ops/plan/capacity.yaml`. | ritual + capacity check: `weekly-review` |
| 3 | Lanes work only in worktrees under `.tmp-session/wt/`, created with an absolute path. | hook `worktree-guard` |
| 4 | Subagents never push, merge, open PRs, run workflows or call write APIs. | hook `ship-guard` |
| 5 | Merge only through `tools/ship/merge`. | hook `ship-guard` + settings deny `gh pr merge` |
| 6 | No paid API or paid service without an explicit yes, with the monthly cost stated first (P5). | ritual: ADR 0003 approvals |
| 7 | Never submit an application, publish a post or send a message without Nghiep. Draft first; Nghiep approves. | ritual: `session` end step 3; `ship-guard` blocks lane writes |
| 8 | Personal data lives only in `private/ops` or `private/vault`. Public repos follow the public-safe rule (§10.2). | local denylist pre-push hook, hash-only public CI; `public-safe-guard` **[P1]** |
| 9 | Nothing from the day job or clients comes in except ways of working (§10.3). | denylist + reviewer-privacy pass |
| 10 | Never state live status from memory. Check it live in the same turn, or label it *unverified*. | ritual: `session` start step 2 |
| 11 | Never read secrets: `.env*`, keys, sops decryption, the denylist file. | hook `secret-path-guard` + settings deny |
| 12 | Repo transfer, delete, archive, visibility change, new token or OAuth app: only with Nghiep's yes for that item. | settings `ask`/`deny`; ritual |

A lesson that keeps coming back becomes a guard (P7, `lessons` §4), then this table gets one line for it.

## 3. Roles (spec §9.1)

| Actor | Does | Never does |
|---|---|---|
| Nghiep | sets session goals and the weekly plan; approves publishing, applications, money, deletes, credentials, visibility changes, transfers | review every routine PR |
| Orchestrator (main session) | plans, runs lanes, merges through the merge tool, verifies, writes logs | publish, submit applications, start paid services, transfer repos without approval |
| Lane / subagent | codes and tests in its worktree, commits locally, returns a structured result | push, merge, open PRs, run workflows, write to external tools |
| Reviewer agent | read-only review of a diff (privacy lens, correctness lens) | edit code |

## 4. Sources of truth

Precedence when sources disagree: **repo > canonical doc > memory > skill**. Report the drift to Nghiep and name both
sources. Never pick one silently.

| Need | Source |
|---|---|
| System map, areas, data homes | `CONTEXT.md`, `docs/spec.md` |
| Repo list, paths, visibility | `repos.yaml`; live: `just ws-status` |
| Decisions | `docs/adr/` |
| What is planned and in progress | the org board "Ecosys board" (spec §6) |
| Budgets and WIP limits | `private/ops/plan/capacity.yaml` |
| Job pipeline | `private/ops/jobs/applications.yaml` (`jobs`) |
| Deadlines | `private/ops/learn/deadlines.yaml` |
| Last session, next steps | newest block of `private/ops/memory.md`, newest `private/ops/sessions/*.md` |
| Scheduled tasks | `private/ops/automations.md` |
| Lessons | `skills/lessons/lessons.md` (public-safe), `private/ops/lessons.md` (personal) |
| Names that must never appear in public | `private/ops/boundaries.md` and the local denylist (never read or print it) |

## 5. Which skill when

| Situation | Skill |
|---|---|
| "start a session", "wrap up", "end the session", first message of a session without context | `session` |
| ready to open or merge a PR, a check is red, about to mark something Done | `ship` |
| found a root cause of a mistake, "note this lesson", before editing an area with known lessons | `lessons` |
| job search, an application, a recruiter reply, a follow-up, the 30-day rule, a form to fill | `jobs` |
| Sunday review, planning next week, capacity or WIP question, too many threads | `weekly-review` |
| course deadlines, study tracks | `learn` **[P1]** (until then: spec §5.3 + `private/ops/learn/`) |
| posts, blog, publishing | `content` **[P1]** (until then: lab-to-prod's own skills) |
| CV or profile text | `cv` **[P1]** (until then: spec §5.1) |

## 6. Issues and lane briefs

- Issue template, where an issue lives (public repo or private `ops`), granularity and the Definition of Ready:
  [`references/issue-and-brief.md`](references/issue-and-brief.md).
- A lane is briefed only with the lane brief template in the same file (spec Appendix C). An issue that fails the
  Definition of Ready is completed first, then briefed.
- Ask before creating an issue. Propose the title and the Problem/Scope/Done-when in plain words so Nghiep only has
  to say yes. Several issues → one batch.

## 7. Asking Nghiep

- Give the context in plain words and a proposed answer. Many questions → one list with a default for each.
- An open question is not a reason to stop. Act on the proposed answer when it is safe and reversible, and say so,
  so Nghiep can reverse it. Stop only on the items of §2 rules 6, 7 and 12.
- Steps that need a permission prompt are batched into one window, announced first.

## 8. Language and style (spec Appendix B)

- English: code, comments, commits, PRs, issues, ADRs, technical docs, skills.
- Vietnamese: chat with Nghiep, session logs, memory, private notes.
- Posts: per the lab-to-prod rules.
- Style: short sentences, active voice, numbers with units, no claim without a source. No "might be because…" as a
  conclusion: check, then state.

## Maintenance

Follow `skills/README.md`. A rule that becomes a guard shrinks to one line in §2 that names the guard.
