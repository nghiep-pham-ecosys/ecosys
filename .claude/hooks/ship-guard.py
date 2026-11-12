#!/usr/bin/env python3
"""ship-guard: PreToolUse hook for Bash and the file-writing tools (spec §9.7).

Lanes code and commit locally. Only the orchestrator ships.

A call is a lane call when any of these is true:
- the payload has agent_id (every subagent, wherever its cwd is);
- the payload cwd is inside <project>/.tmp-session/wt/;
- the command cds, pushds or `git -C`s into such a path (also through a
  variable assigned on the same line), or sets GIT_DIR/GIT_WORK_TREE there.

Lane calls may not: git push in any form (git push, git-push, send-pack,
http-push, subtree push, lfs push, or a push run by submodule foreach,
rebase -x or bisect run), git reset --hard, git clean -f (also with
clean.requireForce=false), skip hooks (--no-verify, git commit -n,
core.hooksPath), define git aliases or includes (git -c / git config
alias.*, include.*, includeIf.*), inject config through the environment
(GIT_CONFIG_*, GIT_EXEC_PATH, HOME= or XDG_CONFIG_HOME= next to git),
write .git/config, .git/hooks/*, ~/.gitconfig or ~/.config/git/config,
run tools/ship/merge in any form (also `cd tools/ship && ./merge`,
`tools/sh?p/merge`, `$DIR/merge` and symlinks: words are resolved against
every folder a literal `cd` may have moved to, globs are matched, and
real paths are compared), pass -c/--config/--template/--upload-pack to
git clone (also after `gh repo clone ... --`), call write `gh api` requests, use any
gh subcommand outside a read-only allowlist, feed git/gh/sops/age
arguments through xargs, pipe text the guard cannot read into a shell,
or run a command whose name, or whose git/gh subcommand, is computed by
the shell ($(...), backticks, $VAR, globs).

Everyone: no raw `gh pr merge`, no merge through `gh api` (PUT
.../pulls/<n>/merge, POST .../merges, GraphQL mergePullRequest,
enablePullRequestAutoMerge or mergeBranch, GraphQL from a file or stdin,
or a GraphQL query built from a shell expansion), no write `gh api` call
whose endpoint is computed and could be a merge, no `gh alias set/import`,
no write to ~/.config/gh/config.yml and no GH_CONFIG_DIR=/HOME=/
XDG_CONFIG_HOME= next to gh (an alias can hide a merge), no
gh group or subcommand computed by the shell, and no computed command
name that could be git/gh/sops/age (`$(which gh) pr merge`). Command
text in environment variables (GIT_PAGER, GIT_EDITOR, EDITOR, PAGER,
GIT_SSH_COMMAND, LESSOPEN, ...) and in git options (grep -O, difftool -x,
filter-branch filters, --upload-pack, ...) is checked as commands. The
safety net also reads shell text passed as one argument or here-string to
a program it does not know (`tmux new -d 'git push'`,
`at now <<< 'gh pr merge 3'`). Merges go
through tools/ship/merge, which runs gh in its own subprocess, not
through the Bash tool.
"""

from __future__ import annotations

import fnmatch
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _guardlib as g  # noqa: E402

NAME = "ship-guard"
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
READ_METHODS = {"GET", "HEAD"}
MERGE_ENDPOINT_RE = re.compile(r"(^|/)pulls/[^/]+/merge$", re.IGNORECASE)
BRANCH_MERGE_ENDPOINT_RE = re.compile(r"(^|/)repos/[^/]+/[^/]+/merges$", re.IGNORECASE)
GRAPHQL_MERGE_RE = re.compile(r"mergePullRequest|enablePullRequestAutoMerge|mergeBranch", re.IGNORECASE)
GIT_CONFIG_ENV_RE = re.compile(
    r"^(GIT_CONFIG_COUNT|GIT_CONFIG_PARAMETERS|GIT_CONFIG_KEY_\w*|GIT_CONFIG_VALUE_\w*"
    r"|GIT_CONFIG_GLOBAL|GIT_CONFIG_SYSTEM|GIT_EXEC_PATH)="
)
HOME_ENV_RE = re.compile(r"^(HOME|XDG_CONFIG_HOME)=")
GH_CONFIG_ENV_RE = re.compile(r"^(GH_CONFIG_DIR|XDG_CONFIG_HOME|HOME)=")
ASSIGN_PREFIX_WORDS = {"env", "export", "declare", "typeset", "readonly", "local", "sudo", "doas",
                       "command", "exec", "nohup", "nice", "setsid"}
