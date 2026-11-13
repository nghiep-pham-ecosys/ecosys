# Lessons (public-safe)

How to read and write this log: [`SKILL.md`](SKILL.md). One rule per entry, with `Why`, `Seen` and `Guard`.
Personal lessons live in `private/ops/lessons.md`. When a guard blocks the whole class of a mistake, the entry moves
to `guards.md` in the same PR.

## Working with agents

### Quote the user's request verbatim in every lane brief
- Why: a workflow lane refused its task because the harness relayed the user's latest message (about something
  else) and the brief did not show which request the task came from → the brief described the work but not the ask.
- How: start each brief with "USER REQUEST FOR THIS TASK (verbatim): …" and, when newer messages exist, say that the
  orchestrator handles them.
- Seen: workspace session 1 (brand lane), 2026-11
- Guard: ritual step in the lane brief template (skills/core/references/issue-and-brief.md)

### Leave a lane worktree before shipping from the main session
- Why: after `cd` into a `.tmp-session/wt/` worktree, the main session's shell stayed there, so ship-guard treated
  the next `git push` as a lane push and blocked it → the shell cwd persists between tool calls.
- How: commit inside the worktree, then `cd` back to the workspace root in its own call before pushing or merging.
  Write worktree paths literally; worktree-guard rejects paths built from shell variables.
- Seen: workspace session 1, 2026-11; 2026-11-13 (a commit-and-push one-liner that named the worktree path)
- Guard: hook ship-guard (blocks the push; this lesson explains the fix)

## Verify and Done

_No entries yet._

## Shipping and CI

### A private repo needs its own CI before the merge tool can ship it
- Why: `ops` had no workflow, so every PR had zero checks and `tools/ship/merge` refused it, even with
  `--require ''`; two PRs sat open and older commits had gone straight to `main` → the private-repo rule assumed
  checks existed but no step created them.
- How: before the first PR in a private repo, add a workflow with jobs named `ci-result` and `pr-title` (copy
  `ops/.github/workflows`). A PR opened before that needs its branch updated
  (`gh api -X PUT repos/<o>/<r>/pulls/<n>/update-branch`) so the checks run.
- Seen: ops, 2026-11-13
- Guard: rule in skills/ship §3 (private repos)

### A FAILED verdict from the merge tool is not proof the PR is unmerged
- Why: with `delete_branch_on_merge` on, `gh pr merge --delete-branch` raced GitHub's own branch delete; the squash
  merge went through but gh exited 1 on the 404 delete, so `tools/ship/merge` printed FAILED → the tool trusted the
  exit code of a two-step command.
- How: after FAILED, run `gh pr view <n> --json state,mergeCommit` before any retry. Fix candidate: the tool
  re-reads the PR state after a non-zero exit and reports MERGED when it is merged.
- Seen: ecosys#20 and ecosys#23, 2026-11-13
- Guard: tools/ship/merge re-reads the PR state after a non-zero gh exit (test_merge_error_after_successful_merge_is_merged)

### In a PR stack, retarget the next PR to main before merging the one below it
- Why: merging a stacked PR with branch deletion closed the PR that was based on that branch (GitHub closes, it does
  not retarget, when the base branch disappears) → the merge step deleted the base before the dependent PR moved.
- How: before each merge, PATCH the next PR's base to `main`, then merge, then rebase the next branch onto the new
  `main` (`git rebase --onto origin/main <old-base-tip> <branch>`) and wait for green checks. With gh 2.45 use
  `gh api -X PATCH repos/<o>/<r>/pulls/<n> -f base=main`; `gh pr edit --base` fails on a Projects-classic field.
- Seen: lab-to-prod stack #1–#8, 2026-11
- Guard: none yet (ritual step in skills/ship; candidate: a `tools/ship/stack-merge` wrapper)

### A recreated repository may not start Actions until its Actions permission is set again
- Why: after deleting and recreating a public repo, pull_request events fired but no workflow run was created until
  the repository Actions permission was written once (`PUT repos/<o>/<r>/actions/permissions`) → new repos inherit
  the org policy on paper but did not trigger runs.
- How: after creating or recreating a repo, PUT its Actions permissions (`enabled=true`, `allowed_actions=selected`),
  then close/reopen open PRs and confirm a run appears before waiting on checks.
- Seen: lab-to-prod recreation, 2026-11
- Guard: ritual step in docs/runbooks/new-project.md

## Publishing

### Check the live profile and the publish record before any manual post
- Why: two posts were made by hand in the browser, but the scheduling tool and the study log still said "waiting
  for approval", so the next session almost posted one of them again → the only record of "posted" was a tool that
  never saw the manual post.
- How: before posting by hand, open the live profile and run `python -m publish.record_manual check` in
  lab-to-prod; right after, run `record` with the live URL. Reports read `published.json` before saying "waiting".
- Seen: 2026-11-13
- Guard: lab-to-prod `publish/record_manual.py` + CLAUDE.md rule (lab-to-prod#13)

### Keep bot-written state off a protected branch
- Why: the publish and metrics workflows pushed `published.json` and `metrics.csv` straight to `main`, but the main
  ruleset only accepts pull requests; a live run would have posted, failed to record it, and posted again on the
  next run → the state store was the one branch bots may not write.
- How: keep bot state on its own unprotected branch (`publish-state`), merge it into the checkout before a run, push
  it back after. Readers that need the full record read that branch.
- Seen: lab-to-prod, 2026-11-13 (caught before going live)
- Guard: lab-to-prod `tools/state_sync.py` with tests (lab-to-prod#21)

### Send your own User-Agent from token and API scripts
- Why: dev.to answered 403 with an empty body to a valid key, because it blocks the default `Python-urllib` agent
  → the error looked like a bad key.
- How: set a named User-Agent in every stdlib HTTP helper; test a public endpoint with and without it before
  blaming the credential.
- Seen: lab-to-prod token scripts, 2026-11-13
- Guard: `scripts/tokens/_common.py` USER_AGENT + test (lab-to-prod#25)

### On use-case based developer apps, add each permission to the use case
- Why: the Meta app was created with the "Manage everything on your Page" use case, but only `pages_show_list` was
  enabled, so sign-in failed with "Invalid Scopes" → the newer app model grants nothing a script asks for unless the
  use case lists it.
- How: after creating an app, open the use case's permissions and add every scope the script requests; check the
  settings page notes (localhost redirects need no entry in development mode).
- Seen: Meta app for the Facebook Page, 2026-11-13
- Guard: lab-to-prod docs/setup.md step 4 (lab-to-prod#17)

## Public-safe and privacy

### A public file must not list the names it is meant to hide
- Why: a banned-terms list and its tests held the protected names in plain text in a public repo, so the guard
  published the exact list it was meant to protect → the check was designed around a readable list instead of a
  secret one.
- How: store only salted or unsalted hashes of the names in public files, or keep the list local and out of git.
  Test fixtures use synthetic names (Example Co, Acme).
- Seen: lab-to-prod PR #1, 2026-11
- Guard: hook pre-push denylist scan (local denylist, never committed) + ci hash-only check in public repos (spec §10.2)

## Data and tools

### Read a scratch file before deleting it
- Why: `.tmp-session/lessons-pending.md` was deleted after one entry was moved, without reading it first; any entry
  an earlier session left there would be lost → the delete assumed the file held only what this session wrote.
- How: `cat` the file, move every entry, then delete. The same holds for `checklist.md` and `drafts.md`.
- Seen: 2026-11-13
- Guard: ritual step (session End step 3)

_No entries yet._
