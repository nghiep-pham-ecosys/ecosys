# AGENTS.md

This file is for agent tools other than Claude Code (Kiro, Codex and similar).
The rules are the same for every agent. They live in one place:

1. **`CLAUDE.md`**: root agent rules. Read it first, including the hard rules and the overrides.
2. **`CONTEXT.md`**: whole-system map (areas, repos, runners, data homes).
3. **`agents/steering/`**: workflow, language and style, data rules, machine notes.
   Kiro reads these through `.kiro/steering -> ../agents/steering`.
4. **`skills/<name>/SKILL.md`**: one skill per flow (`core`, `session`, `ship`, `lessons`, `jobs`, `weekly-review`).
   Read the skill that matches the task before you start.
5. **`docs/spec.md`**: the contract. **`docs/adr/`**: the decisions.

Rules that matter most for a non-Claude agent:

- Work only in a worktree under `.tmp-session/wt/` when you are a lane.
- Do not push, merge, open PRs, run workflows or write to external systems.
- Do not read `.env*`, keys, sops files or the local denylist.
- Write public-safe text everywhere except `private/` (see `docs/standards/public-safe-writing.md`).
- Code, commits, PRs, issues and docs in English.

If this file and `CLAUDE.md` disagree, `CLAUDE.md` wins. Report the drift.