MERGE_TOOL = os.path.join("tools", "ship", "merge")
# Commands that may name the merge tool without running it (lanes may edit it).
MERGE_TOOL_VIEWERS = {"git", "cat", "less", "more", "head", "tail", "grep", "egrep", "fgrep", "rg", "wc",
                      "ls", "stat", "file", "diff", "cmp", "sha256sum", "md5sum", "echo", "printf",
                      "chmod", "touch", "sed", "nl", "bat", "batcat", "xxd", "od", "hexdump", "strings",
                      "ruff", "black", "mypy", "pyflakes", "flake8", "pylint", "pyright", "shellcheck",
                      "shfmt", "codespell", "isort", "vulture", "bandit"}
# python -m <module> that only reads or compiles a file.
MERGE_TOOL_VIEWER_MODULES = {"py_compile", "compileall", "tabnanny", "pyflakes", "flake8", "mypy", "ruff",
                             "black", "pylint", "isort", "pycodestyle", "pydoc", "tokenize", "ast"}
# Commands whose arguments are text, not a command (for the wrapper safety net).
TEXT_COMMANDS = {"echo", "printf", "grep", "egrep", "fgrep", "rg", "ag", "ack", "sed", "awk", "cat", "less",
                 "more", "head", "tail", "wc", "ls", "man", "which", "type", "whereis", "true", ":",
                 "test", "[", "[[", "jq", "yq", "tr", "cut", "sort", "uniq", "column", "fold", "fmt",
                 "export", "declare", "typeset", "readonly", "local", "alias", "printenv"}
PUSH_SUBS = {"push", "send-pack", "http-push"}
# git config keys a lane may not set (-c or git config), with the reason.
LANE_CONFIG_RULES = [
    (re.compile(r"^core\.hookspath", re.I), "override core.hooksPath"),
    (re.compile(r"^alias\.", re.I), "define git aliases"),
    (re.compile(r"^include(if)?\.", re.I), "add git config includes (include.path / includeIf)"),
    (re.compile(r"^clean\.requireforce", re.I), "change clean.requireForce"),
    (re.compile(r"^core\.(fsmonitor|sshcommand)", re.I), "set a git config key that runs a command"),
]
CONFIG_VERBS = {"set", "get", "unset", "list", "edit", "rename-section", "remove-section", "get-color",
                "get-colorbool", "get-regexp", "get-urlmatch", "get-all", "unset-all", "add", "replace-all"}
COPY_LIKE = {"cp", "mv", "install", "ln", "rsync"}
WRITE_ALL_ARGS = {"tee", "truncate", "chmod", "chown", "touch", "rm", "unlink", "shred"}

# gh subcommands a lane may run (read-only or local-only).
GH_LANE_ALLOW = {
    "pr": {"view", "list", "status", "checks", "diff", "checkout"},
    "issue": {"view", "list", "status"},
    "repo": {"view", "list", "clone"},
    "run": {"view", "list", "watch", "download"},
    "workflow": {"view", "list"},
    "release": {"view", "list", "download"},
    "project": {"view", "list", "item-list", "field-list"},
    "label": {"list"},
    "cache": {"list"},
    "ruleset": {"view", "list", "check"},
    "secret": {"list"},
    "variable": {"list", "get"},
    "auth": {"status"},
    "extension": {"list"},
    "gist": {"view", "list"},
    "org": {"list"},
    "alias": {"list"},
    "config": {"get", "list"},
}
GH_LANE_ALLOW_GROUPS = {"search", "help", "version", "status", "completion", ""}


# ---------------------------------------------------------------- helpers


def _commit_skips_hooks(args):
    """git commit -n (short for --no-verify), also inside combined flags like -an."""
    value_flags = set("mFCcSt")
    skip_next = False
    for tok in args:
        tok = str(tok)
        if skip_next:
            skip_next = False
            continue
        if tok == "--":
            break
        if tok in ("-m", "-F", "-C", "-c", "-t", "--message", "--file", "--author", "--date", "--template"):
            skip_next = True
            continue
        if tok.startswith("-") and not tok.startswith("--") and tok[1:].isalpha():
            letters = tok[1:]
            for k, ch in enumerate(letters):
                if ch == "n":
                    return True
                if ch in value_flags:
                    if k == len(letters) - 1:
                        skip_next = True
                    break
    return False


