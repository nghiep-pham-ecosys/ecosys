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

### Copy a lane's test command from the repo README or CI
- Why: a brief composed `unittest discover -s <abs>/tests -t <abs-root>`, which fails in a repo whose `tests/` has
  no `__init__.py` → the command was written from memory, not taken from the repo.
- How: paste the test command exactly as the README or the CI workflow runs it, with `cd <worktree>` in a subshell.
- Seen: process-sim-lab lane, 2026-11-18
- Guard: none yet; candidate: the brief template's `Test:` line says "copied from README or CI"

### Check which Notion workspace a session reaches before the first Notion call
- Why: at session start the inbox page returned 404 and no routines were listed → the client was signed into another
  claude.ai account, and a claude.ai connector (and the routine list) follows that account; one Notion connection
  reaches one workspace.
- How: use the project MCP server `notion-ecosys`; call `notion-get-self` first and stop all Notion calls unless it
  names the `workspace` in `private/ops/notion.yaml`. Before touching a routine, check that `RemoteTrigger list`
  shows the routines in `ops/automations.md`.
- Seen: ecosys#35, 2026-11-16
- Guard: test .claude/hooks/tests/test_settings.py (keeps the `notion-ecosys` server); the workspace check itself is
  session Start step 0 (ecosys#36)

### Leave a lane worktree before shipping from the main session
- Why: after `cd` into a `.tmp-session/wt/` worktree, the main session's shell stayed there, so ship-guard treated
  the next `git push` as a lane push and blocked it → the shell cwd persists between tool calls.
- How: commit inside the worktree, then `cd` back to the workspace root in its own call before pushing or merging.
  Write worktree paths literally; worktree-guard rejects paths built from shell variables.
  `git -C <worktree> push` is blocked the same way: push with `git -C <repo clone> push -u origin <branch>`.
- Seen: workspace session 1, 2026-11; 2026-11-13 (a commit-and-push one-liner that named the worktree path);
  ops#30, 2026-11-16 (`git -C` into the worktree for the push); ops#40, 2026-11-16 evening (a push in the same
  command line as a worktree path, and `gh issue create` from a shell left in a worktree); lab-to-prod#33 and
  process-sim-lab#7, #8, 2026-11-17 (push or merge chained with a worktree command, 4 blocks); S9 2026-11-18 (ops#54 and vault#3: `cd` into the lane worktree in the same command as the push); S10
  2026-11-18 (4 blocks: `cd` into a worktree for `just ci`, then a push; a commit and a push in one line; `gh project
  item-edit` in one line with a worktree commit; `git log` of worktrees in one line with `tools/ship/stack-merge --help`)
- Guard: hook ship-guard (blocks the push; this lesson explains the fix)

### Check the repo before building what an issue says is missing
- Why: physic-ai-for-everyone#16 said lesson 01 had no exercises, but 4 existed; only the test that runs them was
  missing → the issue's premise was taken as fact.
- How: grep the repo for the thing first; build only the gap and say so in the PR.
- Seen: physic-ai-for-everyone#16, 2026-11-17
- Guard: lane brief "Read first" (skills/core issue-and-brief)

### A rule that sorts items by a field names where the field lives
- Why: the two-budget rule split items by owner, but no board field or issue section held an owner → an agent could
  not apply it.
- How: name the source (board field, issue-body section or file) and the default when it is missing.
- Seen: ecosys#42, 2026-11-17
- Guard: reviewer-correctness

## Verify and Done

### Copy a physical constant or citation from the primary table, never from memory
- Why: a lane nearly wrote Antoine constants and a textbook example from memory → plausible numbers are not sources.
- How: open the primary table (for example the NIST WebBook page), copy each value with its valid range and the
  access date. When no example can be checked, build the test so its answer is known exactly and say so in the test.
- Seen: process-sim-lab#4, #5, 2026-11-17
- Guard: reviewer-correctness recomputes test values and checks citations

### Compute a hand-checked number with code before it goes into a test
- Why: a test comment number typed from mental arithmetic was wrong → a hand check is only as good as its arithmetic.
- How: compute the value with a one-line script and paste the printed digits.
- Seen: process-sim-lab#5, 2026-11-17
- Guard: reviewer-correctness recomputes test values

_No entries yet._

### Look for a routine's output before saying it ran
- Why: a plan said a routine ran on 14/11, but the repo had no branch or PR from it → a schedule was read as a run.
- How: find the PR, branch or log line the run should have left; otherwise write "unverified".
- Seen: ops#45, 2026-11-17
- Guard: hard rule 10 (live status) + automations.md "last verified run" column

