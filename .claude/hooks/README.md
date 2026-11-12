# Guard hooks

PreToolUse hooks from spec §9.7. Each reads one JSON payload on stdin, exits 2 with a reason
on stderr to block, and exits 0 to allow. They fail closed on bad input or a crash.

These hooks are **guardrails against agent mistakes, not a sandbox**. They read the command
text before the shell runs it; they never run it. See [Limits](#limits) for what that cannot
see and which controls catch it instead.

| Hook | Tools | Blocks |
|---|---|---|
| `ship-guard.py` | Bash, Write, Edit, MultiEdit, NotebookEdit | lanes: push in every form, `reset --hard`, `clean -f`, skipped hooks, git aliases, includes and injected git config, writes to git config and hooks, the merge tool, gh writes, computed command names and git subcommands, `xargs git/gh/sops/age`, unreadable text piped into a shell; everyone: `gh pr merge`, REST and GraphQL merges, `gh alias set/import`, writes to the gh config, computed gh subcommands, computed command names that could be git/gh/sops/age |
| `worktree-guard.py` | Bash | `git worktree add/move` outside `.tmp-session/wt/` (also through a symlink, a same-line alias or `$PWD`) |
| `secret-path-guard.py` | file tools, Bash | `.env*` (not `.env.example` or `*.sops.*`), `*.pem`/`*.key` and globs that can match them, `~/.config/sops/`, the local denylist, recursive readers started above those two folders, decryption (also behind a computed command name or in a command-valued environment variable), `xargs cat` of secret names |

Shared parsing lives in `_guardlib.py`. Tests: `python3 -m unittest discover -s tests -p 'test_*.py'`.

## How the parser reads a command

`_guardlib.py` normalises the text, then splits it into simple commands:

- `#` comments (at the start of a word, outside quotes) are dropped to the end of the line, so
  an apostrophe in a comment cannot open a quote that hides the next lines.
- Here-document bodies are cut out as data. A body read by a shell (`bash <<X`,
  `cat <<X | sh`) is parsed as commands; an unquoted body (`<<EOF`) still has its `$(...)`
  and backticks walked, because the shell runs them.
- `$(...)`, backticks, `$((...))`, `((...))` and `<(...)` stay one word. `<<` inside
  arithmetic is never a here-document.
- Each word knows whether the shell computes it (`$VAR`, `$(...)`, unquoted globs and braces);
  quoted text such as GraphQL `$id` variables in single quotes counts as literal. ANSI-C strings
  (`$'\x67it'`) and zsh `=git` are decoded.
- Variables assigned earlier on the same line, `$IFS`, `${X:-default}` and empty positional
  parameters are resolved; the resolved text is checked as well as the original.
- Wrappers are stripped and nested shell text is walked: `env` (also `-S`), `sudo` (also `-s`),
  `timeout`, `nice`, `ionice`, `stdbuf`, `time`, `/usr/bin/time`, `flock` (also `-c`),
  `script -c`, `su -c`, `watch`, `unbuffer`, `chronic`, `exec -a`, `xargs` (with literal input
  put where xargs puts it), `find -exec/-execdir/-ok`, `bash/sh/zsh/fish -c`, `eval`, shell
  function bodies, aliases defined on the same line, `git submodule foreach`, `git rebase -x`,
  `git bisect run`, `!` git aliases and command-valued `git -c` settings.
- Literal text piped or process-substituted into a shell (`echo ... | bash`,
  `bash <(echo ...)`) is parsed as commands. A lane may not pipe text the guard cannot read
  into a shell (`curl ... | sh`, `cat file | bash`).
- Command text in environment variables is walked as commands: `GIT_PAGER`, `PAGER`,
  `GIT_EDITOR`, `EDITOR`, `VISUAL`, `GIT_SEQUENCE_EDITOR`, `GIT_EXTERNAL_DIFF`,
  `GIT_SSH_COMMAND`, `GIT_SSH`, `GIT_ASKPASS`, `SSH_ASKPASS`, `LESSOPEN`, `LESSCLOSE`,
  `GIT_PROXY_COMMAND`, `MANPAGER`, `GH_PAGER`, `GH_EDITOR`, `GH_BROWSER`, `BROWSER`, set before a
  command, after `env`, or with `export`/`declare`/`local`. So are git options that take a
  command: `git grep -O<cmd>`, `git difftool -x/--extcmd`, the `git filter-branch` filters,
  `--upload-pack` (`clone`, `fetch`, `pull`, `ls-remote`), `--receive-pack`/`--exec` (`push`,
  `archive`), the `git send-email` `--*-cmd` options and `git mergetool --tool-cmd`.
- `source /dev/stdin <<<'...'` and `. /dev/stdin` are read like `bash <<<'...'`.
  `bash -c 'SCRIPT' arg0 arg1` is also walked with `$0`, `$1`, ... filled in.
- A safety net catches `git push` (lanes) and `gh pr merge` (everyone) behind a program the
  parser does not know as a wrapper (`strace -f git push`), and inside one argument or
  here-string of such a program that holds shell text (`tmux new -d 'git push'`,
  `ssh host 'git push'`, `at now <<< 'gh pr merge 3'`).
- Paths are normalised before they are compared: a leading `//`, `/proc/<pid>/root` and
  `/proc/<pid>/cwd` prefixes, `~+`, existing symlinks (real path). A relative path is checked
  against the payload cwd and against every literal `cd`/`pushd` target earlier on the line
  (`cd` alone is `$HOME`); a link made with `ln -s` earlier on the line is followed.

## Deviations from spec §9.7

- **secret-path-guard matcher** is `Read|Edit|Write|MultiEdit|NotebookEdit|Grep|Glob|Bash`
  (spec: `Read|Edit|Write|Bash`). MultiEdit, NotebookEdit, Grep and Glob also reach file
  paths; the hook already understood their inputs.
- **ship-guard also runs on `Write|Edit|MultiEdit|NotebookEdit`** (a second matcher entry).
  Protected config is a ship concern, not a secret: reading it stays allowed, writing it is
  blocked. Lanes may not write `.git/config`, `.git/config.worktree`, `.git/hooks/*`,
  `.git/worktrees/*/config`, a worktree's `.git` file, `~/.gitconfig` or
  `~/.config/git/config` (aliases, includes and hooks bypass the push and hook rules).
  Nobody may write `~/.config/gh/config.yml` (gh aliases live there, so it is the file form of
  `gh alias set`). Bash writes count too: redirects, `tee`, `cp/mv/install/ln/rsync` targets,
  `sed -i`, `dd of=`, `chmod`, `touch`, `rm`, `truncate`.
- **permissions.deny** adds `mcp__plugin_github_github__merge_pull_request`, so the GitHub
  MCP plugin cannot merge around `tools/ship/merge`.
- **git long-option abbreviations**: git accepts any unique prefix (`git reset --h` runs
  `--hard`, `git clean --f` runs `--force`; checked on git 2.43). The guard therefore treats
  every prefix of at least one letter as the full option, which is stricter than a
  four-character minimum.
- **REST branch merges** (`POST repos/<o>/<r>/merges`) are blocked for everyone, to match the
  GraphQL `mergeBranch` block. Any write method (not only PUT) to `.../pulls/<n>/merge` counts.
  Endpoints are normalised first: scheme and host, query string, `//`, `..`, percent-encoding
  and `api/v3/` are removed. `gh api` methods are read in every form (`-X PUT`, `-XPUT`,
  `-X=PUT`, `-iXPUT`, `-iX PUT`, `--method=PUT`, any case).
- **GraphQL from a file or stdin** (`--input`, `-F query=@file`) is blocked for everyone,
  because the guard cannot read it to check for a merge. So is a GraphQL `query` field built
  from a shell expansion (`-f query="$Q"`, `"$(cat q.graphql)"`). Literal queries, also with
  GraphQL `$variables` in single quotes, are read and checked as before.
- **Computed endpoints**: a write `gh api` call whose endpoint is computed by the shell is
  blocked for everyone when its last path segment is computed or is `merge`, `merges` or
  `graphql` (`repos/$R/issues` stays allowed).
- **Computed command names** (spec: lanes block; the main session blocks only when the word
  could be gh/git/sops/age). "Could be" means: it looks a program up (`which`, `command -v`,
  `type -P`, `whereis`, `hash`), names one of the tools, uses a variable assigned on the same
  line (or a `for` loop variable) whose value names one, or is a glob or brace pattern that
  matches one. A computed word whose file name is literal (`"$(git rev-parse
  --show-toplevel)"/tools/ws/denylist-scan`) is not computed for this rule.
- **Computed gh groups and subcommands** (`gh pr $(echo merge)`, `gh $G merge`) are blocked
  for everyone, not only in lanes, because they could be `gh pr merge`.
- **Lanes and computed git arguments**: besides the subcommand, lanes may not pass computed
  `git -c` values, computed option words to `git reset`, `git clean` or `git commit` (they could
  be `--hard`, `-f` or `--no-verify`; values such as `-m "$MSG"` and paths after `--` are fine),
  or a computed `git config` key.
- **Environment next to git and gh**: lanes may not set `GIT_CONFIG_GLOBAL`,
  `GIT_CONFIG_SYSTEM` or `GIT_EXEC_PATH` (or use `git --exec-path=`), nor `HOME=` or
  `XDG_CONFIG_HOME=` on a line that runs git. Nobody may set `GH_CONFIG_DIR`, `HOME` or
  `XDG_CONFIG_HOME` on a line that runs gh (another gh config can hold a merge alias).
- **xargs**: lanes may not run `xargs git/gh/sops/age` (the guard cannot see the appended
  arguments). secret-path-guard checks file names piped into `xargs cat` and other readers
  when the source is literal, and blocks a lane that feeds them from a source it cannot read.
- **Recursive readers** (`grep -r`, `rg`, `ag`, `ack`, `find ... -exec`, `tar c`, `cp -r`,
  `rsync`, `zip -r`, and the Grep tool's `path`) are blocked when they start at
  `~/.config/sops/`, the denylist folder or any folder above them (`~/.config`, `~`, `/`).
  `find` without `-exec` and `ls -R` only list names and stay allowed.
- **Key and .env globs**: a glob counts as a key or .env name when it can match one
  (`server.ke?`, `*.pe[m]`, `*.k*`, `*.{pem,key}`, `*env`, `.e*`) and is not so broad that it
  also matches ordinary names (`*`, `*.*`, `README.*`, `docs/*`). `*` is treated as matching a
  leading dot, as `find -name` and ripgrep do. Case is ignored (`.ENV`, `*.PEM`).
- **Text words are not file names**: the message of `git commit/tag/notes/stash/merge`
  (`-m`, `--message`, ...), gh `--body`/`--title`, the pattern of grep-like programs, and the
  script of `sed`/`awk` are checked for `~/.config/sops/` and the denylist only, not for
  .env/key names. So are the arguments of `test`, `[`, `ls`, `stat`, `realpath`, `readlink`,
  `git check-ignore` and `git ls-files`, which never read file contents.
- **Encrypted files**: `*.sops.*` names (`.env.sops.yaml`) are readable; they are ciphertext.
- **Denylist scanner exemption**: only when `CLAUDE_PROJECT_DIR` is set and the program's real
  path equals the real path of `$CLAUDE_PROJECT_DIR/tools/ws/denylist-scan` (run directly or as
  `python3 <that path>`), and that file lies inside the project. A copy elsewhere
  (`/tmp/x/tools/ws/denylist-scan`), a symlink to another program, a lane worktree's own copy
  and a computed path are not exempt. `just denylist` and `just ci` stay exempt.
- **Merge tool in lanes**: the word is resolved against every folder the command may run in,
  globs are matched part by part and against the files they find, real paths are compared,
  and a computed folder in front of `merge` (`$DIR/merge`) counts. Read-only tools may name it
  (`cat`, `sed -n`, `ruff`, `mypy`, `shellcheck`, `python3 -m py_compile`, ...).
- **git clone in lanes**: `-c`/`--config` values follow the lane config rules, and
  `--template`, `-u` and `--upload-pack` are blocked, also after `gh repo clone ... --`.

## Limits

A guard that reads text cannot know what a program will do once it runs. These are known gaps.
They are accepted because the guards exist to stop honest mistakes, and other controls catch
the effect (a push or a merge on the server) whatever text produced it. Each item names the
exact commands the round 2 and round 4 adversarial reviews used.

What the guards cannot catch:

- **Other languages.** `python3 -c "import os; os.system('git push')"`,
  `python3 -c "import subprocess; subprocess.run(['gh','pr','merge','3'])"`,
  `python3 -c "import subprocess;subprocess.run(['sops','-d','s.sops.yaml'])"`, `node -e`,
  `perl -e`, `ruby -e` and the like are not parsed as shell. secret-path-guard scans their text
  for secret paths only, so a path built at run time also gets through:
  `python3 -c "print(open('.e'+'nv').read())"`,
  `python3 -c "import os;print(open(os.path.expanduser('~/.config/'+'sops/age/keys.txt')).read())"`,
  `python3 -c "import os;print(open(os.path.join(os.path.expanduser('~'),'.config','sops','age','keys.txt')).read())"`.
- **Code fed to an interpreter from a file or a pipe.** `cat tools/ship/merge | python3 - 3`
  runs the merge tool; the guard does not follow file contents into `python3 -`, `node -` and
  the like.
- **Network clients with a token.** `curl -X PUT -H "Authorization: token $(gh auth token)"
  https://api.github.com/repos/o/r/pulls/3/merge`, `wget`, an HTTP library, or a `git push`
  done by a library are not gh or git commands.
- **Moving a branch through the API.** `gh api -X PATCH repos/o/r/git/refs/heads/main -f sha=...`
  and `gh api -X PUT repos/o/r/contents/...` change the default branch without a merge. Lanes
  cannot send write `gh api` calls; for the main session only the branch rulesets stop it.
- **Files written, then executed.** `printf 'git push\n' > x.sh; bash x.sh`, a `Makefile`,
  `just` recipe, `npm run` script, test fixture or git hook script runs code the guard never
  sees as a command. `bash < x.sh` and `source x.sh` are the same case. A lane may also edit
  its own worktree's `justfile`, which `just denylist` then runs.
- **State from outside the line.** Aliases, functions and variables defined in an earlier Bash
  call, in a shell profile (`~/.bashrc`, `~/.zshrc`) or in another session; gh aliases and gh
  extensions already in `~/.config/gh/`; git aliases already in a config file (worktree-guard
  expands only aliases defined on the same line); environment variables such as `GIT_PAGER`
  exported in an earlier call. The main session runs `$VAR` from the environment unless it
  looks like git/gh/sops/age; lanes block any computed command name but not computed arguments
  of ordinary programs. The main session's Bash cwd carries over between calls, so a relative
  path is resolved against the cwd Claude Code reports in the payload.
- **Computed paths.** `cd "$(...)"`, `cd "$DIR"`, `cd -`, `popd` or `git -C "$DIR"` with a value
  from outside the line cannot be followed. A command after such a `cd` is checked against the
  folders the guard does know, so `cd "$D" && cat sops/age/keys.txt` gets through, and a
  main-session call into a lane worktree through such a path is not seen as a lane call (a
  subagent is always a lane, wherever it runs).
- **Program output.** `cat "$(printf .e)nv"`, `$(printf '%s' g it) push` and
  `echo Z2ggcHIgbWVyZ2UgMw== | base64 -d | sh` build text the guard would have to run to see.
  Lanes block computed command names and unreadable text piped into a shell; the main session
  allows them unless the word names a tool (the base64 pipe is allowed in the main session).
- **Wrappers and shells the parser does not model.** `uv run`, `npx`, `parallel`, `strace`
  and similar launchers are not stripped; only the push/merge safety net looks behind them, and
  it does not join words (`parallel git ::: push` gets through). There is no safety net for
  sops/age behind an unknown launcher (`taskset` is now modelled; others such as `chrt` or
  `nsenter` are not). zsh glob qualifiers that run code (`*(e:'...':)`), `case` patterns inside
  `$(...)` with an unbalanced `)`, and other rare grammar can be misread. Programs that run
  their own command language are not modelled either: `sed 'e ...'`, `awk 'BEGIN{system(...)}'`,
  `vim -c '!...'`, `less` with `!`.
- **Lane-only rules.** Main-session `xargs -a list.txt cat` (file names read from a file) and
  main-session pipes of unreadable text into a shell are allowed by design; only lanes are
  blocked for them.
- **Whole-project reads.** `grep -r PASSWORD .`, `rg -uu PASSWORD`, `tar cf - . | tar tf -`,
  `zip -r /tmp/x.zip .` and `cp -r . /tmp/x` read a project's `.env` or key files along with
  everything else. Blocking every recursive read of the project would stop normal work, so only
  recursive reads that reach `~/.config/sops/` or the denylist folder are blocked. The Grep tool
  over the project is allowed for the same reason.
- **Broad globs.** A glob that also matches ordinary names (`cat *`, `cat certs/*`,
  `cat server.*`) is not treated as naming a key, although the shell may expand it to one.
- **Out of spec scope.** spec §9.7 protects `.env` and `.env.*`, `*.pem`, `*.key`,
  `~/.config/sops/` and the local denylist. Other secret-looking files are not protected:
  `prod.env`, `.envrc`, `~/.ssh/id_ed25519` and other SSH keys, `~/.aws/credentials`,
  `~/.config/gh/hosts.yml`, `.netrc`, `.npmrc`. Case-insensitive mounts (`/mnt/c`) are covered
  for `.env`/key names because names are compared in lower case.

Known false positives (the guards err on the side of blocking):

- A `.env` or key name next to a program that might read it: `git rm --cached .env`,
  `cp .env.example .env` (writes `.env`), `python3 -c "print('remember .env')"` (code that
  mentions `.env` is scanned as code). Run these by hand.
- A regex the guard cannot tell from a glob, outside the grep/sed/awk pattern position:
  `git log --grep 'deploy.k*'` is read as a key-name glob.
- `git worktree add` with a variable other than `$HOME`, `$CLAUDE_PROJECT_DIR` or `$PWD`.
- Lanes: a plain-text argument that reads as shell text with `git push` in it, given to a
  program the guard does not know (`notify-send 'git push done'`).
- Lanes: a glob whose last three parts can match `tools/ship/merge`, given to a program that
  is not a known viewer (`rm */*/*`).

The backstops, which act on the effect instead of the text:

- **settings.json permissions.** `deny` rules (`Bash(gh pr merge*)`, `Bash(sops -d*)`,
  `Bash(age -d*)`, the GitHub MCP merge tool, secret `Read` paths) and `ask` rules
  (`Bash(git push*)`, `gh api -X POST`, `gh workflow run`) are enforced by Claude Code itself.
- **Branch rulesets on public repos.** Rules such as required pull requests, required checks
  and no force push are enforced by GitHub, so they stop a bad push or merge whatever client
  sent it.
- **pre-push hooks.** A pre-push hook runs inside git, so it sees a push however it was
  started (unless hooks are skipped, which the guards block for lanes).
- **The merge tool.** `tools/ship/merge` is the one supported merge path and runs its own
  checks; the guards only make sure nothing else is used by mistake.