def _dynamic_option(args, value_short="", value_long=()):
    """A computed word in option position (it could expand to --hard, -f, ...).

    Values of value options and words after `--` do not count; a literal
    option with a computed value (`--file=$f`, `-m "$msg"`) does not count.
    """
    skip_next = False
    for tok in args:
        if skip_next:
            skip_next = False
            continue
        t = str(tok)
        if t == "--":
            return False
        if g.is_dynamic(tok):
            name = tok.ph.split("=", 1)[0] if isinstance(tok, g.Word) else t
            if not name.startswith("-") or g.EXPAND_RE.search(name) or g.UNQUOTED_GLOB_RE.search(name):
                return True
            continue
        if t.startswith("--"):
            if t in value_long:
                skip_next = True
        elif t.startswith("-") and len(t) > 1:
            for k, ch in enumerate(t[1:]):
                if ch in value_short:
                    skip_next = k == len(t) - 2
                    break
    return False


def _config_key_dynamic(args):
    """git config: a computed word up to and including the key (the value may be computed)."""
    value_opts = {"-f", "--file", "--blob", "--type", "--default", "--comment", "--value"}
    skip_next = False
    verb_seen = False
    for tok in args:
        if skip_next:
            skip_next = False
            continue
        t = str(tok)
        if g.is_dynamic(tok) and not (isinstance(tok, g.Word) and tok.ph.startswith("-")):
            return True
        if t.startswith("-"):
            skip_next = t in value_opts
            continue
        if not verb_seen and t in CONFIG_VERBS:
            verb_seen = True
            continue
        return False  # the key is literal; the value may be computed
    return False


def _config_rule(key):
    for rx, what in LANE_CONFIG_RULES:
        if rx.match(str(key)):
            return what
    return None


def _is_push(parts):
    sub, args = parts[0], parts[1]
    return str(sub) in PUSH_SUBS or (str(sub) in ("subtree", "lfs") and any(str(a) == "push" for a in args))


def _is_graphql(endpoint):
    return endpoint.rsplit("/", 1)[-1].lower() == "graphql"


# ---------------------------------------------------------------- gh api


def _gh_api_reason(args, lane):
    req = g.gh_api_request(args)
    raw_ep = req["endpoint"]
    endpoint = g.normalize_endpoint(raw_ep or "")
    ep_dynamic = g.is_dynamic(raw_ep)
    method = req["method"]
    m_dynamic = g.is_dynamic(method)
    has_body = bool(req["fields"]) or req["input"] is not None
    method_text = str(method) if method is not None else None
    writes = m_dynamic or (method_text is not None and method_text not in READ_METHODS) or (
        method_text is None and has_body)

    if MERGE_ENDPOINT_RE.search(endpoint) and writes:
        return "merging through `gh api .../pulls/<n>/merge` is blocked; use tools/ship/merge"
    if BRANCH_MERGE_ENDPOINT_RE.search(endpoint) and writes:
        return "merging branches through `gh api .../merges` is blocked; use tools/ship/merge"
    if ep_dynamic and writes:
        last = endpoint.rsplit("/", 1)[-1]
        if re.search(r"[$`(){}*?\[]", last) or last.lower() in ("merge", "merges", "graphql"):
            return ("a write `gh api` call to an endpoint computed by the shell is blocked "
                    "(it could be a merge); write the endpoint out")
    if m_dynamic and lane:
        return "lanes may not call `gh api` with a method computed by the shell"
    if _is_graphql(endpoint):
        query_fields = []
        for field in req["fields"]:
            key = str(field).split("=", 1)[0]
            if key == "query" or g.is_dynamic(field) and g.EXPAND_RE.search(key):
                query_fields.append(field)
        if any(g.is_dynamic(f) for f in query_fields):
            return ("a GraphQL query built from a shell expansion is blocked for everyone "
                    "(the guard cannot check it for merges); pass it as a literal")
        values = " ".join(str(f) for f in req["fields"])
        if GRAPHQL_MERGE_RE.search(values):
            return "GraphQL merge mutations are blocked for everyone; use tools/ship/merge"
        if req["input"] is not None or any("=@" in str(f) or str(f).startswith("@") for f in req["fields"]):
            return "GraphQL sent from a file or stdin is blocked (the guard cannot check it for merges)"
        if lane and "mutation" in values.lower():
            return "lanes may not send GraphQL mutations"
        return None
    if not lane:
        return None
    if writes:
        if method_text is None:
            return "lanes may not call write API requests (gh api with -f/-F/--input defaults to POST)"
        return f"lanes may not call write API requests (gh api -X {method_text})"
    return None


