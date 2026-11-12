"""Shared helpers for the PreToolUse guard hooks (spec §9.7).

The hooks read one JSON payload from stdin. They block a tool call by
printing a reason to stderr and exiting 2. They allow it by exiting 0.

These hooks are guardrails against agent mistakes, not a sandbox. See
README.md "Limits" for what a text guard cannot see.

Design rules:
- Fail closed. If the payload cannot be parsed, or a hook crashes, the
  call is blocked with a clear message.
- A pre-pass normalises the shell text before shlex sees it:
  * comments (`#` at the start of a word, outside quotes) are dropped up
    to the end of the line, so an apostrophe in a comment cannot open a
    quote that hides the next lines;
  * here-document bodies are cut out, so text in a commit message or a
    file written with `cat > f <<'E'` is not read as commands. A body
    read by a shell (`bash <<X`, `cat <<X | sh`) is still parsed as
    commands; a body read by an interpreter (`python3 <<X`) is returned
    by code_bodies() for path scanning;
  * command substitution `$(...)`, backticks, arithmetic `$((...))` /
    `((...))` and process substitution `<(...)` stay one word, so
    `<<` inside arithmetic is never a here-document and a substitution
    in the middle of a word does not split it;
  * characters that only quoting makes literal (`$`, backtick, glob and
    brace characters) are marked, so each Word knows whether the shell
    would expand it (Word.expands, Word.globs);
  * ANSI-C strings `$'\\x67it'` are decoded.
- Assignments made earlier on the same line (`G=git; $G push`), `$IFS`,
  `${X:-default}` and empty positional parameters are resolved, and the
  resolved text is checked as well as the original.
- The text is split into simple commands on ; && || | & ( ) and
  newlines. Wrappers (env, sudo, timeout, nice, ionice, stdbuf, time,
  flock, xargs, ...) are stripped, and nested shell text is walked as
  commands: bash -c, eval, env -S, script -c, su -c, watch, fish -c,
  find -exec, git submodule foreach / rebase -x / bisect run, `!` git
  aliases, git options that take a command (grep -O, difftool -x,
  filter-branch filters, --upload-pack, ...), environment variables that
  hold a command (GIT_PAGER, GIT_EDITOR, EDITOR, PAGER, GIT_SSH_COMMAND,
  LESSOPEN, ...), here-strings fed to a shell or to `source /dev/stdin`,
  literal text piped into a shell, `sh -c SCRIPT arg0 arg1` with $0..$9
  filled in, aliases defined on the same line and command substitution.
- Paths: expand_path() normalises `//`, /proc/<pid>/root and
  /proc/<pid>/cwd, and `~+`. track_cwds() gives each command the folders
  it may run in (literal cd/pushd earlier on the line); line_symlinks()
  and path_aliases() follow `ln -s` links made earlier on the line.
"""

from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import re
import shlex
import sys
from urllib.parse import unquote

WT_REL = os.path.join(".tmp-session", "wt")

SEPARATORS = {";", "&&", "||", "|", "&", "|&", ";;", "(", ")", "$", "`"}
REDIRECT_RE = re.compile(r"^[0-9]*[<>&]+[|]?$")
GLOB_CHARS = set("*?[")
ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")

# Words that only introduce the real command.
SHELL_KEYWORDS = {"{", "}", "!", "then", "do", "else", "elif", "if", "while", "until", "coproc"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "mksh", "ash", "yash", "posh", "fish", "csh", "tcsh"}
# Tools whose command word or subcommand must be literal in a lane.
TOOLS = {"git", "gh", "sops", "age", "rage"}
# Programs that run a here-document body as code (not shell).
INTERPRETER_RE = re.compile(r"^(python[0-9.]*|pypy[0-9.]*|node|nodejs|deno|bun|perl|ruby|php|lua|Rscript|osascript)$")
MAX_DEPTH = 6

# Wrappers: name -> (short options with a value, long options with a value,
# short options whose value is shell text, long options whose value is shell
# text, positional words before the command, mode). Mode "core": the command
# follows; "none": no command follows (only the option text runs); "join":
# the rest is joined with spaces and run by sh -c (watch).
WRAPPERS = {
    "command": ("", set(), "", set(), 0, "core"),
    "builtin": ("", set(), "", set(), 0, "core"),
    "nohup": ("", set(), "", set(), 0, "core"),
    "setsid": ("", set(), "", set(), 0, "core"),
    "unbuffer": ("", set(), "", set(), 0, "core"),
    "chronic": ("", set(), "", set(), 0, "core"),
    "busybox": ("", set(), "", set(), 0, "core"),
    "exec": ("a", set(), "", set(), 0, "core"),
    "stdbuf": ("ioe", {"--input", "--output", "--error"}, "", set(), 0, "core"),
    "nice": ("n", {"--adjustment"}, "", set(), 0, "core"),
    "ionice": ("cnpPu", {"--class", "--classdata", "--pid", "--pgid", "--uid"}, "", set(), 0, "core"),
    "time": ("fo", {"--format", "--output"}, "", set(), 0, "core"),
    "timeout": ("ks", {"--kill-after", "--signal"}, "", set(), 1, "core"),
    "sudo": ("ugpChDrtUT", {"--user", "--group", "--host", "--prompt", "--close-from", "--chdir", "--role",
                             "--type", "--other-user", "--command-timeout"}, "", set(), 0, "core"),
    "doas": ("uC", set(), "", set(), 0, "core"),
    "xargs": ("nILPdsEa", {"--max-args", "--max-procs", "--delimiter", "--arg-file", "--max-lines", "--max-chars",
                           "--process-slot-var"}, "", set(), 0, "core"),
    "flock": ("wE", {"--wait", "--timeout", "--conflict-exit-code"}, "c", {"--command"}, 1, "core"),
    "chroot": ("", {"--userspec", "--groups"}, "", set(), 1, "core"),
    "script": ("EIOBTm", {"--echo", "--log-in", "--log-out", "--log-io", "--log-timing", "--logging-format"},
               "c", {"--command"}, 0, "none"),
    "su": ("gGsw", {"--group", "--supp-group", "--shell", "--whitelist-environment"}, "c", {"--command"}, 0, "none"),
    "runuser": ("gGsuw", {"--group", "--supp-group", "--shell", "--user", "--whitelist-environment"}, "c",
                {"--command"}, 0, "none"),
    "watch": ("nq", {"--interval", "--equexit"}, "", set(), 0, "join"),
    "taskset": ("", set(), "", set(), 1, "core"),
    "env": ("uC", {"--unset", "--chdir"}, "S", {"--split-string"}, 0, "core"),
}

# ---------------------------------------------------------------- payload


def read_payload(stream=None) -> dict:
    """Return the hook payload. Exit 2 if stdin is not a JSON object."""
    stream = stream if stream is not None else sys.stdin
    raw = stream.read()
    try:
        data = json.loads(raw)
    except ValueError:
        block("guard: hook payload is not valid JSON; blocking to be safe")
    if not isinstance(data, dict):
        block("guard: hook payload is not a JSON object; blocking to be safe")
    return data


def block(reason: str) -> None:
    """Print the reason to stderr and exit 2 (Claude Code blocks the call)."""
    sys.stderr.write(reason.rstrip() + "\n")
    sys.exit(2)


def run_guard(name: str, check) -> None:
    """Run check(payload) -> reason|None. Block on a reason or on a crash."""
    try:
        payload = read_payload()
        reason = check(payload)
    except SystemExit:
        raise
    except Exception as exc:  # fail closed on bugs
        block(f"{name}: guard error ({type(exc).__name__}: {exc}); blocking to be safe")
    if reason:
        block(f"{name}: {reason}")
    sys.exit(0)


def home_dir() -> str:
    return os.path.normpath(os.environ.get("HOME") or os.path.expanduser("~"))


