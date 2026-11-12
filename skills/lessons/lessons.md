# Lessons (public-safe)

How to read and write this log: [`SKILL.md`](SKILL.md). One rule per entry, with `Why`, `Seen` and `Guard`.
Personal lessons live in `private/ops/lessons.md`. When a guard blocks the whole class of a mistake, the entry moves
to `guards.md` in the same PR.

## Working with agents

_No entries yet._

## Verify and Done

_No entries yet._

## Shipping and CI

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

_No entries yet._