# ---------------------------------------------------------------- merge tool


def _merge_tool_tail(path):
    """True when the last three parts of path are (or, as a glob, match)
    tools/ship/merge."""
    parts = path.rstrip(os.sep).split(os.sep)
    if len(parts) < 3:
        return False
    return all(fnmatch.fnmatchcase(want, got) for want, got in zip(MERGE_TOOL.split(os.sep), parts[-3:]))


def _names_merge_tool(tok, cwds, project, links=()):
    """True when tok (or the value of --opt=tok) is a path to tools/ship/merge.

    The word is resolved against every folder the command may run in (a
    literal `cd` earlier on the line counts), globs are matched part by part
    and against the files they match, and real paths are compared, so
    `cd tools/ship && ./merge`, `tools/sh?p/merge` and a symlink to the
    tool all count.
    """
    tok = str(tok)
    if tok.startswith("-"):
        if "=" not in tok:
            return False
        tok = tok.split("=", 1)[1]
    if not tok:
        return False
    if isinstance(cwds, str):
        cwds = [cwds]
    real_tool = os.path.realpath(os.path.join(project, MERGE_TOOL))
    for alt in g.brace_expand(tok):
        for cwd in cwds:
            path = g.expand_path(alt, cwd, project)
            for alias in g.path_aliases(path, links):
                if _merge_tool_tail(alias):
                    return True
                found = glob.glob(alias)[:64] if g.has_glob(alias) else [alias]
                for hit in found:
                    real = os.path.realpath(hit)
                    if real == real_tool or real.endswith(os.sep + MERGE_TOOL):
                        return True
    return False


def _python_viewer(cmd):
    """python -m py_compile FILE and similar: reads the file, does not run it."""
    base = os.path.basename(str(cmd[0]))
    if not re.match(r"^python[0-9.]*$", base):
        return False
    words = [str(t) for t in cmd[1:]]
    return "-m" in words and words.index("-m") + 1 < len(words) and \
        words[words.index("-m") + 1] in MERGE_TOOL_VIEWER_MODULES and "-c" not in words


def _runs_merge_tool(cmd, cwds, project, lane=True, links=()):
    """The merge tool as the command, or as an argument of anything that may run it
    (python3 tools/ship/merge, bash /abs/tools/ship/merge, uv run ...)."""
    base = os.path.basename(str(cmd[0]))
    if _names_merge_tool(cmd[0], cwds, project, links) or (base == "merge" and "ship" in str(cmd[0])):
        return True
    if lane and base == "merge" and g.is_dynamic(cmd[0]):
        return True  # $DIR/merge: the folder is computed and could be tools/ship
    if base in MERGE_TOOL_VIEWERS or _python_viewer(cmd):
        return False
    return any(_names_merge_tool(t, cwds, project, links) for t in cmd[1:])


# ---------------------------------------------------------------- one command


def _check_gh(gh, lane):
    group, sub, args = gh
    if g.is_dynamic(group) or g.is_dynamic(sub):
        return ("a gh command group or subcommand computed by the shell is blocked for everyone "
                "(it could be `gh pr merge`); write it out")
    if group == "pr" and sub == "merge":
        return "raw `gh pr merge` is blocked for everyone; use tools/ship/merge"
    if group == "alias" and sub in ("set", "import"):
        return f"`gh alias {sub}` is blocked for everyone (an alias can hide a merge)"
    if group == "api":
        return _gh_api_reason(args, lane)
    if lane and group == "repo" and sub in ("clone", "fork") and any(str(a) == "--" for a in args):
        reason = _clone_reason(args[[str(a) for a in args].index("--") + 1 :])
        if reason:
            return reason
    if lane and group not in GH_LANE_ALLOW_GROUPS:
        allowed = GH_LANE_ALLOW.get(str(group), set())
        if sub not in allowed:
            shown = f"gh {group} {sub}" if sub else f"gh {group}"
            return f"lanes may not run `{shown}` (push, PRs, workflows and other writes belong to the orchestrator)"
    return None


