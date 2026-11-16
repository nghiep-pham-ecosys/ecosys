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
- Git identity: `~/.gitconfig` has `includeIf "gitdir:~/projects/nghiep-pham-ecosys/"` → `~/.config/git/nghiep-pham-ecosys.gitconfig`,
  which sets `user.email` to the GitHub noreply address for every workspace repo and worktree. Repos outside the
  workspace keep the global address.

## MCP servers

- `.mcp.json` at the root defines one project server, `notion-ecosys` (hosted Notion MCP, OAuth). It is enabled in
  `.claude/settings.json` (`enabledMcpjsonServers`), so Claude Code loads it only in this workspace.
- Why not the claude.ai Notion connector: a connector belongs to the claude.ai account the client is signed into, and
  one Notion connection reaches one workspace. The project server keeps its own OAuth token on this machine, so it
  works whichever claude.ai account is signed in. Claude Code treats a connector with the same URL as a duplicate and
  uses the project server.
- First use on a machine: run `/mcp` → `notion-ecosys` → Authenticate, then pick the personal workspace (the name is
  `workspace` in `private/ops/notion.yaml`) on the Notion consent page. Check with `notion-get-self`.
- A Notion workspace for other work is never added here. Configure it in that project's own folder.
- Limits: cloud routines do not read `.mcp.json`; they use the claude.ai connectors of the account that owns the
  routine. Claude Chat on the web and Kiro keep their own Notion connections.
- `.mcp.json` holds URLs only: no headers, tokens or env values (a settings test checks this).

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
