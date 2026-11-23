# Runbook: the main session

The main session is Claude Code in Claude Desktop, signed into Nghiep's personal claude.ai account. It is the single
place where Nghiep gives work. Claude Chat is the fallback. Rules: `skills/session/SKILL.md` ("Main session"),
`skills/daily-start/SKILL.md`. Approval rules do not change (ADR 0003, ADR 0006 §1).

## Why Claude Desktop

- Every `claude` process in WSL (a terminal, tmux, the VS Code extension) shares one CLI login in `~/.claude`.
  That login is the Team seat the day-job VS Code sessions use.
- claude.ai connectors (Gmail, Google Calendar, Google Drive) belong to the account that is signed in. On the Team
  seat the personal Gmail is out of reach.
- Claude Desktop keeps its own login, so it can stay on the personal account while VS Code stays on the Team seat.
  When a Desktop Code session runs inside WSL, confirm on first use that it reports the personal account (*verify*,
  see "Account check").
- The tmux hub (`just hub`, W48) ran on the shared CLI login and was retired on 2026-11-23 (ADR 0006, "Decisions by
  Nghiep").

## Start

1. Open Claude Desktop with the personal account (Settings → Account shows it).
2. Open the Code tab and choose the workspace root `~/projects/nghiep-pham-ecosys` in WSL.
3. Say "bắt đầu ngày làm việc" (skill `daily-start`) or "bắt đầu session mới" (skill `session`).

## Account check

Run this first when a connector fails:

- In the session, ask which account it runs on, or run `claude auth status` in its shell and read `email`,
  `orgName` and `subscriptionType`. The main session must show the personal account, not the Team org.
- A connector shown as Active in Settings → Plugins belongs to the account of that app window only.
- A connector with "Sign-in expired" needs Reconnect in the same window.

## Data sources for "bắt đầu ngày làm việc"

| Source | Tool | Note |
|---|---|---|
| Google Calendar | Google Calendar connector, or the `notion-ecosys` calendar tools | |
| Gmail (job replies, newsletters) | Gmail connector | personal account only; on another account, say so and skip |
| Notion inbox and pages | `notion-ecosys` | check the workspace with `notion-get-self` first |
| Board, PRs, runs | `gh`, `just board-export` | |
| Jobs | `just jobs-check` | |
| Day-job trackers | Linear and Jira connectors, read-only | summary in the session chat only, never written anywhere (root `CLAUDE.md`, exception 2026-11-22); skipped when the personal account has no such connector |

## Day job

The day job keeps its own Claude Code in VS Code on the Team seat. That session never opens this workspace, and the
main session never opens day-job repos.
