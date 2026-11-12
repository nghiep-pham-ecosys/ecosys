# ADR 0001: Workspace topology

- **Status:** Accepted
- **Date:** 2026-11-12

## Context

Personal work is spread over many repos, docs and tools. Several repos already exist, each with its own history and CI (`lab-to-prod` and others). Some data must stay private (job search, plans, profile facts); some repos are public.

Draft v0.2 of the spec proposed one public monorepo. Nghiep already works every day in a multi-repo workspace: one root repo for rules and docs, with child repos cloned under it.

## Decision

Use a multi-repo workspace in one GitHub org, `nghiep-pham-ecosys`.

- The root repo `ecosys` (public) is the workspace folder. It holds rules, steering, skills, hooks, tools, ADRs and `repos.yaml`.
- Child repos are cloned under it, each with its own `.git`:
  - `meta/` for org-level repos (`.github`, later `tmpl-project`);
  - `private/` for `ops` and `vault`;
  - `projects/` for project repos.
- The root `.gitignore` excludes `meta/`, `private/`, `projects/`, `.tmp-session/`, `import/` and `.env*`. CI fails if any path under the child folders is tracked.
- `repos.yaml` lists every repo. `tools/ws/sync` and `tools/ws/status` work from it.
- Existing personal repos move into the org by transfer (history, issues and PRs kept). Nghiep approves each transfer.
- Sessions start at the root, so the root `CLAUDE.md` applies everywhere. Each child repo has a short `CLAUDE.md` that points back to the root.

## Consequences

- Each repo keeps its own history, CI and visibility. Public and private data split cleanly by repo.
- Habits and tools from the day-job workspace carry over without change.
- Cross-repo changes need one PR per repo. Shared code has to be copied for now.
- `ws-sync` and `ws-status` are needed to keep many clones in step.
- Transferred repos change URLs. GitHub redirects them, but remotes and Pages config are updated by hand.

## Revisit when

Two repos need to share code and copying it becomes a chore. Then add a `packages` repo or merge just those two.