def _clone_reason(args):
    """git clone (also through `gh repo clone ... -- <git flags>`): config,
    templates and upload-pack commands that skip or replace hooks."""
    vals = []
    j = 0
    while j < len(args):
        t = str(args[j])
        if t in ("-c", "--config") and j + 1 < len(args):
            vals.append(args[j + 1])
            j += 2
            continue
        if t.startswith("--config="):
            vals.append(g.sub_word(args[j], t.split("=", 1)[1]))
        elif t.startswith("-c") and len(t) > 2:
            vals.append(g.sub_word(args[j], t[2:]))
        elif g.long_opt(t, "--template") or g.long_opt(t, "--upload-pack") or t == "-u" or (
                t.startswith("-u") and not t.startswith("--")):
            return f"lanes may not pass {t.split('=', 1)[0]} to git clone (it can replace hooks or run a command)"
        j += 1
    for cfg in vals:
        if g.is_dynamic(cfg):
            return "lanes may not pass git clone -c values computed by the shell"
        what = _config_rule(cfg)
        if what:
            return f"lanes may not {what} (git clone -c {str(cfg).split('=', 1)[0]})"
    return None


def _check_git_lane(cmd, parts):
    sub, args, _chdirs, configs = parts
    if str(sub) == "clone":
        reason = _clone_reason(args)
        if reason:
            return reason
    if g.is_dynamic(sub):
        return f"lanes may not run a git subcommand computed by the shell ({sub}); write it out"
    for cfg in configs:
        if g.is_dynamic(cfg):
            return "lanes may not pass git -c values computed by the shell"
        what = _config_rule(cfg)
        if what == "define git aliases":
            return "lanes may not define git aliases (git -c alias.*)"
        if what:
            return f"lanes may not {what} (git -c {str(cfg).split('=', 1)[0]})"
    if any(str(t).startswith("--exec-path=") for t in g.git_global_words(cmd)):
        return "lanes may not point git at another --exec-path"
    if _is_push(parts):
        return "lanes may not git push; return the branch to the orchestrator"
    if sub == "reset":
        if any(g.long_opt(a, "--hard") for a in args):
            return "lanes may not git reset --hard"
        if _dynamic_option(args):
            return "lanes may not pass git reset arguments computed by the shell (one could be --hard)"
    if sub == "clean":
        if any(g.long_opt(a, "--force") or (str(a).startswith("-") and not str(a).startswith("--")
                                            and "f" in str(a)[1:]) for a in args):
            return "lanes may not git clean -f"
        if _dynamic_option(args, value_short="e", value_long={"--exclude"}):
            return "lanes may not pass git clean arguments computed by the shell (one could be -f)"
    if sub == "commit":
        if _commit_skips_hooks(args):
            return "lanes may not skip hooks with git commit -n"
        if _dynamic_option(args, value_short="mFCct",
                           value_long={"--message", "--file", "--author", "--date", "--template",
                                       "--reuse-message", "--reedit-message", "--fixup", "--squash",
                                       "--trailer", "--cleanup"}):
            return "lanes may not pass git commit options computed by the shell (one could be --no-verify)"
    if sub == "config":
        for a in args:
            what = _config_rule(a)
            if what == "define git aliases":
                return "lanes may not define git aliases (git config alias.*)"
            if what:
                return f"lanes may not {what} (git config {a})"
        if _config_key_dynamic(args):
            return "lanes may not run git config with a key or option computed by the shell"
    return None


