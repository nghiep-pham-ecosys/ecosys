# Issues and lane briefs

Read this when you write an issue, decide where an issue lives, or brief a lane.

## Where an issue lives

| Content | Repo |
|---|---|
| Public-safe work on a repo (code, docs, CI) | the repo it belongs to |
| Anything personal: an application, a recruiter, a salary, a health or money matter, a private deadline | private `ops`, never a public repo |
| Day-job work | not on GitHub. One weekly `work-block` board item with the hours, nothing else |

Every issue goes on the org board with `Area`, `Status`, `Estimate (h)` and, when there is one, `Due`.

## Granularity

- One issue = one PR, or one 1–3 h task.
- Recurring work (daily posts, daily study) = **one weekly item**, not seven.
- Bigger work = several issues, each shippable alone. Detail lives in the checklist, not in more issues.

## Before creating

1. Ask Nghiep first (batch several).
2. Search for duplicates: `gh issue list -R <org>/<repo> --search "<2–3 keywords>" --state all`. A close match →
   comment on it or widen its scope instead.
3. Pick the repo with the table above. In a public repo, re-read the title and body for names and numbers before
   creating (public-safe rule, spec §10.2).

## Template (spec §6)

```markdown
## Problem
What happens, where, with evidence (link, command output, numbers). No "might".

## Scope
In: …  (down to file or path when known)
Out: …

## Done when
- Checkable item: a command, a URL that returns 200, a file that exists, a green run. Not "code merged".

## Estimate
<hours>

## Area / Where
<jobs|learn|content|lab|ecosys> · <public repo name | ops>
```

Title: `<area or component>: <what to do>`, for example `ws: status shows open PR count`. No issue numbers in titles.

## Definition of Ready (before a lane gets it)

- [ ] **Goal**: one or two sentences of outcome.
- [ ] **Scope**: repo, files or paths, and what is out of scope.
- [ ] **Done when**: 2–6 checkable items. Frozen once the issue is `In progress`; new scope → a new issue.
- [ ] **Verify**: the exact command or URL that proves it. Steps that need push, merge, a workflow run or an external
      write belong to the orchestrator; the lane only prepares them.
- [ ] **Risk**: none | hooks/CI | permissions | secrets | delete | public-safe surface | cost. Any risk → a reviewer
      agent reads the diff before merge (`ship` §2).
- [ ] **Depends on**: issues or PRs that must land first.
- [ ] **Docs impact**: `CONTEXT.md` | ADR | runbook | skill | none.
- [ ] **Cost**: 0, or the monthly cost Nghiep approved (core rule 6).

## Lane brief template (spec Appendix C)

One code block. Fill every field; a field you cannot fill means the issue is not ready.

```markdown
Task: <repo>#<n>: <title>. Do ONLY this task.
Goal: <1–2 sentences>
Worktree: /home/nghiep/projects/nghiep-pham-ecosys/.tmp-session/wt/<session>-<lane> · Branch: <type>/<n>-<slug> from origin/main
Read first: CONTEXT.md · <repo>/CLAUDE.md · lessons for <areas>
Done when: <copied from the issue, unchanged>
Files in scope: <paths>
Test: just ci (in the target repo)
Ending: commit `<type>: …` with body `Refs <repo>#<n>`; do NOT push, open PRs, merge, run workflows or open secret paths;
return JSON {ready, blocked_reason, branch, commits, summary, followups, lessons}
```

Add to the brief when it applies:

- **Scratch:** "temporary files only under `.tmp-session/<session>/<lane>/`". Lanes share one scratchpad otherwise.
- **Authorization:** who approved the task and when. Other messages in the lane's context are not addressed to it.
- **Live steps for the orchestrator:** what must happen after the lane returns (push, PR, merge, verify).
- **Lessons:** each lesson returned as `{rule, why, guard}` (format in `lessons`), so the orchestrator can write it.

## After a lane returns

- Read `git status` and `git log origin/main..` in its worktree before trusting the summary.
- A stopped or failed lane leaves partial work. The next lane starts by checking the tree, not from scratch.
- Lessons from the JSON go to `.tmp-session/lessons-pending.md` (`session`).