def project_dir(payload: dict) -> str:
    """CLAUDE_PROJECT_DIR, else the payload cwd with any wt/<lane> tail cut off."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return os.path.normpath(env)
    cwd = os.path.normpath(payload.get("cwd") or os.getcwd())
    marker = os.sep + WT_REL
    idx = cwd.find(marker + os.sep)
    if idx < 0 and cwd.endswith(marker):
        idx = len(cwd) - len(marker)
    return cwd[:idx] if idx > 0 else cwd


def payload_cwd(payload: dict) -> str:
    return os.path.normpath(payload.get("cwd") or os.getcwd())


def wt_root(project: str) -> str:
    return os.path.normpath(os.path.join(project, WT_REL))


def is_under(path: str, root: str) -> bool:
    """True when path equals root or lies below it (lexical, after normpath)."""
    path = os.path.normpath(path)
    root = os.path.normpath(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def is_subagent(payload: dict) -> bool:
    """Subagent payloads carry agent_id; main-session payloads do not."""
    return bool(payload.get("agent_id"))


# ---------------------------------------------------------------- paths


def expand_vars(text: str, env: dict) -> str:
    def repl(m):
        name = m.group(1) or m.group(2)
        return env[name] if name in env else m.group(0)

    return VAR_RE.sub(repl, text)


_PROC_ROOT_RE = re.compile(r"^/proc/(?:self|thread-self|[0-9]+)/root(?=/|$)")
_PROC_CWD_RE = re.compile(r"^/proc/(?:self|thread-self|[0-9]+)/cwd(?=/|$)")


def normalize_abs(path: str, cwd: str) -> str:
    """normpath, then the aliases the kernel resolves for the same file:
    a leading `//` is `/`, `/proc/<pid>/root/x` is `/x` and
    `/proc/<pid>/cwd/x` is `<cwd>/x`."""
    path = os.path.normpath(path)
    for _ in range(8):
        before = path
        if path.startswith("//"):
            path = "/" + path.lstrip("/")
        path = _PROC_ROOT_RE.sub("", path) or "/"
        m = _PROC_CWD_RE.match(path)
        if m:
            path = cwd + path[m.end():]
        path = os.path.normpath(path)
        if path == before:
            break
    return path


def expand_path(token: str, cwd: str, project: str, home: str | None = None) -> str:
    """Expand ~, ~+, ~-, $HOME, $CLAUDE_PROJECT_DIR and $PWD; make absolute;
    normpath and normalize_abs."""
    home = home or home_dir()
    env = {"HOME": home, "CLAUDE_PROJECT_DIR": project, "PWD": cwd}
    text = expand_vars(token, env)
    if text == "~" or text.startswith("~/"):
        text = home + text[1:]
    elif text[:2] in ("~+", "~-") and (len(text) == 2 or text[2] == "/"):
        # ~+ is $PWD; ~- is $OLDPWD, which the caller's cwd list stands for.
        text = cwd + text[2:]
    elif text.startswith("~"):
        text = os.path.expanduser(text)
    if not os.path.isabs(text):
        text = os.path.join(cwd, text)
    return normalize_abs(text, cwd)


def glob_reaches(pattern: str, root: str) -> bool:
    """True when the absolute glob `pattern` can match root or a path below it.

    Compares component by component, so `*` never crosses a `/`.
    """
    pat = pattern.rstrip(os.sep).split(os.sep)
    parts = root.rstrip(os.sep).split(os.sep)
    if len(pat) < len(parts):
        return False
    return all(fnmatch.fnmatchcase(r, p) for r, p in zip(parts, pat))


def glob_ancestor(pattern: str, root: str) -> bool:
    """True when `pattern` (absolute, maybe a glob) can be root or a folder above it."""
    if not has_glob(pattern):
        return is_under(root, pattern)
    pat = pattern.rstrip(os.sep).split(os.sep) or [""]
    parts = root.rstrip(os.sep).split(os.sep)
    if len(pat) > len(parts):
        return False
    return all(fnmatch.fnmatchcase(r, p) for r, p in zip(parts, pat))


# ---------------------------------------------------------------- cd and ln on the same line


def _plain_args(cmd):
    """Arguments of a stripped command without redirects and their targets."""
    out = []
    skip = False
    for tok in cmd[1:]:
        if skip:
            skip = False
            continue
        if is_redirect(str(tok)):
            skip = True
            continue
        out.append(tok)
    return out


def _literal_path_word(word) -> bool:
    """A word the guard can turn into a path: no expansion other than
    $HOME, $CLAUDE_PROJECT_DIR and $PWD (globs are kept as patterns)."""
    if not isinstance(word, Word) or not word.expands:
        return True
    if word.spans:
        return False
    rest = re.sub(r"\$\{?(HOME|CLAUDE_PROJECT_DIR|PWD)\}?", "", str(word))
    return "$" not in rest and "`" not in rest


def cd_target(cmd, home: str | None = None):
    """The literal folder a `cd`/`pushd` moves to (`cd` alone is HOME), else None."""
    if not cmd or os.path.basename(str(cmd[0])) not in ("cd", "pushd", "chdir"):
        return None
    args = _plain_args(cmd)
    while args and str(args[0]).startswith("-") and str(args[0]) != "-":
        if str(args.pop(0)) == "--":
            break
    if not args:
        return (home or home_dir()) if os.path.basename(str(cmd[0])) != "pushd" else None
    word = args[0]
    if str(word) == "-" or str(word).startswith("+") or not _literal_path_word(word):
        return None
    return str(word)


MAX_CWDS = 16


def track_cwds(infos, cwd: str, project: str, home: str | None = None) -> list:
    """For each command (in walk order), the folders it may run in: the
    payload cwd and every literal cd/pushd target seen earlier on the line.
    Keeping the payload cwd covers subshells such as `(cd x); cat y`."""
    home = home or home_dir()
    seen = [cwd]
    out = []
    for item in infos:
        out.append(list(seen))
        cmd = item["core"] if isinstance(item, dict) else item
        target = cd_target(cmd, home)
        if target is None:
            continue
        for base in list(seen):
            path = expand_path(target, base, project, home)
            if path not in seen and len(seen) < MAX_CWDS:
                seen.append(path)
    return out


def _ln_links(cmd, cwd, project, home):
    """(link, target) pairs for `ln -s` (absolute, normalised)."""
    if not cmd or os.path.basename(str(cmd[0])) not in ("ln", "cp"):
        return []
    args = _plain_args(cmd)
    symbolic = False
    target_dir = None
    pos = []
    i = 0
    while i < len(args):
        t = str(args[i])
        if t == "--":
            pos.extend(str(a) for a in args[i + 1 :])
            break
        if t in ("-t", "--target-directory") and i + 1 < len(args):
            target_dir = str(args[i + 1])
            i += 2
            continue
        if t.startswith("--target-directory="):
            target_dir = t.split("=", 1)[1]
        elif t in ("-S", "--suffix"):
            i += 2
            continue
        elif t == "--symbolic" or (t.startswith("-") and not t.startswith("--") and "s" in t[1:]):
            symbolic = True
        elif not t.startswith("-"):
            pos.append(t)
        i += 1
    if not symbolic or not pos:
        return []
    pairs = []
    if target_dir is not None:
        dest = expand_path(target_dir, cwd, project, home)
        links = [(t, os.path.join(dest, os.path.basename(t.rstrip("/")))) for t in pos]
    elif len(pos) == 1:
        links = [(pos[0], os.path.join(cwd, os.path.basename(pos[0].rstrip("/"))))]
    else:
        dest = expand_path(pos[-1], cwd, project, home)
        links = [(t, os.path.join(dest, os.path.basename(t.rstrip("/")))) for t in pos[:-1]]
        if len(pos) == 2:
            links.append((pos[0], dest))
    for target, link in links:
        link = normalize_abs(link, cwd)
        dest = expand_path(target, os.path.dirname(link), project, home)
        pairs.append((link, dest))
    return pairs


def line_symlinks(infos, cwds, project: str, home: str | None = None) -> list:
    """(link, target) for every `ln -s` (or `cp -s`) on the line, for each
    folder it may run in."""
    home = home or home_dir()
    out = []
    for item, folders in zip(infos, cwds):
        cmd = item["core"] if isinstance(item, dict) else item
        for folder in folders:
            for pair in _ln_links(cmd, folder, project, home):
                if pair not in out:
                    out.append(pair)
    return out


def path_aliases(path: str, links) -> list:
    """path, plus what it names when a link made on the same line sits on it."""
    out = [path]
    for _ in range(3):
        added = False
        for p in list(out):
            for link, target in links:
                if is_under(p, link) and p != target:
                    alias = os.path.normpath(target + p[len(link.rstrip(os.sep)):])
                    if alias not in out and len(out) < 32:
                        out.append(alias)
                        added = True
        if not added:
            break
    return out


def has_glob(text: str) -> bool:
    return any(c in GLOB_CHARS for c in text)


BRACE_RE = re.compile(r"(?<!\$)\{([^{}]*,[^{}]*)\}")
MAX_BRACE = 64


def brace_expand(text: str) -> list[str]:
    """Expand simple {a,b} groups like the shell does (not ${VAR})."""
    out = [text]
    for _ in range(8):
        nxt = []
        changed = False
        for item in out:
            m = BRACE_RE.search(item)
            if not m:
                nxt.append(item)
                continue
            changed = True
            for alt in m.group(1).split(","):
                nxt.append(item[: m.start()] + alt + item[m.end() :])
        out = nxt[:MAX_BRACE]
        if not changed:
            break
    return out


# ---------------------------------------------------------------- words

# Characters that are special only when unquoted. Inside quotes the
# pre-pass swaps them for private-use characters, so a Word can tell a real
# expansion from a quoted one. Restoring is one character for one, so
# offsets stay valid.
_PH = {"$": "", "`": "", "*": "", "?": "", "[": "",
       "{": "", "}": "", ",": ""}
_PROCSUB_IN = ""   # marks <(...) ; restored to "<"
_PROCSUB_OUT = ""  # marks >(...) ; restored to ">"
_PH_BACK = {v: k for k, v in _PH.items()}
_PH_BACK[_PROCSUB_IN] = "<"
_PH_BACK[_PROCSUB_OUT] = ">"
_PH_RE = re.compile("[-]")
DQ_LITERAL = "*?[{},"  # literal inside double quotes ($ and ` still expand there)

EXPAND_RE = re.compile(r"\$(?:[({]|[A-Za-z_0-9@*#?$!-])|`")
UNQUOTED_GLOB_RE = re.compile(r"[*?]|\[[^\]]+\]|(?<!\$)\{[^{}]*(?:,|\.\.)[^{}]*\}")


def _restore(text: str) -> str:
    return _PH_RE.sub(lambda m: _PH_BACK[m.group(0)], text)


class Word(str):
    """A shell word after quote removal.

    expands: it holds a parameter, command or arithmetic expansion.
    globs: it holds an unquoted glob or brace expansion.
    spans: (start, end, inner) of each command substitution.
    procsub: it is a process substitution <(...) or >(...).
    """

    expands: bool
    globs: bool
    spans: tuple
    procsub: bool
    ph: str

    def __new__(cls, ph_text: str):
        obj = str.__new__(cls, _restore(ph_text))
        spans = tuple((a, b, _restore(inner)) for a, b, inner in _subst_spans(ph_text))
        outer = ph_text
        for a, b, _inner in reversed(spans):
            outer = outer[:a] + outer[b:]
        obj.ph = ph_text
        obj.spans = spans
        obj.expands = bool(spans) or bool(EXPAND_RE.search(outer))
        obj.globs = bool(UNQUOTED_GLOB_RE.search(outer))
        obj.procsub = ph_text[:1] in (_PROCSUB_IN, _PROCSUB_OUT)
        return obj

    @property
    def substs(self):
        return [inner for _a, _b, inner in self.spans if inner.strip()]


def is_dynamic(word) -> bool:
    """True when the shell computes this word (expansion, glob or brace)."""
    return isinstance(word, Word) and (word.expands or word.globs)


def sub_word(word, text: str):
    """A slice of a Word (an option value) keeps the parent's dynamic flags."""
    if not isinstance(word, Word):
        return text
    out = Word(text.replace("$", _PH["$"]).replace("`", _PH["`"]))
    out.expands = word.expands and ("$" in text or "`" in text)
    out.globs = word.globs and bool(UNQUOTED_GLOB_RE.search(text))
    return out