def _hidden_tool_reason(cmd, lane, depth=0):
    """Safety net for programs the parser does not know (strace -f git push,
    tmux new -d 'git push', at now <<< 'gh pr merge 3'): git push (lanes) or
    gh pr merge (everyone) later in the same command, or inside one of its
    arguments or here-strings that holds shell text."""
    base = os.path.basename(str(cmd[0]))
    if base in TEXT_COMMANDS or base in ("git", "gh") or base.startswith("git-"):
        return None
    for k in range(1, len(cmd)):
        word = os.path.basename(str(cmd[k]))
        if lane and (word == "git" or word.startswith("git-")):
            parts = g.git_parts(cmd[k:])
            if parts and _is_push(parts):
                return f"lanes may not git push (found behind `{base}`, which the guard does not know as a wrapper)"
        if word == "gh":
            gh = g.gh_parts(cmd[k:])
            if gh and gh[0] == "pr" and gh[1] == "merge":
                return f"raw `gh pr merge` is blocked for everyone (found behind `{base}`); use tools/ship/merge"
    if depth >= 2:
        return None
    for k in range(1, len(cmd)):
        text = str(cmd[k])
        if not re.search(r"\s", text.strip()) or not re.search(r"\b(git|gh)\b", text):
            continue
        for inner in g.split_commands(text):
            parts = g.git_parts(inner)
            if lane and parts and _is_push(parts):
                return f"lanes may not git push (found in an argument of `{base}`, which runs shell text)"
            gh = g.gh_parts(inner)
            if gh and gh[0] == "pr" and gh[1] == "merge":
                return f"raw `gh pr merge` is blocked for everyone (found in an argument of `{base}`); use tools/ship/merge"
            reason = _hidden_tool_reason(inner, lane, depth + 1)
            if reason:
                return reason
    return None


def _check_info(info, lane, cwds, project, links=()):
    """Reason to block one simple command, or None."""
    cmd = info["core"]
    if not cmd:
        return None
    name, dynamic = g.command_word(cmd)
    if dynamic:
        if lane:
            return (f"lanes may not run a command whose name is computed by the shell ({cmd[0]}); "
                    "write the command out")
        if g.could_be_tool(cmd[0], info["env"]):
            return (f"the command name {cmd[0]} is computed by the shell and could be git/gh/sops/age; "
                    "write it out")
        return None
    if lane and "xargs" in info["wrappers"] and name in g.TOOLS:
        return f"lanes may not run `{name}` through xargs (the guard cannot see the arguments it appends)"

    gh = g.gh_parts(cmd)
    if gh:
        return _check_gh(gh, lane)

    if lane:
        parts = g.git_parts(cmd)
        if any(str(t) == "--no-verify" or str(t).startswith("--no-verify=") for t in cmd[1:]) or (
            parts and any(g.long_opt(t, "--no-verify") for t in parts[1])
        ):
            return "lanes may not skip hooks with --no-verify"
        if _runs_merge_tool(cmd, cwds, project, lane, links):
            return "lanes may not merge; the orchestrator runs tools/ship/merge"
        if parts:
            reason = _check_git_lane(cmd, parts)
            if reason:
                return reason
    return _hidden_tool_reason(cmd, lane)


# ---------------------------------------------------------------- environment


def _assignment_words(seg):
    """Tokens in assignment position: before the real command word, or after
    env/export/declare. A commit message that mentions FOO=1 is not one."""
    for tok in seg:
        if g.ENV_ASSIGN_RE.match(tok):
            yield tok
        elif str(tok).startswith("-") or os.path.basename(str(tok)) in ASSIGN_PREFIX_WORDS or tok in g.SHELL_KEYWORDS:
            continue
        else:
            return


def _env_reason(infos):
    """GIT_CONFIG_* / GIT_EXEC_PATH set anywhere (FOO=1 cmd, env FOO=1 cmd,
    export FOO=1) inject config such as aliases or hooksPath; HOME= or
    XDG_CONFIG_HOME= on a line that runs git swaps the global config."""
    runs_git = any(g.git_parts(info["core"]) for info in infos)
    for info in infos:
        for tok in _assignment_words(info["raw"]):
            m = GIT_CONFIG_ENV_RE.match(tok)
            if m:
                if m.group(1) == "GIT_EXEC_PATH":
                    return "lanes may not set GIT_EXEC_PATH (it swaps the git programs that run)"
                return f"lanes may not set {m.group(1)} (it injects git config such as aliases or hooksPath)"
            m = HOME_ENV_RE.match(tok)
            if m and runs_git:
                return f"lanes may not set {m.group(1)} next to git (it swaps the global git config)"
    return None


def _gh_env_reason(infos):
    """GH_CONFIG_DIR=, XDG_CONFIG_HOME= or HOME= on a line that runs gh loads
    another gh config, whose aliases could hide a merge (everyone)."""
    if not any(g.gh_parts(info["core"]) for info in infos):
        return None
    for info in infos:
        for tok in _assignment_words(info["raw"]):
            m = GH_CONFIG_ENV_RE.match(tok)
            if m:
                return f"setting {m.group(1)} next to gh is blocked (another gh config can hold aliases that hide a merge)"
    return None


