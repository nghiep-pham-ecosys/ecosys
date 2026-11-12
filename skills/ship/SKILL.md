---
name: ship
description: The path from a branch to "Done" in the nghiep-pham-ecosys org. Covers branch and worktree naming, the commit and PR title format with "Refs <repo>#<n>", checks before merge, merging only through tools/ship/merge, the difference between public repos (rulesets) and private repos on the Free plan (pre-push hook plus merge tool), verifying after merge, marking a board item Done with evidence, and rollback. Use it when a PR is ready, a check is red, before any merge, or before moving an item to Done. It does not cover writing issues or lane briefs (core), session rituals (session), or publishing posts and submitting applications, which always need Nghiep (content, jobs).
---

# ship

"Done" means verified, with evidence (spec §9.5, P3). A merged PR alone is not Done.
Read the lessons for "Shipping and CI" and "Verify and Done" before merging (`lessons`).

## 0. Who does what

- **Orchestrator** (main session): push, open PRs, run `tools/ship/merge`, verify, set board status.
- **Lane / subagent**: code, test, commit locally in its worktree. `ship-guard` blocks push, `gh pr create/merge`,
  `gh workflow run`, `git reset --hard`, `git clean -f`, `--no-verify` and write API calls from inside
  `.tmp-session/wt/`. A lane returns the steps it needs as "live steps for the orchestrator".
- **Nghiep**: approves anything that goes out to people (posts, applications, messages), money, deletes, visibility
  changes, transfers, and the one-off force-push of a named branch.

## 1. Branch, commit, PR

- Worktree: `git -C <repo> worktree add /home/nghiep/projects/nghiep-pham-ecosys/.tmp-session/wt/<session>-<lane> -b <type>/<n>-<slug> origin/main`.
  Always an absolute path (`worktree-guard`). Fetch first so `origin/main` is current.
- Branch: `<type>/<n>-<slug>`, for example `docs/12-org-runbook`.
- Commit subject: `type: description` in English, no issue number.
  Types: `feat`, `fix`, `chore`, `refactor`, `docs` (the `pr-title` check is the source of the allowed list).
- Commit body: a line `Refs <repo>#<n>` (several: `Refs ecosys#12, ops#4`).
- **Never** `Fixes`, `Closes`, `Resolves` or their variants anywhere in a commit or PR body. GitHub closes the issue on
  merge, before anything is verified. Close it by hand in §5.
- PR title = the squash commit subject: `type: description`. PR body: what and why, how it was tested, `Refs` line,
  and "Docs impact: …" (or "none").
- Public repo: before pushing, re-read the diff, title and body for names, salaries, contact details and claude.ai
  links (spec §10.2). The pre-push denylist scan is the guard; reading is the habit.

```
docs: add org setup runbook

Refs ecosys#12
```

## 2. Before merge

- [ ] `just ci` green locally in the target repo.
- [ ] Every check in `gh pr checks <n>` is green. Read all checks, not only the required ones. Pending is not green.
- [ ] Anything pushed to the PR after the last green run (a fix, a rebase, a bot) → wait for the new run.
- [ ] **Risky PR** (hooks, CI or workflows, permissions, secrets handling, deletes, profile or post text, public
      README) → a reviewer agent with the privacy lens and one with the correctness lens read the diff. Fix every
      blocker before merge.
- [ ] Red locally green in CI, or the reverse → compare tool versions (`mise ls`, `.mise.toml`) before changing code.
- [ ] Not a draft, no conflicts with `main`.

## 3. Merge

Only through `tools/ship/merge` (raw `gh pr merge` is denied in settings and blocked by `ship-guard`). The tool:

- refuses drafts, conflicts, and any red, pending or missing check;
- reads the checks twice, about 20 s apart, so a run that starts late is not missed;
- merges with `--squash --match-head-commit <sha>`, so a push that lands during the check is never merged unchecked.

Run `tools/ship/merge --help` for its arguments. If it refuses, fix the cause; never work around it.

**Public repos** have a ruleset on `main`: PR required, squash only, required checks `ci-result` and `pr-title`, no
force push, no deletion.

**Private repos** (`ops`, `vault`, private projects) cannot have rulesets on the Free plan *(verify)*. They rely on:

- the committed pre-push hook (`.githooks/pre-push`, enabled with `git config core.hooksPath .githooks`) that runs
  gitleaks. Check `git -C <repo> config core.hooksPath` prints `.githooks` before the first push. No hook → no push.
- the same PR flow and `tools/ship/merge` as public repos. Direct pushes to `main` are not used, even though GitHub
  would allow them.

## 4. Verify after merge

- CI on `main` green: `gh run list -R <org>/<repo> --branch main --limit 3`.
- Something deployed or published by the merge (blog, Pages site, scheduled workflow): verify the real thing. A URL
  returns 200 with the expected content, or the workflow run is green. Record the link or command output.
- Pull the merged `main` into the local clone (`just ws-sync`) and remove the worktree.

## 5. Done with evidence

Move a board item to `Done` only when every "Done when" line has evidence. Put the link in the `Evidence` field and
a short comment on the issue:

```markdown
Verified <YYYY-MM-DD HH:MM>
- <Done-when line 1> — <PR / run / URL / command output>
- <Done-when line 2> — <evidence>
```

Then close the issue by hand (`gh issue close <n> -R <org>/<repo> --reason completed`).

- "Done when" is frozen once the item is `In progress`. New scope found on the way → a new issue.
- Part of the scope verified, part not → the item stays `In progress` with what is left, or the rest moves to a new
  issue that Nghiep agrees to, and the comment says so.
- Evidence missing → not Done. Write what is missing.
- Non-code items (an application, a post, a course module): the artifact exists and is linked: confirmation mail,
  post URL, certificate or progress screenshot stored in `ops` (spec §9.5).

## 6. Rollback

- Revert through the same flow: `git revert <sha>` on a new branch → PR → checks → `tools/ship/merge` → verify.
- Never force-push `main`. A force-push of any other branch needs Nghiep to name that branch.

## Maintenance

Follow `skills/README.md`. When a check starts enforcing a line here (for example the PR body rule), shrink the line
to the check's name.
