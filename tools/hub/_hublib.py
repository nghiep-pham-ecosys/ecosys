"""Build the command that starts the Claude Code hub (Remote Control server).

The hub is one long-running `claude remote-control` server at the workspace root. Each session
opened from the phone or claude.ai/code gets its own git worktree (`--spawn worktree`), so parallel
sessions never share a working tree. tmux keeps the server alive when the terminal window closes.
"""

from __future__ import annotations

HUB_NAME = "hub"
TMUX_SESSION = "hub"


def claude_command(name: str = HUB_NAME, permission_mode: str | None = None) -> list[str]:
    """The `claude remote-control` command line."""
    cmd = ["claude", "remote-control", "--spawn", "worktree", "--name", name]
    if permission_mode:
        cmd += ["--permission-mode", permission_mode]
    return cmd


def launch_command(
    claude_cmd: list[str],
    *,
    use_tmux: bool,
    tmux_found: bool,
    inside_tmux: bool,
    tmux_session: str = TMUX_SESSION,
) -> list[str]:
    """Wrap the claude command in tmux when asked and possible.

    `tmux new-session -A` attaches to the session when it already runs, so a second
    `just hub` reattaches instead of starting a second server.
    """
    if not use_tmux or not tmux_found or inside_tmux:
        return list(claude_cmd)
    return ["tmux", "new-session", "-A", "-s", tmux_session, *claude_cmd]
