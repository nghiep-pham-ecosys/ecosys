# ecosys

The root repo of `nghiep-pham-ecosys`: a personal workspace kept as code.

It holds the rules, skills, guard hooks, small tools and decisions that one person and a set of coding agents use to run job search, learning, content and side projects from one board, within a weekly time budget.

## What is here

| Path | What |
|---|---|
| `CLAUDE.md`, `AGENTS.md` | rules for coding agents |
| `CONTEXT.md` | map of areas, repos, runners and data homes |
| `agents/steering/` | workflow, language and style, data rules, machine notes |
| `skills/` | one skill per flow: session, ship, lessons, jobs, weekly review |
| `.claude/hooks/` | guard hooks that block unsafe agent actions, with tests |
| `tools/` | workspace sync and status, merge tool, job pipeline checks |
| `docs/` | spec, ADRs, runbooks, standards |
| `repos.yaml` | the list of public-safe repos in the org (a private overlay lists the rest) |

Other repos are cloned under `meta/`, `private/` and `projects/`. They are not part of this repo.

## Quick start

```sh
mise install
just ws-sync
just ws-status
just ws-workspace   # optional: local VS Code workspace with every repo
just ci
```

## Principles

Capacity first. Everything as code. Evidence over claims. One home per fact. Free tools only. Private data stays private. Guards over good intentions.

This is a personal setup, not a product. Issues and PRs from outside are not expected.