# ---------------------------------------------------------------- protected config


def _protected_kind(path, home):
    """'gh' for the gh config (aliases), 'git' for git config and hooks, else None."""
    path = os.path.normpath(path)
    if path == os.path.join(home, ".config", "gh", "config.yml"):
        return "gh"
    if path in (os.path.join(home, ".gitconfig"), os.path.join(home, ".config", "git", "config")):
        return "git"
    parts = path.split(os.sep)
    if ".git" in parts:
        idx = len(parts) - 1 - parts[::-1].index(".git")
        rel = parts[idx + 1 :]
        if not rel or rel[0] in ("config", "config.worktree", "hooks") or "hooks" in rel:
            return "git"
        if rel[0] in ("worktrees", "modules") and rel[-1] in ("config", "config.worktree"):
            return "git"
    return None


def _write_targets(info):
    """Paths a Bash command writes: redirect targets and writer arguments."""
    raw = info["raw"]
    targets = [raw[k + 1] for k, t in enumerate(raw[:-1]) if g.is_redirect(t) and ">" in str(t)]
    cmd = info["core"]
    if not cmd:
        return targets
    base = os.path.basename(str(cmd[0]))
    args = [a for a in cmd[1:] if not g.is_redirect(a)]
    plain = [a for a in args if not str(a).startswith("-")]
    if base in WRITE_ALL_ARGS:
        targets.extend(plain)
    elif base in COPY_LIKE:
        for k, a in enumerate(args):
            if str(a) in ("-t", "--target-directory") and k + 1 < len(args):
                targets.append(args[k + 1])
            elif str(a).startswith("--target-directory="):
                targets.append(str(a).split("=", 1)[1])
        if plain:
            targets.append(plain[-1])
    elif base in ("sed", "perl") and any(str(a).startswith("-i") or str(a).startswith("--in-place") for a in args):
        targets.extend(plain)
    elif base == "dd":
        targets.extend(str(a)[3:] for a in args if str(a).startswith("of="))
    return targets


def _protected_reason(kind, path, lane):
    if kind == "gh":
        return (f"writing {path} is blocked for everyone (gh aliases live there and can hide a merge); "
                "edit it by hand")
    if kind == "git" and lane:
        return f"lanes may not write git config or hooks ({path}); the orchestrator owns them"
    return None


def _protected_bash_reason(infos, lane, cwd, project, home):
    for info in infos:
        for target in _write_targets(info):
            path = g.expand_path(str(target), cwd, project, home)
            reason = _protected_reason(_protected_kind(path, home), path, lane)
            if reason:
                return reason
    return None


def _check_file_tool(payload, project, cwd):
    ti = payload.get("tool_input") or {}
    home = g.home_dir()
    for field in ("file_path", "notebook_path"):
        val = ti.get(field)
        if isinstance(val, str) and val:
            path = g.expand_path(val, cwd, project, home)
            lane = g.is_lane(payload, [], cwd, project) or g.is_under(path, g.wt_root(project))
            reason = _protected_reason(_protected_kind(path, home), path, lane)
            if reason:
                return reason
    return None


# ---------------------------------------------------------------- entry


def check(payload):
    tool = payload.get("tool_name")
    project = g.project_dir(payload)
    cwd = g.payload_cwd(payload)
    if tool in FILE_TOOLS:
        return _check_file_tool(payload, project, cwd)
    if tool != "Bash":
        return None
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command.strip():
        return None
    infos = g.command_infos(command)
    lane = g.is_lane(payload, infos, cwd, project)
    cwds = g.track_cwds(infos, cwd, project)
    links = g.line_symlinks(infos, cwds, project)
    for info, folders in zip(infos, cwds):
        reason = _check_info(info, lane, folders, project, links)
        if reason:
            return reason
    reason = _gh_env_reason(infos)
    if reason:
        return reason
    if lane:
        for kind, seg in g.opaque_feeds(command):
            shown = " ".join(str(t) for t in seg)
            return (f"lanes may not run shell code the guard cannot read (`{shown}` reads it from "
                    f"{'a pipe' if kind == 'stdin' else 'a process substitution'}); run the commands directly")
        reason = _env_reason(infos)
        if reason:
            return reason
    return _protected_bash_reason(infos, lane, cwd, project, g.home_dir())


if __name__ == "__main__":
    g.run_guard(NAME, check)
