# Machine notes

## Host

- Windows with WSL2, distro Ubuntu. All work happens inside WSL.
- Shell: zsh. Config: `~/.zshrc`.
- Workspace root: `/home/nghiep/projects/nghiep-pham-ecosys` (`~/projects/nghiep-pham-ecosys`).
- Other folders under `~/projects` are not part of this workspace. Workspace tools never touch them.

## Toolchain

- `mise` is installed at `~/.local/bin/mise` and activated in `~/.zshrc`:
  `eval "$(~/.local/bin/mise activate zsh)"`.
- Versions are pinned in `.mise.toml` at the root: uv, node 22, pnpm, just 1.59.0, gitleaks 8.30.1, typst, actionlint 1.7.12.
  Python is not pinned there: the tools use the system `/usr/bin/python3` (3.12, has PyYAML); CI pins python with `actions/setup-python`.
  Run `mise install` after a change. Bump versions in a PR, never ad hoc.
- System `python3` is 3.12 with PyYAML 6.0.1. `pytest` is not assumed: tests use `unittest`.
- A non-interactive shell (agent Bash tool, cron) may not load `~/.zshrc`. If `just` or `gitleaks` is not found, call `~/.local/bin/mise exec -- <cmd>` or use the absolute shim path.
- `gh` is signed in as `pqnghiep1354`. Org admin calls need the `admin:org` scope; Project calls need `project`.

## Commands

- Prefer single-line commands. Long backslash-continued commands are fragile in WSL terminals and in agent tools.
- Use absolute paths in agent commands. The agent shell resets its working directory between calls.
- Run checks per repo with `just ci` from that repo's root.
- Use `git -C <path>` instead of `cd` when you act on a child repo.

## Paths agents must know

| Path | Note |
|---|---|
| `.tmp-session/wt/` | the only place for lane worktrees |
| `~/.config/nghiep-pham-ecosys/denylist.txt` | local denylist; never read, print or commit it |
| `~/.config/sops/` | age keys `[P1]`; agents are denied |
| `import/`, `skill/` | local, gitignored, read-only inputs |
