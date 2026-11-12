#!/usr/bin/env python3
"""worktree-guard: PreToolUse hook for Bash (spec §9.7).

`git worktree add <path>` and `git worktree move <wt> <new-path>` are
allowed only when the target path is absolute and lies below
<project>/.tmp-session/wt/ (for example .tmp-session/wt/s1-lane-a).

~, $HOME, $CLAUDE_PROJECT_DIR and $PWD are expanded first, because the
shell expands them before git sees the path ($PWD against every folder a
literal `cd` earlier on the line may have moved to). A relative path, a
path with any other variable, or a path that escapes with .. is blocked.
The real path (existing symlinks resolved, and links made with `ln -s`
earlier on the same line followed) must stay below .tmp-session/wt/ too.
Aliases defined on the same line (`git -c alias.wa='worktree add' wa x`,
`git config alias.wa ...`) are expanded. The raw text is not pre-filtered
for the word "worktree", so quoting tricks (`git wor''ktree`) are parsed.
"""

from __future__ import annotations

import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _guardlib as g  # noqa: E402

NAME = "worktree-guard"

# `git worktree add` options that take a value.
ADD_VALUE_OPTS = {"-b", "-B", "--reason"}


def _positionals(args, value_opts):
    out = []
    i = 0
    while i < len(args):
        tok = args[i]
        if tok == "--":
            out.extend(args[i + 1 :])
            break
        if tok in value_opts:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        out.append(tok)
        i += 1
    return out


def _target_reason(raw, project, home, cwds, links):
    wt = g.wt_root(project)
    real_wt = os.path.realpath(wt)
    for cwd in cwds:
        env = {"HOME": home, "CLAUDE_PROJECT_DIR": project, "PWD": cwd}
        text = g.expand_vars(str(raw), env)
        if text == "~" or text.startswith("~/"):
            text = home + text[1:]
        if "$" in text or "`" in text:
            return f"worktree path {raw!r} uses a variable the guard cannot resolve; use an absolute path under {wt}/"
        if not os.path.isabs(text):
            return f"worktree path {raw!r} is relative; use an absolute path under {wt}/"
        path = g.normalize_abs(text, cwd)
        if not g.is_under(path, wt) or path == wt:
            return f"worktree path {path} is outside {wt}/; lanes live in .tmp-session/wt/<session>-<lane>"
        # A symlink below wt/ (existing, or made earlier on this line) must not lead out.
        for alias in g.path_aliases(path, links):
            real = os.path.realpath(alias)
            if not g.is_under(real, real_wt) or real == real_wt:
                return (f"worktree path {path} resolves to {real}, outside {wt}/ "
                        "(a symlink leads out); use a real folder under .tmp-session/wt/")
    return None


def _line_aliases(cmds):
    """git aliases defined on this line: `git -c alias.X=...` and `git config alias.X ...`."""
    aliases = {}
    for cmd in cmds:
        parts = g.git_parts(cmd)
        if not parts:
            continue
        for cfg in parts[3]:
            key, eq, val = str(cfg).partition("=")
            if eq and key.lower().startswith("alias."):
                aliases[key[6:].lower()] = val
        if str(parts[0]) == "config":
            vals = [str(a) for a in parts[1] if not str(a).startswith("-")]
            if vals and vals[0] in ("set", "add"):
                vals = vals[1:]
            if len(vals) >= 2 and vals[0].lower().startswith("alias."):
                aliases[vals[0][6:].lower()] = vals[1]
    return aliases


def _expand_alias(cmd, aliases):
    """`git wa x` with alias wa='worktree add' -> ['git', 'worktree', 'add', 'x']."""
    for _ in range(4):
        parts = g.git_parts(cmd)
        if not parts or not str(parts[0]) or str(parts[0]).lower() not in aliases:
            return cmd
        val = aliases[str(parts[0]).lower()]
        if val.startswith("!"):
            return cmd  # a shell alias: its text is walked as commands by the parser
        try:
            words = shlex.split(val)
        except ValueError:
            words = val.split()
        idx = len(cmd) - len(parts[1]) - 1
        cmd = list(cmd[:idx]) + [g.Word(w) for w in words] + list(cmd[idx + 1 :])
    return cmd


def check(payload):
    if payload.get("tool_name") != "Bash":
        return None
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command.strip():
        return None
    project = g.project_dir(payload)
    home = g.home_dir()
    cwd = g.payload_cwd(payload)
    infos = g.command_infos(command)
    cwds = g.track_cwds(infos, cwd, project, home)
    links = g.line_symlinks(infos, cwds, project, home)
    aliases = _line_aliases([info["core"] for info in infos])
    for info, folders in zip(infos, cwds):
        cmd = _expand_alias(info["core"], aliases) if aliases else info["core"]
        parts = g.git_parts(cmd)
        if not parts or str(parts[0]) != "worktree" or not parts[1]:
            continue
        action, args = str(parts[1][0]), parts[1][1:]
        if action == "add":
            pos = _positionals(args, ADD_VALUE_OPTS)
            if not pos:
                return "git worktree add needs an absolute path under .tmp-session/wt/"
            reason = _target_reason(pos[0], project, home, folders, links)
        elif action == "move":
            pos = _positionals(args, set())
            if len(pos) < 2:
                return "git worktree move needs a new absolute path under .tmp-session/wt/"
            reason = _target_reason(pos[1], project, home, folders, links)
        else:
            reason = None
        if reason:
            return reason
    return None


if __name__ == "__main__":
    g.run_guard(NAME, check)