### After a decision lands early, update every later slot that waits for it
- Why: ADR 0005 merged on 17/11 while the master plan still had a W48 draft slot, a 29/11 decision and an open risk
  for it → only the item itself was updated.
- How: grep the plan and schedule for the decision's name and fix each row in the same PR.
- Seen: ops#43, 2026-11-17
- Guard: none yet (weekly review drift check)

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
### A `ci-result` job names its core jobs and allows only intended skips
- Why: an aggregate that fails on any skipped job breaks repos with dispatch-only or disabled jobs, and one that
  passes on skipped jobs hides a broken core job.
- How: require `needs.<core>.result == 'success'` for each core job; accept `skipped` only for named optional jobs.
- Seen: claude-for-everyone-vi#14, 2026-11-17
- Guard: ci claude-for-everyone-vi `ci.yml` `ci-result` job

### `just ci` in a child-repo worktree may run the root recipe
- Why: `ops` has no `justfile`. Its worktree sat under `.tmp-session/wt/` inside the root repo, so `just` searched
  upward and ran the root `ci` recipe; a PR body then claimed a local check for `ops` that never ran → the evidence
  named a command without checking which repo it belonged to.
- How: before citing `just ci`, check that `<repo>/justfile` exists. Without one, cite the PR's CI checks and any
  script you ran by name.
- Seen: ops#26, 2026-11-15
- Guard: none yet (candidate: an `ops` justfile with a `ci` recipe)

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
- How: merge the whole stack with `tools/ship/stack-merge --repo <o>/<r> <bottom> ... <top>`. It retargets the next
  PR to `main` before each merge, merges through `tools/ship/merge`, updates the next branch on GitHub and waits for
  its checks. By hand, the same order applies; with gh 2.45 use `gh api -X PATCH repos/<o>/<r>/pulls/<n> -f base=main`
  (`gh pr edit --base` fails on a Projects-classic field).
- After a squash merge, the next branch still carries the bottom commit and can conflict with its squashed copy on
  `main`; `stack-merge` stops there. Without a force-push that Nghiep named, cherry-pick the top commit onto a new
  branch from `main`, open it as a new PR and close the old one.
- Seen: lab-to-prod stack #1–#8, 2026-11; lab-to-prod#41–#44, 2026-11-17 (four manual steps per PR, two merge
  conflicts and a worktree push block); process-sim-lab#20–#21, 2026-11-18 (conflict after the squash; #22 replaced #21)
- Guard: tool `tools/ship/stack-merge` (test tools/ship/tests/test_stack_merge.py); skills/ship §3 names it

### A recreated repository may not start Actions until its Actions permission is set again
- Why: after deleting and recreating a public repo, pull_request events fired but no workflow run was created until
  the repository Actions permission was written once (`PUT repos/<o>/<r>/actions/permissions`) → new repos inherit
  the org policy on paper but did not trigger runs.
- How: after creating or recreating a repo, PUT its Actions permissions (`enabled=true`, `allowed_actions=selected`),
  then close/reopen open PRs and confirm a run appears before waiting on checks.
- Seen: lab-to-prod recreation, 2026-11
- Guard: ritual step in docs/runbooks/new-project.md

### Rerun a workflow whose check stays pending after the run completed
- Why: a gitleaks job still showed `in_progress` on the PR while its run was `completed` with `success`, so
  `tools/ship/merge` kept waiting → GitHub did not refresh the job status on the check.
- How: if `gh run view <id>` says completed but the check is still pending after 2 min, run `gh run rerun <id>`
  and wait for the new run. Never merge around the tool.
- Seen: ops#33, 2026-11-16
- Guard: none: external GitHub check status not refreshed

### A validator that starts requiring a field plans the existing data in the same change
- Why: requiring `work:` from W48 made every W48+ calendar item invalid, so the PR had to park them all to pass its
  own CI → the rule was added without its data migration.
- How: in the same PR, fix or park the data past the start date, and say which follow-up PR fills it again.
- Seen: lab-to-prod#34, 2026-11-17
- Guard: the validator's own test on the real calendar

### A PR that enforces a convention updates every doc that states the old one
- Why: a pr-title check was added while CONTRIBUTING, CLAUDE.md and the PR template still taught the old title form.
- How: grep for the old form and change it in the same PR.
- Seen: physic-ai-for-everyone#17, 2026-11-17
- Guard: reviewer-correctness

### Read issues with `gh issue view --json`
- Why: plain `gh issue view` exits 1 on these repos: its query asks for Projects (classic) cards, which are retired.
- How: `gh issue view <n> -R <repo> --json title,body,comments`.
- Seen: lab-to-prod lanes, 2026-11-17
- Guard: none (tool behaviour)

## Publishing

