# nghiep-pham-ecosys: agent rules (root)

## Identity & scope

- Personal workspace of one person: Nghiep (GitHub `pqnghiep1354`, id `65300490`).
- Org: `nghiep-pham-ecosys`. Root repo: `ecosys` (this folder, branch `main`).
- Areas: `jobs`, `learn`, `content`, `lab`, `ecosys` (plus `profile` facts in `vault`).
- The contract is `docs/spec.md`. The whole-system map is `CONTEXT.md`.

## Overrides

This file replaces the global day-job rules for every session opened in this workspace.

- No AWS commands, no day-job accounts, profiles or trackers.
- No `handoff.md`. Session state lives in `private/ops` (memory block and session log, skill `session`).
- Claude Chat ↔ Claude Code talk only through the Notion inbox page (`inbox` in `private/ops/notion.yaml`): read
  today's `Chat` line at session start, prepend a `CC` line at session end (skill `session`, Start step 0 and End step 7).
- Issue refs are `<repo>#<n>` (for example `Refs ecosys#12`). Day-job issue keys never appear here.
- Only the ways of working carry over from the day job (spec §10.3). Nothing else does.

## Workspace map

- Root repo `ecosys` holds rules, steering, skills, hooks, tools, ADRs and public-safe docs.
- Child repos are cloned under `meta/`, `private/` and `projects/`. Each has its own `.git`.
  The root `.gitignore` excludes them, and CI fails if any path under them is tracked.
- `repos.yaml` is the list of repos (name, path, visibility, area, default branch). Repos whose names must stay out of
  public files are listed in the private overlay `private/ops/repos.private.yaml` (same schema), which the `ws` tools
  merge when it exists.
- `.tmp-session/` is gitignored scratch: `wt/<session>-<lane>/` worktrees, `checklist.md`, `lessons-pending.md`.
- `skill/` and `import/` are local, gitignored and read-only. They never feed a public file.

## Hard rules (MUST)

Each rule names what enforces it.

| Rule | Guard |
|---|---|
| Start sessions at the workspace root. Read `CONTEXT.md`, then the target repo's `CLAUDE.md`. | ritual (skill `session`) |
| Plan within the `capacity.yaml` budgets and WIP limits. | skill `weekly-review` |
| Lanes work in worktrees under `.tmp-session/wt/` only. | hook `worktree-guard` |
| Subagents never push, merge, open PRs or run workflows. | hook `ship-guard` |
| Merge only through `tools/ship/merge`. Raw `gh pr merge` is blocked. | hook `ship-guard` + deny list |
| Never read `.env*`, keys, sops files, `~/.config/sops/**` or the local denylist. | hook `secret-path-guard` |
| No paid API or paid service without an explicit yes, with the monthly cost stated first (P5). | ADR 0003 |
| Never submit an application, publish a post or send a message without Nghiep (P8). | ADR 0003 |
| Personal data lives only in `private/ops` or `private/vault`. Everything else is public-safe. | denylist + pre-push hook |
| Nothing from the day job or clients except ways of working (spec §10.3). | denylist + reviewer-privacy |
| Never state live status from memory. Check it, or label it *unverified*. | ritual |

Stop points that always need Nghiep are listed in `docs/adr/0003-approvals.md`.

## Sources of truth

Precedence: **repo > canonical doc > memory > skill**.
Each fact has one home (see `CONTEXT.md`, "Where each fact lives").
Report drift between records and reality. Never resolve it silently.

## Imports

@agents/steering/workflow.md
@agents/steering/language-and-style.md
@agents/steering/data-rules.md
@agents/steering/machine-notes.md

## Which skill when

| Situation | Skill |
|---|---|
| Unsure which rule or skill applies; hard rules, roles, brief template | `skills/core/SKILL.md` |
| Session start or end, checklist, memory block, session log | `skills/session/SKILL.md` |
| PR ready, checks, merge tool, verify, Done with evidence | `skills/ship/SKILL.md` |
| A root cause found, a repeated mistake, "note this lesson" | `skills/lessons/SKILL.md` |
| Applications, stages, 30-day rule, form filling, sources | `skills/jobs/SKILL.md` |
| Sunday review, weekly plan, capacity and WIP check | `skills/weekly-review/SKILL.md` |
| Learning tracks and deadlines `[P1]` | `skills/learn/SKILL.md` |
| Posts and blog (points to lab-to-prod) `[P1]` | `skills/content/SKILL.md` |
| CV from facts `[P1]` | `skills/cv/SKILL.md` |

Claude Code reads skills through `.claude/skills -> ../skills`. Kiro reads steering through `.kiro/steering`.

## Commands

| Command | Does |
|---|---|
| `just ws-sync` | Clone missing repos from `repos.yaml`; fast-forward clean repos on their default branch. Reports dirty or off-branch repos and leaves them alone. |
| `just ws-status` | One line per repo: branch, dirty count, ahead/behind, open PRs. |
| `just ws-workspace` | Write the gitignored `nghiep-pham-ecosys.local.code-workspace`: public folders plus the private-manifest repos. |
| `just ci` | Run the local checks: hook and tool tests, tracked-children, actionlint, gitleaks, denylist scan. |
| `just jobs-check` | Run `tools/jobs/check` on `private/ops/jobs/applications.yaml`. |
| `just digest` `[P1]` | Build the daily digest sections. |
| `just review` `[P1]` | Build the weekly review draft. |