def literal_tail(word) -> str | None:
    """The literal file name of a dynamic command word such as
    `$(git rev-parse --show-toplevel)/tools/x` (here `x`), else None.

    The last `/` must lie outside every substitution and the text after it
    must hold no expansion, glob or brace.
    """
    if not isinstance(word, Word):
        return None
    text = word.ph
    k = text.rfind("/")
    if k < 0 or any(a <= k < b for a, b, _ in word.spans):
        return None
    tail = text[k + 1 :]
    if not tail or re.search(r"[$`*?\[{}()]", tail):
        return None
    return _restore(tail)


# ---------------------------------------------------------------- scanning helpers


def _match_close(text: str, i: int) -> int:
    """text[i] is '('. Return the index of the matching ')', or -1.

    Understands quotes, backslashes, nested $(...), backticks, comments and
    here-document bodies (so an apostrophe in a commit message inside
    "$(cat <<'EOF' ... EOF)" does not open a quote).
    """
    n = len(text)
    depth = 0
    quote = None
    pending: list[tuple[str, bool]] = []
    j = i
    while j < n:
        c = text[j]
        if quote == "'":
            if c == "'":
                quote = None
        elif c == "\\":
            j += 2
            continue
        elif quote == '"':
            if c == '"':
                quote = None
            elif c == "$" and text.startswith("$(", j):
                k = _match_close(text, j + 1)
                if k < 0:
                    return -1
                j = k + 1
                continue
            elif c == "`":
                k = _backtick_end(text, j + 1)
                if k < 0:
                    return -1
                j = k + 1
                continue
        elif c in ("'", '"'):
            quote = c
        elif c == "`":
            k = _backtick_end(text, j + 1)
            if k < 0:
                return -1
            j = k + 1
            continue
        elif c == "#" and (j == i + 1 or text[j - 1] in " \t\n;&|("):
            k = text.find("\n", j)
            if k < 0:
                return -1
            j = k
            continue
        elif c == "<" and text.startswith("<<", j) and not text.startswith("<<<", j) and text[j - 1] != "<":
            k = j + 2
            strip_tabs = k < n and text[k] == "-"
            parsed = _heredoc_word(text, k + 1 if strip_tabs else k)
            if parsed:
                pending.append((parsed[0], strip_tabs))
                j = parsed[1]
                continue
        elif c == "\n" and pending:
            found = _heredoc_bodies(text, j + 1, pending)
            pending = []
            if found is not None:
                j = found[1]
                continue
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return -1


def _backtick_end(text: str, j: int) -> int:
    """Index of the backtick closing one opened before j, or -1."""
    n = len(text)
    while j < n:
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == "`":
            return j
        j += 1
    return -1


def _subst_spans(text: str):
    """(start, end, inner) for each real $(...) or backtick in a word.

    An unclosed one runs to the end of the word (its text is still walked).
    """
    spans = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("$(", i):
            k = _match_close(text, i + 1)
            if k < 0:
                spans.append((i, n, text[i + 2 :]))
                break
            if text.startswith("$((", i) and _match_close(text, i + 2) == k - 1:
                # Arithmetic: not a command, but it may hold substitutions.
                inner = [s[2] for s in _subst_spans(text[i + 3 : k - 1])]
                spans.append((i, k + 1, "\n".join(inner)))
            else:
                spans.append((i, k + 1, text[i + 2 : k]))
            i = k + 1
        elif text[i] == "`":
            k = _backtick_end(text, i + 1)
            if k < 0:
                spans.append((i, n, text[i + 1 :]))
                break
            spans.append((i, k + 1, text[i + 1 : k]))
            i = k + 1
        else:
            i += 1
    return spans


_ANSI_SIMPLE = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n", "r": "\r",
                "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}
_ANSI_RE = re.compile(r"\\(?:([abeEfnrtv\\'\"?])|([0-7]{1,3})|x([0-9A-Fa-f]{1,2})|u([0-9A-Fa-f]{1,4})"
                      r"|U([0-9A-Fa-f]{1,8})|c(.))", re.S)


def _ansi_c_decode(body: str) -> str:
    def repl(m):
        if m.group(1):
            return _ANSI_SIMPLE[m.group(1)]
        if m.group(2):
            return chr(int(m.group(2), 8) & 0xFF)
        for g in (3, 4, 5):
            if m.group(g):
                try:
                    return chr(int(m.group(g), 16))
                except (ValueError, OverflowError):
                    return ""
        return chr(ord(m.group(6)) & 0x1F)

    return _ANSI_RE.sub(repl, body)


def _ansi_c_end(text: str, j: int) -> int:
    n = len(text)
    while j < n:
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == "'":
            return j
        j += 1
    return -1


def _sq_ph(text: str) -> str:
    """Single-quote text for the pre-pass output, marking special characters."""
    marked = "".join(_PH.get(ch, ch) for ch in text)
    return "'" + marked.replace("'", "'\"'\"'") + "'"


def _dq_wrap(raw: str, quote) -> str:
    """Raw substitution text as part of a double-quoted shlex word."""
    esc = raw.replace("\\", "\\\\").replace('"', '\\"')
    return esc if quote == '"' else '"' + esc + '"'


# ---------------------------------------------------------------- here-documents


def _heredoc_word(command: str, j: int):
    """Parse a here-document delimiter that starts at j (after `<<` or `<<-`).

    Handles WORD, 'WORD', "WORD" and \\WORD. Returns (word, end) or None.
    """
    n = len(command)
    while j < n and command[j] in " \t":
        j += 1
    word = []
    while j < n:
        c = command[j]
        if c in ("'", '"'):
            k = command.find(c, j + 1)
            if k < 0:
                return None
            word.append(command[j + 1 : k])
            j = k + 1
        elif c == "\\" and j + 1 < n and command[j + 1] != "\n":
            word.append(command[j + 1])
            j += 2
        elif c.isspace() or c in ";&|()<>`":
            break
        else:
            word.append(c)
            j += 1
    text = "".join(word)
    return (text, j) if text else None


