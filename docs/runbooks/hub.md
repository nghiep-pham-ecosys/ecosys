# Runbook: the Claude Code hub

The hub is one long-running Claude Code Remote Control server at the workspace root. From 2026-W48 it is the single
place where Nghiep gives work, from the phone or the laptop. Rules: `skills/session/SKILL.md` ("Hub"),
`skills/daily-start/SKILL.md`. Approval rules do not change (ADR 0003, ADR 0006 §1).

## Start

```bash
just hub
```

- Runs `claude remote-control --spawn worktree --name hub` from the workspace root (`tools/hub/start`).
- Runs inside the tmux session `hub` when tmux is installed. A second `just hub` reattaches; `Ctrl-b d` detaches and
  the hub keeps running. `just hub --no-tmux` runs in the current terminal. `just hub --dry-run` prints the command.
- Each session opened from the app gets its own git worktree under `.claude/worktrees/` (managed by Claude Code).
  Lanes briefed by the hub still go under `.tmp-session/wt/` (hook `worktree-guard`).
- The machine must stay awake. The hub stops when WSL or the laptop sleeps; run `just hub` again after a restart.

## One-time settings

Set once in `~/.claude/settings.json` (or `/config` in a terminal session):

| Setting | Value | Why |
|---|---|---|
| `remoteControlAtStartup` | `true` | every local session is reachable from the app |
| `agentPushNotifEnabled` | `true` | push to the phone when a session finishes |
| `inputNeededNotifEnabled` | `true` | push when a session waits for Nghiep |

On the phone: Claude app → Code tab → the session named `hub`. Allow notifications for the Claude app.

## Account

- The hub runs on the claude.ai account the local client is signed into. Switch with `/login` inside the hub.
- The hub is not listed in the app although it says "Connected" → compare `claude auth status` with the app's
  account; on a mismatch run `claude auth logout` and `claude auth login`, start the hub again, then `/mcp` →
  `notion-ecosys` → Authenticate in a normal `claude` session.
- Remote Control sessions belong to that account: after `/login` to another account, open the app with the same
  account, or the hub is not listed.
- claude.ai connectors (Gmail, Google Calendar, Google Drive) follow the signed-in account. The project MCP server
  `notion-ecosys` keeps its own token and works on any account (`agents/steering/machine-notes.md`).

## Data sources for "bắt đầu ngày làm việc"

| Source | Tool in the hub | Note |
|---|---|---|
| Google Calendar | `notion-ecosys` calendar tools (any account); Google Calendar connector (personal account) | |
| Gmail (job replies) | Gmail connector | needs the personal claude.ai account; on another account, say so and skip |
| Notion inbox and pages | `notion-ecosys` | check the workspace with `notion-get-self` first |
| Board, PRs, runs | `gh`, `just board-export` | |
| Jobs | `just jobs-check` | |
| Day-job trackers | Linear and Jira connectors, read-only | progress summary in the hub chat only, never written anywhere (root `CLAUDE.md`, exception 2026-11-22) |
| Industry news | Gmail newsletters and alerts | same account rule as Gmail |

## Stop

`tmux kill-session -t hub`, or `Ctrl-c` in the hub terminal.
