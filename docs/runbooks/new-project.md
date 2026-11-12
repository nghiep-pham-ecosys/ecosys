# Runbook: new project

How a project repo enters the workspace. Two cases: a new repo, or an existing repo moved from the personal account.

## Before you start

- **One new project at a time** (spec §2.2). A new `lab` project starts only when another one is paused, with `Status: Paused` and a reason on the board.
- Creating a repo, transferring a repo and choosing public visibility each need Nghiep's yes (ADR 0003).
- Anything owned by or related to an employer or client never enters the org.

## Case A: new repo

1. Create it in the org. Until `tmpl-project` exists `[P1]`, start empty:
   `gh repo create nghiep-pham-ecosys/<repo> --private --clone`
   Choose `--public` only with a yes. Run the command from `projects/`.
2. Add the basics:
   - `README.md`: what it is, how to run it.
   - `CLAUDE.md`: two or three lines saying what the repo is, then "Rules: see `../../CLAUDE.md`." It imports nothing.
   - `project.yaml` `[P1]`: name, area, status (`active|paused|done`), stack, highlights, links, visibility.
   - CI: gitleaks and `pr-title`, plus the project's own tests, with one aggregate `ci-result` job. Pin actions by full SHA. Only allowed actions run (ADR 0002).
   - `justfile` with a `ci` recipe.
3. Private repo: install the pre-push hook (gitleaks) before the first push:
   `git -C projects/<repo> config core.hooksPath .githooks`
4. Public repo: turn on secret scanning, push protection and Dependabot alerts; add the `main` ruleset (runbook `org-setup.md`, items 7 and 8). The required checks must exist in that repo: a repo without `ci-result`/`pr-title` requires its own CI check instead (lab-to-prod requires `validate`).
5. Write the repo's Actions permission once, even though the org policy already allows it, then open or reopen a PR and confirm a run appears (lesson "A recreated repository may not start Actions…"):
   `gh api -X PUT repos/nghiep-pham-ecosys/<repo>/actions/permissions -F enabled=true -f allowed_actions=selected`
6. Register it (see "Register" below).

## Case B: move an existing repo (spec §4.4)

1. Check the local clone: `git -C ~/projects/<repo> status -sb` and open PRs. Report uncommitted work. Transfer and `mv` keep both.
2. Transfer (needs a yes for this repo):
   `gh api -X POST repos/pqnghiep1354/<repo>/transfer -f new_owner=nghiep-pham-ecosys`
   Wait until `gh repo view nghiep-pham-ecosys/<repo>` works.
3. Move the clone and repoint it:
   `mv ~/projects/<repo> ~/projects/nghiep-pham-ecosys/projects/<repo>`
   `git -C ~/projects/nghiep-pham-ecosys/projects/<repo> remote set-url origin https://github.com/nghiep-pham-ecosys/<repo>.git`
   `git -C ~/projects/nghiep-pham-ecosys/projects/<repo> fetch`
4. Check what points at the old owner:
   - GitHub Pages: the URL changes from `pqnghiep1354.github.io/<repo>` to `nghiep-pham-ecosys.github.io/<repo>`. Update `site`/`base` and canonical URLs in a PR before the next public post.
   - Webhooks, deploy keys, OAuth apps.
   - Workflows that use actions outside the org allowlist: they will fail until the action is allowed or replaced.
5. Ask Nghiep to reopen any editor or Claude session that used the old path.
6. Merging a stack of PRs after the move: retarget the next PR to `main` before each merge, then rebase it onto the new `main` (lesson "In a PR stack…").
7. Register it (below). A repo that would reveal private matters (a take-home for an application, for example) goes in `private/ops/repos.private.yaml` instead of the public `repos.yaml`.

## Register

1. Add one line to `repos.yaml`: name, path `projects/<repo>`, visibility, area, `default_branch: main`.
2. Add a folder entry to `nghiep-pham-ecosys.code-workspace`.
3. Add the topic `project` on GitHub.
4. Add a row to the repos table in `CONTEXT.md`.
5. Run `just ws-status`: the repo shows clean on `main`.
6. Add a board item for the first piece of work, within the area's WIP limit.