def _heredoc_bodies(command: str, pos: int, pending: list):
    """Read the bodies of the pending here-documents, starting at pos.

    Returns (bodies, position after the last terminator line), or None when a
    terminator is missing (the caller then keeps the text as commands).
    """
    n = len(command)
    bodies = []
    for word, strip_tabs in pending:
        lines = []
        while True:
            if pos >= n:
                return None
            k = command.find("\n", pos)
            line, pos = (command[pos:], n) if k < 0 else (command[pos:k], k + 1)
            if (line.lstrip("\t") if strip_tabs else line) == word:
                break
            lines.append(line)
        bodies.append("\n".join(lines))
    return bodies, pos


def _line_kind(line: str) -> str:
    """What reads a here-document on this line: 'shell', 'code' or 'data'.

    Any shell word on the line (bash <<X, cat <<X | sh, sudo bash -s <<X,
    cat <<X | $(which bash)) makes the body shell commands. An interpreter
    (python, node, ...) makes it code. Anything else (cat > file,
    git commit -F -, tee) is data.
    """
    line = _restore(line)
    try:
        lex = shlex.shlex(line, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        words = list(lex)
    except ValueError:
        words = re.findall(r"[^\s;&|()<>'\"]+", line)
    if re.search(r"\|\s*[\"']?(\$|`)", line):
        return "shell"  # cat <<X | $SHELL
    kind = "data"
    for word in words:
        for piece in re.split(r"[\s()$\"'`]+", word):
            base = os.path.basename(piece)
            if base in SHELLS:
                return "shell"
            if INTERPRETER_RE.match(base):
                kind = "code"
    return kind


# ---------------------------------------------------------------- pre-pass


def _word_start(out: list) -> bool:
    if not out:
        return True
    return out[-1][-1] in " \t;&|()"


def _prepass_full(command: str):
    """Normalise shell text for shlex and pull out here-document bodies.

    See the module docstring. Returns (text, bodies) where bodies is a list
    of (kind, body, quoted): kind comes from _line_kind, and quoted is True
    when the delimiter was quoted (the shell then expands nothing in it).
    """
    out: list[str] = []
    bodies: list[tuple[str, str]] = []
    pending: list[tuple[str, bool]] = []
    quoted: list[bool] = []
    line_start = 0
    quote = None
    i = 0
    n = len(command)
    while i < n:
        c = command[i]
        if quote == "'":
            if c == "'":
                quote = None
                out.append(c)
            else:
                out.append(_PH.get(c, c))
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            nxt = command[i + 1]
            if nxt == "\n":
                i += 2
                continue
            if nxt in _PH and (quote is None or nxt in "$`"):
                out.append(_PH[nxt])
            elif quote == '"' and nxt in _PH:
                out.append("\\" + _PH[nxt])
            else:
                out.append(command[i : i + 2])
            i += 2
            continue
        if c == "$" and quote is None and command.startswith("$'", i):
            k = _ansi_c_end(command, i + 2)
            if k >= 0:
                out.append(_sq_ph(_ansi_c_decode(command[i + 2 : k])))
                i = k + 1
                continue
        if c == "$" and quote is None and command.startswith('$"', i):
            i += 1
            continue
        if c == "$" and command.startswith("$(", i):
            k = _match_close(command, i + 1)
            if k >= 0:
                out.append(_dq_wrap(command[i : k + 1], quote))
                i = k + 1
                continue
        if c == "`":
            k = _backtick_end(command, i + 1)
            if k >= 0:
                inner = re.sub(r"\\([$`\\])", r"\1", command[i + 1 : k])
                out.append(_dq_wrap("$(" + inner + ")", quote))
                i = k + 1
                continue
            out.append(" ; " if quote is None else c)
            i += 1
            continue
        if quote == '"':
            if c == '"':
                quote = None
                out.append(c)
            else:
                out.append(_PH[c] if c in DQ_LITERAL else c)
            i += 1
            continue
        # ---- unquoted from here
        if c in ("'", '"'):
            quote = c
            out.append(c)
        elif c == "#" and _word_start(out):
            k = command.find("\n", i)
            i = n if k < 0 else k
            continue
        elif c == "(" and command.startswith("((", i) and _word_start(out):
            k = _match_close(command, i)
            if k > 0 and command[k - 1] == ")" and _match_close(command, i + 1) == k - 1:
                # Arithmetic command: never a here-document, never a command.
                out.append(" : " + _dq_wrap("$" + command[i : k + 1], None) + " ")
                i = k + 1
                continue
            out.append(c)
        elif c in "<>" and command.startswith("(", i + 1) and not (i > 0 and command[i - 1] in "<>"):
            k = _match_close(command, i + 1)
            if k >= 0:
                mark = _PROCSUB_IN if c == "<" else _PROCSUB_OUT
                out.append(mark + _dq_wrap("$" + command[i + 1 : k + 1], None))
                i = k + 1
                continue
            out.append(c)
        elif (
            c == "<"
            and command.startswith("<<", i)
            and not command.startswith("<<<", i)
            and not (i > 0 and command[i - 1] == "<")
        ):
            j = i + 2
            strip_tabs = j < n and command[j] == "-"
            parsed = _heredoc_word(command, j + 1 if strip_tabs else j)
            if parsed is None:
                out.append("<<")
                i += 2
                continue
            word, end = parsed
            pending.append((word, strip_tabs))
            quoted.append(bool(re.search(r"['\"\\]", command[j:end])))
            out.append(command[i:end])
            i = end
            continue
        elif c == "\n":
            if pending:
                found = _heredoc_bodies(command, i + 1, pending)
                pending = []
                flags, quoted = quoted, []
                if found is not None:
                    kind = _line_kind("".join(out[line_start:]))
                    bodies.extend((kind, body, q) for body, q in zip(found[0], flags))
                    out.append(" ; ")
                    line_start = len(out)
                    i = found[1]
                    continue
            out.append(" ; ")
            line_start = len(out)
        else:
            out.append(c)
        i += 1
    return "".join(out), bodies


def _prepass(command: str) -> str:
    """Text of _prepass_full without the here-document bodies."""
    return _prepass_full(command)[0]


# ---------------------------------------------------------------- same-line variables

_PARAM_RE = re.compile(
    r"\$\{(?P<b>[A-Za-z_][A-Za-z0-9_]*)(?P<rest>[^{}]*)\}"
    r"|\$(?P<n>[A-Za-z_][A-Za-z0-9_]*)"
    r"|\$(?P<pos>[1-9@*])"
)
_DEFAULT_OP_RE = re.compile(r"^(:?[-=+])(.*)$", re.S)
_ASSIGN_AT_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=")
_FOR_RE = re.compile(r"(?:for|select)\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([^;\n]*)")


def _render(value: str, literal: bool, quote) -> str:
    """Text that stands for an expanded value at this point of the line."""
    if not literal:
        return value
    if quote == '"':
        return re.sub(r'([\\"$`])', r"\\\1", value)
    parts = re.split(r"(\s+)", value)
    return "".join(" " if p.isspace() else shlex.quote(p) for p in parts if p)


def _value_end(text: str, j: int) -> int:
    """End of an assignment value word that starts at j."""
    n = len(text)
    quote = None
    while j < n:
        c = text[j]
        if quote == "'":
            if c == "'":
                quote = None
        elif c == "\\":
            j += 2
            continue
        elif c == "$" and text.startswith("$(", j):
            k = _match_close(text, j + 1)
            if k < 0:
                return n
            j = k + 1
            continue
        elif c == "`":
            k = _backtick_end(text, j + 1)
            if k < 0:
                return n
            j = k + 1
            continue
        elif quote == '"':
            if c == '"':
                quote = None
        elif c in ("'", '"'):
            quote = c
        elif c.isspace() or c in ";&|()<>":
            return j
        j += 1
    return n


def _resolve(text: str, top: bool, env: dict | None = None, record: bool = True):
    """Substitute variables assigned earlier on the same line.

    Returns (resolved_text, env) where env maps NAME -> (value, literal,
    substitutable). $IFS becomes a space, ${X:-word} its default when X is
    unknown, and at the top level $1..$9, $@ and $* are empty. Loop
    variables (for X in ...) are recorded but not substituted.
    """
    env = {} if env is None else env
    out: list[str] = []
    quote = None
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if quote == "'":
            out.append(c)
            if c == "'":
                quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(text[i : i + 2])
            i += 2
            continue
        if c == "$":
            m = _PARAM_RE.match(text, i)
            rep = _param_value(m, env, top) if m else None
            if rep is not None:
                out.append(_render(rep[0], rep[1], quote))
                i = m.end()
                continue
        if quote == '"':
            out.append(c)
            if c == '"':
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            out.append(c)
            i += 1
            continue
        at_start = i == 0 or text[i - 1] in " \t\n;&|()"
        if record and at_start:
            m = _ASSIGN_AT_RE.match(text, i)
            if m:
                k = _value_end(text, m.end())
                raw_val = text[m.end() : k]
                val = _resolve(raw_val, top, env, record=False)[0]
                literal = not re.search(r"[$`]", val)
                if literal:
                    try:
                        val = " ".join(shlex.split(val))
                    except ValueError:
                        literal = False
                env[m.group(1)] = (val, literal, True)
                out.append(text[i : m.end()] + _resolve(raw_val, top, env, record=False)[0])
                i = k
                continue
            m = _FOR_RE.match(text, i)
            if m:
                env[m.group(1)] = (m.group(2), True, False)
        out.append(c)
        i += 1
    return "".join(out), env


def _param_value(m, env, top):
    """(value, literal) for a parameter expansion we can resolve, else None."""
    if m.group("pos"):
        return ("", True) if top else None
    name = m.group("b") or m.group("n")
    rest = m.group("rest") or ""
    if name == "IFS":
        return (" ", False)
    known = env.get(name)
    if known is not None and not known[2]:
        return None
    if m.group("n") or not rest:
        return (known[0], known[1]) if known else None
    op = _DEFAULT_OP_RE.match(rest)
    if not op:
        return None
    kind, word = op.group(1), op.group(2)
    if kind in ("-", ":-", "=", ":="):
        if known and (known[0] or not kind.startswith(":")):
            return (known[0], known[1])
        return (word, not re.search(r"[$`]", word))
    if kind in ("+", ":+"):
        return (word, not re.search(r"[$`]", word)) if known else ("", True)
    return None


def line_assignments(command: str) -> dict:
    """NAME -> value for variables assigned on this line (top level)."""
    return {k: v[0] for k, v in _resolve(command, True)[1].items()}


# ---------------------------------------------------------------- tokenising


def tokenize(command: str) -> list[str]:
    """shlex tokens with shell punctuation split out. Falls back on bad quoting."""
    return _tokenize_text(_prepass(command))


def _tokenize_text(text: str) -> list[Word]:
    try:
        lex = shlex.shlex(text, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        raw = list(lex)
    except ValueError:
        # Unbalanced quotes: strip quotes and split on whitespace and punctuation.
        text = text.replace('"', " ").replace("'", " ")
        raw = re.findall(r"[;&|()<>]+|[^\s;&|()<>]+", text)
    return [Word(t) for t in raw]


def _is_sep(tok) -> bool:
    return tok in SEPARATORS or bool(tok and set(tok) <= set(";&|()"))


def _split_with_ops(tokens):
    """[(segment, separators before it)]."""
    out = []
    cur: list = []
    ops: list[str] = []
    for tok in tokens:
        if _is_sep(tok):
            if cur:
                out.append((cur, ops))
                cur, ops = [], []
            ops.append(str(tok))
        else:
            cur.append(tok)
    if cur:
        out.append((cur, ops))
    return out


def _split_tokens(tokens):
    return [seg for seg, _ops in _split_with_ops(tokens)]


def _requote(tokens) -> str:
    """Join tokens back into shell text, keeping expansions expandable."""
    parts = []
    for tok in tokens:
        if is_dynamic(tok):
            parts.append('"' + re.sub(r'(["\\])', r"\\\1", str(tok)) + '"')
        else:
            parts.append(shlex.quote(str(tok)))
    return " ".join(parts)


# ---------------------------------------------------------------- wrappers


def _skip_options(seg, i, spec, nested):
    """Skip a wrapper's options from i. Collect shell-text option values."""
    value_short, value_long, nested_short, nested_long = spec[:4]
    n = len(seg)
    while i < n:
        t = str(seg[i])
        if t == "--":
            return i + 1
        if not t.startswith("-") or t == "-":
            return i
        if t.startswith("--"):
            name, eq, val = t.partition("=")
            if name in nested_long:
                nested.append(val if eq else (str(seg[i + 1]) if i + 1 < n else ""))
                i += 1 if eq else 2
            elif name in value_long and not eq:
                i += 2
            else:
                i += 1
            continue
        letters = t[1:]
        if letters.isdigit():  # nice -10
            i += 1
            continue
        step = 1
        for k, ch in enumerate(letters):
            if ch in value_short or ch in nested_short:
                val = letters[k + 1 :]
                if not val:
                    val = str(seg[i + 1]) if i + 1 < n else ""
                    step = 2
                if ch in nested_short:
                    nested.append(val)
                break
        i += step
    return i


def _sudo_shell_mode(seg, i, spec) -> bool:
    """sudo -s / -i with a command runs it through a shell."""
    n = len(seg)
    while i < n:
        t = str(seg[i])
        if t == "--" or not t.startswith("-"):
            return False
        if t in ("--shell", "--login"):
            return True
        if t.startswith("--"):
            i += 2 if t in spec[1] else 1
            continue
        for ch in t[1:]:
            if ch in "si":
                return True
            if ch in spec[0]:
                break
        i += 2 if t[-1] in spec[0] else 1
    return False


def _unwrap(seg):
    """Strip keywords, assignments and wrappers in front of the real command.

    Returns (core, nested_texts, wrappers): nested_texts is shell text the
    wrappers run (env -S, script -c, su -c, flock -c, watch, sudo -s), and
    wrappers names the wrappers that were stripped.
    """
    i = 0
    n = len(seg)
    nested: list[str] = []
    wrappers: list[str] = []
    while i < n:
        tok = seg[i]
        base = os.path.basename(str(tok))
        if tok in SHELL_KEYWORDS or ENV_ASSIGN_RE.match(tok):
            i += 1
            continue
        if tok == "function":
            i += 2
            continue
        spec = WRAPPERS.get(base) if not is_dynamic(tok) else None
        if spec is None:
            break
        wrappers.append(base)
        i += 1
        before = len(nested)
        if base in ("sudo", "doas") and _sudo_shell_mode(seg, i, spec):
            i = _skip_options(seg, i, spec, nested)
            if i < n:
                nested.append(" ".join(str(t) for t in seg[i:]))
            return [], nested, wrappers
        i = _skip_options(seg, i, spec, nested)
        if base == "env":
            if len(nested) > before:
                # env -S 'cmd args' extra...: the split string is the command.
                nested[-1] = (nested[-1] + " " + _requote(seg[i:])).strip()
                return [], nested, wrappers
            while i < n and (str(seg[i]) == "-" or ENV_ASSIGN_RE.match(seg[i])):
                i += 1
            continue
        mode = spec[5]
        if mode == "none":
            # script/su: options may follow the positional words (su root -c x).
            while i < n:
                i = _skip_options(seg, i + 1, spec, nested)
            return [], nested, wrappers
        i += spec[4]
        if spec[4]:
            i = _skip_options(seg, i, spec, nested)  # flock FILE -c CMD
        if len(nested) > before:
            return [], nested, wrappers
        if mode == "join":
            nested.append(" ".join(str(t) for t in seg[i:]))
            return [], nested, wrappers
    core = seg[i:]
    if core and re.match(r"^=[A-Za-z0-9_.+-]+$", str(core[0])):
        # zsh `=git` expands to the path of git.
        core = [Word(str(core[0])[1:])] + list(core[1:])
    return core, nested, wrappers


def strip_wrappers(seg: list) -> list:
    """Drop keywords, env assignments and wrapper commands in front of the real one."""
    return _unwrap(seg)[0]


# ---------------------------------------------------------------- nested shell text

GIT_EXEC_CONFIG_RE = re.compile(
    r"^(core\.(editor|pager|sshcommand|fsmonitor|askpass)|sequence\.editor|diff\.external|gpg\.program"
    r"|credential\.helper|pager\..*|alias\..*|.*\.(textconv|command|cmd|process|clean|smudge))$",
    re.IGNORECASE,
)


def _shell_c_value(core):
    """The script of `bash -c SCRIPT` / `fish --command=SCRIPT`, else None."""
    for j, tok in enumerate(core[1:], start=1):
        t = str(tok)
        if t in ("--command",) and j + 1 < len(core):
            return str(core[j + 1])
        if t.startswith("--command="):
            return t.split("=", 1)[1]
        if t.startswith("-") and not t.startswith("--") and "c" in t[1:]:
            return str(core[j + 1]) if j + 1 < len(core) else ""
    return None


# Environment variables whose value a program runs as a command.
CMD_ENV_VARS = {"GIT_PAGER", "PAGER", "GIT_EDITOR", "EDITOR", "VISUAL", "GIT_SEQUENCE_EDITOR",
                "GIT_EXTERNAL_DIFF", "GIT_SSH_COMMAND", "GIT_SSH", "GIT_ASKPASS", "SSH_ASKPASS",
                "LESSOPEN", "LESSCLOSE", "GIT_PROXY_COMMAND", "MANPAGER", "SYSTEMD_PAGER", "GH_PAGER",
                "GH_EDITOR", "GH_BROWSER", "BROWSER"}
EXPORT_WORDS = {"export", "declare", "typeset", "readonly", "local"}

# git subcommand -> (short options, long options) whose value is a command.
GIT_CMD_OPTIONS = {
    "grep": ("O", {"--open-files-in-pager"}),
    "difftool": ("x", {"--extcmd"}),
    "filter-branch": ("", {"--env-filter", "--tree-filter", "--index-filter", "--parent-filter",
                           "--msg-filter", "--commit-filter", "--tag-name-filter"}),
    "clone": ("u", {"--upload-pack"}),
    "fetch": ("", {"--upload-pack"}),
    "pull": ("", {"--upload-pack"}),
    "ls-remote": ("u", {"--upload-pack"}),
    "push": ("", {"--receive-pack", "--exec"}),
    "archive": ("", {"--exec"}),
    "send-email": ("", {"--to-cmd", "--cc-cmd", "--header-cmd", "--sendmail-cmd", "--smtp-server"}),
    "mergetool": ("", {"--tool-cmd"}),
}
# Options of those subcommands whose (optional) value must be attached.
GIT_ATTACHED_ONLY = {"O", "--open-files-in-pager"}


def _option_values(args, short, longs):
    """Values of the given options (-Xval, -X val, --long=val, --long val)."""
    out = []
    j = 0
    while j < len(args):
        t = str(args[j])
        if t == "--":
            break
        if t.startswith("--"):
            name, eq, val = t.partition("=")
            if name in longs:
                if eq:
                    out.append(val)
                elif name not in GIT_ATTACHED_ONLY and j + 1 < len(args):
                    out.append(str(args[j + 1]))
                    j += 1
        elif t.startswith("-") and len(t) > 1:
            for k, ch in enumerate(t[1:], start=1):
                if ch in short:
                    val = t[k + 1 :]
                    if val:
                        out.append(val)
                    elif ch not in GIT_ATTACHED_ONLY and j + 1 < len(args):
                        out.append(str(args[j + 1]))
                        j += 1
                    break
        j += 1
    return out


def env_command_values(seg, core) -> list:
    """Values of command-valued environment variables (GIT_PAGER=..., export
    EDITOR=...) set by this simple command. LESSOPEN's `|` is dropped."""
    out = []
    words = list(seg[: max(len(seg) - len(core), 0)]) if core else list(seg)
    if core and os.path.basename(str(core[0])) in EXPORT_WORDS:
        words += list(core[1:])
    for tok in words:
        name, eq, val = str(tok).partition("=")
        if eq and name in CMD_ENV_VARS and val.strip():
            val = val.lstrip("|-").lstrip("|")
            out.append(val)
    return out


def _git_nested(core):
    """Shell text git itself runs: submodule foreach, rebase -x, bisect run,
    `!` aliases, command-valued -c settings and options that take a command
    (grep -O, difftool -x, filter-branch filters, --upload-pack, ...)."""
    parts = git_parts(core)
    if not parts:
        return []
    sub, args, _chdirs, configs = parts
    out = []
    spec = GIT_CMD_OPTIONS.get(str(sub))
    if spec:
        out.extend(v for v in _option_values(args, spec[0], spec[1]) if v.strip())
    for cfg in configs:
        key, _, val = str(cfg).partition("=")
        if GIT_EXEC_CONFIG_RE.match(key) and val:
            out.append(val[1:] if val.startswith("!") else val)
    if sub == "submodule" and "foreach" in args:
        rest = args[args.index("foreach") + 1 :]
        while rest and str(rest[0]).startswith("-"):
            rest = rest[1:]
        out.append(" ".join(str(t) for t in rest))
    elif sub == "rebase":
        for j, tok in enumerate(args):
            t = str(tok)
            if t in ("-x", "--exec") and j + 1 < len(args):
                out.append(str(args[j + 1]))
            elif t.startswith("--exec="):
                out.append(t.split("=", 1)[1])
            elif t.startswith("-") and not t.startswith("--") and "x" in t[1:]:
                rest = t[t.index("x") + 1 :]
                out.append(rest or (str(args[j + 1]) if j + 1 < len(args) else ""))
    elif sub == "bisect" and args and str(args[0]) == "run":
        out.append(_requote(args[1:]))
    elif sub == "config":
        vals = [a for a in args if not str(a).startswith("-")]
        if len(vals) >= 2 and GIT_EXEC_CONFIG_RE.match(str(vals[0])):
            val = str(vals[1])
            out.append(val[1:] if val.startswith("!") else val)
    return out


def _find_exec(core):
    """Commands run by find -exec/-execdir/-ok/-okdir."""
    out = []
    j = 1
    while j < len(core):
        if str(core[j]) in ("-exec", "-execdir", "-ok", "-okdir"):
            k = j + 1
            while k < len(core) and str(core[k]) not in (";", "+"):
                k += 1
            out.append(_requote(core[j + 1 : k]))
            j = k
        j += 1
    return out


_POSARG_RE = re.compile(r"\$\{([0-9])\}|\$([0-9])")


def _shell_c_args(core):
    """Words after the script of `bash -c SCRIPT arg0 arg1 ...` ($0, $1, ...)."""
    for j, tok in enumerate(core[1:], start=1):
        t = str(tok)
        if t == "--command" or (t.startswith("-") and not t.startswith("--") and "c" in t[1:]):
            return [str(a) for a in core[j + 2 :] if not is_redirect(str(a))]
        if t.startswith("--command="):
            return [str(a) for a in core[j + 1 :] if not is_redirect(str(a))]
    return []


def _with_positional(script, args):
    """The script with $0, $1, ... replaced by the words passed after it."""
    def repl(m):
        k = int(m.group(1) or m.group(2))
        if k >= len(args):
            return ""
        val = args[k]
        return val if re.match(r"^[A-Za-z0-9_./:=@%+,-]+$", val) else shlex.quote(val)

    return _POSARG_RE.sub(repl, script)


def _nested_sources(seg, core):
    """Shell text nested in a simple command."""
    nested = list(env_command_values(seg, core))
    if core:
        base = os.path.basename(str(core[0]))
        if base in SHELLS or _maybe_shell(core[0]):
            script = _shell_c_value(core)
            if script is not None:
                nested.append(script)
                args = _shell_c_args(core)
                if args and _POSARG_RE.search(script):
                    nested.append(_with_positional(script, args))
            for j, tok in enumerate(core[1:-1], start=1):
                if tok == "<<<":  # here-string fed to a shell runs as commands
                    nested.append(str(core[j + 1]))
        elif base in ("source", "."):
            toks = [str(t) for t in core]
            if len(toks) > 1 and toks[1] in ("/dev/stdin", "-", "/proc/self/fd/0", "/dev/fd/0") and "<<<" in toks[:-1]:
                nested.append(toks[toks.index("<<<") + 1])
        elif base == "eval":
            nested.append(" ".join(str(t) for t in core[1:]))
        elif base == "find":
            nested.extend(_find_exec(core))
        elif base == "git" or base.startswith("git-"):
            nested.extend(_git_nested(core))
    for tok in seg:
        if isinstance(tok, Word):
            nested.extend(tok.substs)
    return nested


# ---------------------------------------------------------------- text fed to a shell


def _literal_feed(src):
    """(text, dynamic) that a pipeline source writes, or None when unknown.

    echo/printf arguments, a here-string, or a here-document (whose body the
    here-document logic already walks; the text is then empty).
    """
    core = _unwrap(src)[0]
    if not core:
        return None
    base = os.path.basename(str(core[0]))
    toks = [str(t) for t in core]
    if "<<<" in toks[:-1]:
        word = core[toks.index("<<<") + 1]
        return str(word), is_dynamic(word)
    if any(t.startswith("<<") for t in toks):
        return "", False
    if base == "echo":
        args = list(core[1:])
        while args and re.match(r"^-[neE]+$", str(args[0])):
            args = args[1:]
        text = " ".join(str(a) for a in args)
    elif base == "printf":
        args = list(core[1:])
        if args and str(args[0]) == "--":
            args = args[1:]
        if args and str(args[0]) == "-v":
            return "", False
        if not args:
            return "", False
        fmt, rest = str(args[0]), [str(a) for a in args[1:]]
        text = re.sub(r"%[-#0 +]*[0-9]*(?:\.[0-9]+)?[sbdq]", lambda _m: rest.pop(0) if rest else "", fmt)
        if rest:
            text += "\n" + " ".join(rest)
    else:
        return None
    text = text.replace("\\n", "\n").replace("\\t", "\t")
    return text, any(is_dynamic(a) for a in core[1:])


def _maybe_shell(word) -> bool:
    """A computed command word ($SHELL, "$(which bash)") could be a shell."""
    return is_dynamic(word) and literal_tail(word) is None


def _stdin_shell(core, wrappers, piped):
    """What feeds this command code: 'stdin', 'procsub' or None."""
    if not core:
        return None
    base = os.path.basename(str(core[0]))
    args = core[1:]
    if base in ("source", "."):
        if args and (args[0].procsub if isinstance(args[0], Word) else False):
            return "procsub"
        if args and str(args[0]) in ("/dev/stdin", "-", "/proc/self/fd/0"):
            return "stdin" if piped else None
        return None
    if base not in SHELLS and not _maybe_shell(core[0]):
        return None
    if "xargs" in wrappers and piped:
        return "stdin"
    if _shell_c_value(core) is not None:
        return None
    j = 0
    while j < len(args):
        t = str(args[j])
        if isinstance(args[j], Word) and args[j].procsub:
            return "procsub"
        if t == "<" and j + 1 < len(args):
            if isinstance(args[j + 1], Word) and args[j + 1].procsub:
                return "procsub"
            return None  # bash < script.sh: a file (see README Limits)
        if t in ("-o", "+o", "-O", "+O", "--rcfile", "--init-file"):
            j += 2
            continue
        if t.startswith("-") or t.startswith("+"):
            j += 1
            continue
        if is_redirect(t):
            j += 2
            continue
        if t in ("/dev/stdin", "/proc/self/fd/0"):
            break
        return None  # bash script.sh
    return "stdin" if piped else None


def _procsub_feed(core):
    for tok in core[1:]:
        if isinstance(tok, Word) and tok.procsub and tok.substs:
            segs = _split_tokens(_tokenize_text(_prepass(tok.substs[0])))
            if len(segs) == 1:
                return _literal_feed(segs[0])
            return None
    return None


# ---------------------------------------------------------------- walking


def _walk(command: str, depth: int):
    """Yield events for every simple command in the text:

    ("seg", raw_tokens, info): info has core (wrappers stripped), env
        (same-line variables), wrappers, piped (stdin comes from a pipe) and
        feed ((text, dynamic) the pipe source writes, or None).
    ("body", kind, text): a here-document body that is not shell.
    ("opaque", kind, raw_tokens): a shell reads code the guard cannot see
        (`curl ... | sh`, `bash <(cat x)`, `echo "$X" | bash`).

    Assignments on the line are resolved and the resolved text is walked
    as well. Nested shell text is walked up to MAX_DEPTH levels.
    """
    resolved, env = _resolve(command, depth == 0)
    texts = [command] if resolved == command else [command, resolved]
    for text in texts:
        yield from _walk_text(text, depth, env)


def _walk_text(text: str, depth: int, env: dict):
    pre, bodies = _prepass_full(text)
    aliases: dict[str, str] = {}
    prev = None
    items = _split_with_ops(_tokenize_text(pre))
    case_depth = 0
    expect_pattern = False
    for idx, (seg, ops) in enumerate(items):
        core, wrapper_texts, wrappers = _unwrap(seg)
        # case WORD in PATTERN) ...;; PATTERN|PATTERN) ...;; esac
        next_ops = items[idx + 1][1] if idx + 1 < len(items) else []
        if case_depth and any(o in (";;", ";&", ";;&") for o in ops):
            expect_pattern = True
        if core and str(core[0]) == "case" and not is_dynamic(core[0]):
            case_depth += 1
            expect_pattern = True
        elif core and str(core[0]) == "esac" and case_depth:
            case_depth -= 1
            expect_pattern = False
        elif case_depth and expect_pattern and next_ops and next_ops[0] in (")", "|"):
            if next_ops[0] == ")":
                expect_pattern = False
            core, wrapper_texts, wrappers = [], [], []
        piped = any(o in ("|", "|&") for o in ops)
        feed = _literal_feed(prev) if piped and prev is not None else None
        info = {"core": core, "env": env, "wrappers": wrappers, "piped": piped, "feed": feed}
        yield ("seg", seg, info)
        prev = seg
        if depth >= MAX_DEPTH:
            continue
        texts = list(wrapper_texts)
        if core and os.path.basename(str(core[0])) == "alias":
            for arg in core[1:]:
                name, eq, val = str(arg).partition("=")
                if eq:
                    aliases[name] = val
                    texts.append(val)
        elif core and str(core[0]) in aliases:
            texts.append(aliases[str(core[0])] + " " + _requote(core[1:]))
        texts.extend(_nested_sources(seg, core))
        for inner in texts:
            yield from _walk(inner, depth + 1)
        if "xargs" in wrappers and core and feed is not None and feed[0].strip():
            yield from _walk_xargs(seg, core, feed[0], depth)
        fed = _stdin_shell(core, wrappers, piped)
        if fed:
            src = _procsub_feed(core) if fed == "procsub" else feed
            if src is not None:
                yield from _walk(src[0], depth + 1)
            if src is None or src[1]:
                yield ("opaque", fed, seg)
    for kind, body, quoted in bodies:
        if kind == "shell" and depth < MAX_DEPTH:
            yield from _walk(body, depth + 1)
            continue
        if not quoted and depth < MAX_DEPTH:
            # <<EOF (unquoted) runs $(...) and backticks in the body.
            masked = re.sub(r"\\[\\$`]", "\0\0", body)
            for a, b, _inner in _subst_spans(masked):
                inner = body[a:b]
                inner = inner[2:-1] if inner.startswith("$(") else inner[1:-1]
                if inner.strip():
                    yield from _walk(inner, depth + 1)
        yield ("body", kind, body)


def _xargs_replace(seg):
    """The -I / -i / --replace string of an xargs wrapper, else None."""
    for j, tok in enumerate(seg):
        t = str(tok)
        if t == "-I" and j + 1 < len(seg):
            return str(seg[j + 1])
        if t.startswith("-I") and len(t) > 2:
            return t[2:]
        if t == "-i" or t == "--replace":
            return "{}"
        if t.startswith("-i") and len(t) > 2 and "xargs" in [os.path.basename(str(x)) for x in seg[:j]]:
            return t[2:]
        if t.startswith("--replace="):
            return t.split("=", 1)[1] or "{}"
    return None


def _walk_xargs(seg, core, feed_text, depth):
    """`echo merge 1 | xargs gh pr`: walk the command with the literal input
    put where xargs puts it (appended, or in place of the -I string)."""
    repl = _xargs_replace(seg)
    lines = [ln for ln in feed_text.splitlines() if ln.strip()][:16]
    for line in lines:
        if repl:
            toks = [sub_word(t, str(t).replace(repl, line)) if repl in str(t) else t for t in core]
            text = _requote(toks)
        else:
            text = _requote(core) + " " + line
        yield from _walk(text, depth + 1)


def split_commands(command: str) -> list[list[str]]:
    """Every simple command in the text, wrappers stripped, nested shells included.

    Each item is the token list of one command, starting at the command word.
    """
    return [event[2]["core"] for event in _walk(command, 0) if event[0] == "seg" and event[2]["core"]]


def command_infos(command: str) -> list[dict]:
    """Like split_commands, with the raw segment and its info (see _walk)."""
    out = []
    for event in _walk(command, 0):
        if event[0] == "seg":
            info = dict(event[2])
            info["raw"] = event[1]
            out.append(info)
    return out


def raw_segments(command: str) -> list[list[str]]:
    """Segments with wrappers kept (for path scanning). Nested shells included."""
    return [event[1] for event in _walk(command, 0) if event[0] == "seg"]


def code_bodies(command: str) -> list[str]:
    """Bodies of here-documents read by an interpreter (python <<X, node <<X)."""
    return [event[2] for event in _walk(command, 0) if event[0] == "body" and event[1] == "code"]


def opaque_feeds(command: str) -> list[tuple[str, list]]:
    """(kind, raw segment) for each shell that reads code the guard cannot see."""
    return [(event[1], event[2]) for event in _walk(command, 0) if event[0] == "opaque"]


def is_redirect(tok: str) -> bool:
    return bool(REDIRECT_RE.match(tok))


# ---------------------------------------------------------------- dynamic command words

SUSPECT_RE = re.compile(r"\bwhich\b|\bcommand\s+-[vV]\b|\btype\s+-[aPpt]|\bwhereis\b|\bhash\b|\bcompgen\b")
TOOL_WORD_RE = re.compile(r"(?<![\w.-])(git|gh|sops|r?age)(?![\w-])")


def could_be_tool(word, env: dict) -> bool:
    """True when a computed word could turn into git, gh, sops or age:
    it looks a program up (which, command -v, ...), names one of them, uses
    a variable assigned to one of them on this line, or is a glob/brace
    pattern that matches one of them."""
    text = str(word)
    if SUSPECT_RE.search(text) or TOOL_WORD_RE.search(text):
        return True
    for m in re.finditer(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)", text):
        val = env.get(m.group(1))
        if val is None:
            continue
        val = val[0] if isinstance(val, tuple) else val
        if SUSPECT_RE.search(val) or TOOL_WORD_RE.search(val):
            return True
        if has_glob(val) and any(fnmatch.fnmatchcase(t, os.path.basename(v)) for v in val.split() for t in TOOLS):
            return True
    if isinstance(word, Word) and word.globs and not word.expands:
        for alt in brace_expand(text):
            if any(fnmatch.fnmatchcase(t, os.path.basename(alt)) for t in TOOLS):
                return True
    return False


def command_word(cmd):
    """(name, dynamic) for the command word of a stripped command.

    name is the basename the shell will run when it is known (also for
    `$(...)/tools/x`, whose file name is literal); dynamic is True when the
    word is computed and its name cannot be known.
    """
    if not cmd:
        return "", False
    word = cmd[0]
    if not is_dynamic(word):
        return os.path.basename(str(word)), False
    tail = literal_tail(word)
    if tail is not None:
        return tail, False
    return None, True


# ---------------------------------------------------------------- lanes


def lane_paths(cmds_or_infos, cwd, project):
    """Paths a command moves into: cd/pushd targets, git -C/--git-dir/
    --work-tree values and GIT_DIR=/GIT_WORK_TREE= assignments."""
    paths = []
    for item in cmds_or_infos:
        cmd = item["core"] if isinstance(item, dict) else item
        raw = item.get("raw", cmd) if isinstance(item, dict) else cmd
        for tok in raw:
            m = re.match(r"^(GIT_DIR|GIT_WORK_TREE)=(.+)$", str(tok))
            if m:
                paths.append(expand_path(m.group(2), cwd, project))
        if not cmd:
            continue
        base = os.path.basename(str(cmd[0]))
        if base in ("cd", "pushd"):
            args = [a for a in cmd[1:] if not str(a).startswith("-")]
            if args:
                paths.append(expand_path(str(args[0]), cwd, project))
        parts = git_parts(cmd)
        if parts:
            for c in parts[2]:
                paths.append(expand_path(str(c), cwd, project))
    return paths


def is_lane(payload, infos, cwd, project) -> bool:
    """A lane call: a subagent, a cwd inside .tmp-session/wt/, or a command
    that moves into it."""
    if is_subagent(payload):
        return True
    wt = wt_root(project)
    if is_under(cwd, wt):
        return True
    return any(is_under(p, wt) for p in lane_paths(infos, cwd, project))


# ---------------------------------------------------------------- git / gh


GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}


def git_parts(cmd: list):
    """For a git command return (subcommand, args, chdirs, configs); else None.

    chdirs are the -C, --git-dir and --work-tree values; configs are the -c
    and --config-env values (key=value). `git-push` style binaries (also
    /usr/lib/git-core/git-push) count as `git push`.
    """
    if not cmd:
        return None
    base = os.path.basename(str(cmd[0]))
    if base.startswith("git-") and len(base) > 4:
        return (base[4:], list(cmd[1:]), [], [])
    if base != "git":
        return None
    i = 1
    chdirs: list = []
    configs: list = []
    while i < len(cmd) and str(cmd[i]).startswith("-"):
        tok = str(cmd[i])
        if tok in GIT_OPTS_WITH_VALUE and i + 1 < len(cmd):
            if tok in ("-C", "--git-dir", "--work-tree"):
                chdirs.append(cmd[i + 1])
            elif tok in ("-c", "--config-env"):
                configs.append(cmd[i + 1])
            i += 2
            continue
        if tok.startswith("--git-dir=") or tok.startswith("--work-tree="):
            chdirs.append(sub_word(cmd[i], tok.split("=", 1)[1]))
        elif tok.startswith("--config-env="):
            configs.append(sub_word(cmd[i], tok.split("=", 1)[1]))
        elif tok.startswith("-c") and len(tok) > 2:
            configs.append(sub_word(cmd[i], tok[2:]))
        i += 1
    if i >= len(cmd):
        return ("", [], chdirs, configs)
    return (cmd[i], list(cmd[i + 1 :]), chdirs, configs)


def git_global_words(cmd: list) -> list:
    """The global-option words of a git command (before the subcommand)."""
    out = []
    i = 1
    while i < len(cmd) and str(cmd[i]).startswith("-"):
        out.append(cmd[i])
        if str(cmd[i]) in GIT_OPTS_WITH_VALUE and i + 1 < len(cmd):
            out.append(cmd[i + 1])
            i += 1
        i += 1
    return out


def long_opt(tok: str, full: str) -> bool:
    """True when tok is the long option `full` or an abbreviation git accepts.

    git takes any unique prefix of a long option (`git reset --h` is
    `--hard`, `git clean --f` is `--force`), so every prefix of at least
    one letter counts. An `=value` tail is ignored.
    """
    tok = str(tok)
    if not tok.startswith("--"):
        return False
    name = tok.split("=", 1)[0]
    return len(name) >= 3 and full.startswith(name)


GH_GLOBAL_WITH_VALUE = {"-R", "--repo", "--hostname"}


def gh_parts(cmd: list):
    """For a gh command return (group, sub, args); else None.

    `gh pr merge 3` -> ("pr", "merge", ["3"]); `gh api x` -> ("api", None, ["x"]).
    """
    if not cmd or os.path.basename(str(cmd[0])) != "gh":
        return None
    i = 1
    while i < len(cmd) and str(cmd[i]).startswith("-"):
        i += 2 if str(cmd[i]) in GH_GLOBAL_WITH_VALUE else 1
    if i >= len(cmd):
        return ("", None, [])
    group = cmd[i]
    rest = list(cmd[i + 1 :])
    if group in ("api", "search", "help", "version", "status", "browse", "completion"):
        return (group, None, rest)
    j = 0
    while j < len(rest) and str(rest[j]).startswith("-"):
        j += 2 if str(rest[j]) in GH_GLOBAL_WITH_VALUE else 1
    if j >= len(rest):
        return (group, None, rest)
    return (group, rest[j], rest[:j] + rest[j + 1 :])


# gh api flags: short letters that take a value, and those that do not.
GH_API_SHORT_VALUE = set("XHfFqtp")
GH_API_LONG_VALUE = {"--header", "--jq", "--template", "--hostname", "--preview", "--cache", "--method",
                     "--field", "--raw-field", "--input"}


def gh_api_request(args: list) -> dict:
    """Parse `gh api` arguments into {endpoint, method, fields, input}.

    Understands -X PUT, -XPUT, -X=PUT, combined short flags (-iXPUT,
    -iX PUT), --method PUT and --method=PUT. Values keep their Word flags,
    so callers can tell a literal from a shell expansion.
    """
    out = {"endpoint": None, "method": None, "fields": [], "input": None}

    def take(flag, value):
        if flag in ("X", "--method"):
            out["method"] = value
        elif flag in ("f", "F", "--field", "--raw-field"):
            out["fields"].append(value)
        elif flag == "--input":
            out["input"] = value

    i = 0
    n = len(args)
    while i < n:
        tok = args[i]
        t = str(tok)
        nxt = args[i + 1] if i + 1 < n else ""
        if t == "--":
            if out["endpoint"] is None and i + 1 < n:
                out["endpoint"] = args[i + 1]
            break
        if t.startswith("--"):
            name, eq, val = t.partition("=")
            if name in GH_API_LONG_VALUE:
                take(name, sub_word(tok, val) if eq else nxt)
                i += 1 if eq else 2
                continue
            i += 1
            continue
        if t.startswith("-") and len(t) > 1:
            letters = t[1:]
            step = 1
            for k, ch in enumerate(letters):
                if ch in GH_API_SHORT_VALUE:
                    val = letters[k + 1 :]
                    if val.startswith("=") and ch == "X":
                        val = val[1:]
                    if val:
                        take(ch, sub_word(tok, val))
                    else:
                        take(ch, nxt)
                        step = 2
                    break
            i += step
            continue
        if out["endpoint"] is None:
            out["endpoint"] = tok
        i += 1
    if out["method"] is not None:
        method = out["method"]
        upper = sub_word(method, str(method).upper()) if isinstance(method, Word) else str(method).upper()
        out["method"] = upper
    return out


def normalize_endpoint(endpoint: str) -> str:
    """Endpoint path as GitHub routes it: no scheme/host, query, fragment,
    percent-encoding, doubled slashes or dot segments."""
    ep = str(endpoint or "")
    ep = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://[^/]*", "", ep)
    ep = ep.split("?", 1)[0].split("#", 1)[0]
    ep = unquote(ep)
    ep = re.sub(r"/{2,}", "/", ep)
    if ep:
        ep = posixpath.normpath("/" + ep)
    ep = ep.strip("/")
    return re.sub(r"^api/v3/", "", ep)