### Check the live profile and the publish record before any manual post
- Why: two posts were made by hand in the browser, but the scheduling tool and the study log still said "waiting
  for approval", so the next session almost posted one of them again → the only record of "posted" was a tool that
  never saw the manual post.
- How: before posting by hand, open the live profile and run `python -m publish.record_manual check` in
  lab-to-prod; right after, run `record` with the live URL. Reports read `published.json` before saying "waiting".
- Seen: 2026-11-13
- Guard: lab-to-prod `publish/record_manual.py` + CLAUDE.md rule (lab-to-prod#13)

### Record a manual X post with the time from its status id
- Why: a manual record took `at` = the time of recording, so the 2026-11-17 post reads as posted a day late → the
  tool defaults `--at` to now, and the post time was not known when the link arrived.
- How: an X status id holds its time: `(id >> 22) + 1288834974657` ms since the epoch. Pass that as `--at`.
- Seen: 2026-11-18 (S9 record of 2026-11-17; S10 recorded 2026-11-18 correctly)
- Guard: none yet; candidate: `record_manual` derives `at` from an x.com status URL (after the 2026-12-13 freeze)

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

### Never trust a GitHub `schedule` cron for a wall-clock deadline
- Why: in this org every measured scheduled run started 4.5–8.5 h late and none on time: publish (cron 01:15Z) ran
  07:34–09:09Z on 13, 14, 16 and 17 Nov; blog (01:20Z) 07:37–09:14Z; metrics (15:00Z) 19:31–23:33Z;
  claude-for-everyone-vi weekly (01:00Z) 05:39–07:30Z. The 16/11 fix added a backup cron 45 min later; on 17/11
  both crons fired about 8 h late, so a 08:15 post went out at 16:09 → the fix assumed the scheduler skips a run
  now and then, but here it delays every run by hours.
- How: use `schedule` only for jobs with no deadline. For a fixed-time job, start early and wait in the job
  (lab-to-prod `tools/wait_until.py`), trigger `workflow_dispatch` from a scheduler that keeps time, or use the
  channel's own scheduling. Measure with `gh run list --event schedule` before trusting a cron.
- Seen: lab-to-prod#29, 2026-11-16; lab-to-prod#32, 2026-11-17
- Guard: ci lab-to-prod publish.yml and blog.yml early crons plus `tools/wait_until.py` (lab-to-prod#33)

## Public-safe and privacy

### Strip claude.ai session links from routine PRs before the merge
- Why: the first cloud-routine PR (process-sim-lab#18) carried a `Claude-Session:` commit trailer with a session URL
  and a footer with the same link, and was opened as a draft → the cloud client adds them by default and
  the routine instructions did not forbid them.
- How: before merging a routine PR in a public repo, read the body and commits for `claude.ai/`; edit the body
  (the squash message is the PR body in these repos, so `main` stays clean); mark a draft ready. The branch commit
  stays visible in the PR's commit list.
- Seen: process-sim-lab#18, 2026-11-18
- Guard: process-sim-lab `.claude/routine.md` §4 (process-sim-lab#19); candidate: a CI check that fails on
  `claude.ai/` in a PR body or commit of a public repo

### A public file must not list the names it is meant to hide
- Why: a banned-terms list and its tests held the protected names in plain text in a public repo, so the guard
  published the exact list it was meant to protect → the check was designed around a readable list instead of a
  secret one.
- How: store only salted or unsalted hashes of the names in public files, or keep the list local and out of git.
  Test fixtures use synthetic names (Example Co, Acme).
- Seen: lab-to-prod PR #1, 2026-11
- Guard: hook pre-push denylist scan (local denylist, never committed) + ci hash-only check in public repos (spec §10.2)

### A parse check in a repo with personal data prints the location, not the parser message
- Why: a YAML parser's error text includes the offending source line, so a CI parse check would copy private content
  into the log.
- How: print file, line and a fixed problem text; never `str(exception)`.
- Seen: vault#1, 2026-11-17
- Guard: vault `tools/check-yaml`

### Every value in a guard's block message goes through the mask
- Why: with no manifest, the public-safe guard printed a repo name taken from the command unmasked, so a listed term
  could leak through the block message itself.
- How: route names, paths and terms through `mask()` before printing.
- Seen: ecosys#8, 2026-11-17
- Guard: hook public-safe-guard tests

### Write text that names the denylist path with the Write tool, not in a Bash command
- Why: secret-path-guard scans command text for the path, so a heredoc that edited docs mentioning it was blocked.
- How: edit such docs with Write/Edit or a script file.
- Seen: ecosys#8, 2026-11-17
- Guard: hook secret-path-guard (by design)

### Branch from the session worktree itself, never after `cd` into the workspace root
- Why: `cd <workspace root> && git checkout -b <branch>` from a Claude Code session worktree moved the main ecosys
  checkout onto the new branch while the commit landed in the session worktree, so the first push sent an empty
  branch → the root checkout and the session worktree are two working trees of the same repo.
- How: in a session worktree, run `git checkout -b` in the session cwd with no `cd`; use `git -C <repo>` for any
  other repo.
- Seen: ecosys#53, 2026-11-18
- Guard: none yet (candidate: worktree-guard warns on `checkout -b` in the workspace root from a session worktree)

### Prove a concurrency test fails without the fix
- Why: race tests often pass by luck; the mock-lock test in claude-for-everyone-vi#21 was trusted only after it
  failed 3 of 3 runs with the lock removed (forced with `sys.setswitchinterval(1e-6)`).
- How: revert the guard temporarily, run the test, restore it, and note the result in the lane summary.
- Seen: claude-for-everyone-vi#21, 2026-11-18
- Guard: lane habit; ask for it in the lane brief when the change is about threads

### A child-repo lane worktree is not the session worktree
- Why: the harness Write tool refused files under `.tmp-session/wt/<lane>` of a child repo because it took them for
  the base checkout of the root repo; the lane had to write with Bash heredocs.
- How: before writing another way, check that the path is the lane worktree named in the brief; write with Bash
  there, never in the root checkout.
- Seen: claude-for-everyone-vi#22 and vault#3, 2026-11-18
- Guard: none yet (candidate: teach the hook about `.tmp-session/wt/` lanes)

## Data and tools

### Run a src-layout package's tests with PYTHONPATH=src in a fresh worktree
- Why: `unittest discover` in a new worktree failed on import → CI installs the package first, a worktree does not.
- How: run `PYTHONPATH=src python3 -m unittest discover -s tests`, or install it editable in a venv under
  `.tmp-session/`; name the local test command in the lane brief.
- Seen: process-sim-lab#3, 2026-11-17
- Guard: lane brief Test line (skills/core issue-and-brief)

### Commit with the GitHub noreply address in every workspace repo
- Why: a privacy review found the personal e-mail as author on a PR commit → identity came from the global git
  config; squash merges hide it on `main`, but PR commits stay readable on GitHub.
- How: once per machine, `includeIf "gitdir:~/projects/nghiep-pham-ecosys/"` in `~/.gitconfig` points to a file
  that sets `user.email` to the GitHub noreply address (`agents/steering/machine-notes.md`). Check with
  `git config user.email` in any workspace repo before the first commit on a new machine.
- Seen: ecosys PR #36, 2026-11-16 (earlier PRs too)
- Guard: none: external machine git config, outside the repos

### zsh does not split a variable into words
- Why: `set -- $spec` in a polling loop left `$2` empty under zsh, so the loop spun for 10 minutes on a usage
  error → the agent shell is zsh, and zsh does not word-split unquoted parameters.
- How: use `${=spec}`, `cut`, or `name:number` pairs split with `${s%%:*}` and `${s##*:}`. `mise exec -C <dir>`
  also changes the working directory, so pass absolute file paths to it.
- Seen: S10, 2026-11-18
- Guard: none (this lesson)

### Read a scratch file before deleting it
- Why: `.tmp-session/lessons-pending.md` was deleted after one entry was moved, without reading it first; any entry
  an earlier session left there would be lost → the delete assumed the file held only what this session wrote.
- How: `cat` the file, move every entry, then delete. The same holds for `checklist.md` and `drafts.md`.
- Seen: 2026-11-13
- Guard: ritual step (session End step 3)

### Fetch before reading ahead/behind
- Why: at session start `just ws-status` showed `ops` at +0/-0, but `origin/main` already had one more commit merged
  the evening before → the status read local remote refs without fetching, so it reported an old snapshot.
- How: run `just ws-sync` (or `git fetch`) before `just ws-status`, and say which one ran when reporting state.
- Seen: ops, 2026-11-16
- Guard: none: judgement until ws-status fetches itself (candidate change to tools/ws)

### Render a local Copier template with an explicit `--vcs-ref`
- Why: without a ref, Copier renders the latest tag, not the working tree, so template tests would check old code
  once v0.1.0 is tagged.
- How: pass `--vcs-ref HEAD` in tests; pass a tag for releases.
- Seen: tmpl-project v0.1, 2026-11-17
- Guard: tmpl-project tests

### Check a download against a checksum file by fields, not by an exact line
- Why: `sha256sum` binary mode writes `<sha> *<file>`; an exact two-space grep failed every CI install.
- How: compare the hash and file name fields and strip a leading `*`.
- Seen: tmpl-project v0.1, 2026-11-17
- Guard: tmpl-project `scripts/install-tools` tests

