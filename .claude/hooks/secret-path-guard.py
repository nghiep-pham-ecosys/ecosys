#!/usr/bin/env python3
"""secret-path-guard: PreToolUse hook for Read, Edit, Write and Bash (spec §9.7).

Blocks access to:
- .env and .env.* files (.env.example is allowed);
- *.pem and *.key files;
- anything under ~/.config/sops/ (the age key lives there);
- the local denylist ~/.config/nghiep-pham-ecosys/denylist.txt (also the
  folder itself and globs inside it);
- decryption: sops -d / --decrypt / decrypt / exec-env / exec-file / edit,
  a bare `sops <file>` (opens a decrypted copy), age -d / --decrypt.

Paths are normalised the way the kernel resolves them: a leading `//`,
/proc/<pid>/root and /proc/<pid>/cwd prefixes, `~+`, and existing
symlinks (real path) are all followed. A relative path is checked against
the payload cwd and every literal `cd`/`pushd` target earlier on the
line (`cd ~/.config && cat sops/age/keys.txt`), and `ln -s` links made
earlier on the line are followed.

Globs and simple {a,b} braces count in every path component
(`cat ~/.config/nghiep-*/denylist.txt` is caught). A glob in a file name
counts as a key or .env name when it can match one (`server.ke?`,
`*.pe[m]`, `*.k*`, `*env`) and is not so broad that it also matches
ordinary names (`*`, `*.*`, `README.*`). find -name/-iname patterns and
the Grep tool's glob (brace-expanded) are checked the same way.

Recursive readers aimed at ~/.config/sops, the denylist folder or a
folder above them are blocked: grep -r, rg, ag, ack, find ... -exec,
tar c, cp -r, rsync, zip -r, and the Grep tool with such a path.

Path-like text inside code is scanned too: a token that looks like code
(quotes or parentheses, as in `python3 -c "open('...')"`) and mentions
`/.config/` or `.env`, and the body of a here-document read by an
interpreter (`python3 <<X`). Text words (a git commit/tag message, a gh
--body, a grep pattern, a sed or awk script) and the arguments of
programs that only look at names (test, ls, stat, git check-ignore) are
checked for the protected folders only, not for .env/key names.

Reading an encrypted *.sops.* file is allowed: it is ciphertext
(`.env.sops.yaml` too).

Computed words: a command whose name is computed by the shell and that
carries a decrypt flag (`$S -d f`) is blocked, and so is `age` with an
argument computed by the shell in option position (it could be -d)
unless a literal encrypt flag (-e, -r, -R, -p) is present. `xargs cat`
and other readers fed by a pipe have their file names checked when the
source is literal (echo/printf); in a lane, a source the guard cannot
read is blocked.

The denylist path may appear only in a command whose program is the
project's denylist scanner: its real path must equal the real path of
$CLAUDE_PROJECT_DIR/tools/ws/denylist-scan (run directly or as
`python3 <that path>`), CLAUDE_PROJECT_DIR must be set, and the scanner
must be a file inside the project. `just denylist` / `just ci` stay
exempt.

The hook never opens any of these files. It only compares paths.
It also understands Grep, Glob and NotebookEdit inputs, so the matcher can
be widened later without changing this file.
"""

from __future__ import annotations

import fnmatch
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _guardlib as g  # noqa: E402

NAME = "secret-path-guard"
ENV_ALLOWED = {".env.example"}
DENYLIST_REL = os.path.join(".config", "nghiep-pham-ecosys", "denylist.txt")
SOPS_REL = os.path.join(".config", "sops")
PIECE_SPLIT_RE = re.compile(r"[=:,]")

SOPS_DECRYPT = {"-d", "--decrypt", "decrypt", "exec-env", "exec-file", "edit", "--extract"}
SOPS_SAFE = {"-e", "--encrypt", "encrypt", "-v", "--version", "version", "-h", "--help", "help",
             "updatekeys", "rotate", "-r", "--rotate", "filestatus", "keyservice", "publish"}
AGE_DECRYPT = {"-d", "--decrypt"}
AGE_ENCRYPT = {"-e", "--encrypt", "-r", "-R", "-p", "--passphrase", "-a", "--armor"}
AGE_VALUE_SHORT = "rRio"
XARGS_READERS = {"cat", "tac", "nl", "less", "more", "head", "tail", "strings", "xxd", "od", "hexdump", "base64",
                 "bat", "batcat", "cp", "mv", "scp", "rsync", "source", ".", "tar", "zip"}
ECHO_LIKE = {"echo", "printf"}
CODE_TRIGGERS = ("/.config/", ".env")
CODE_CHARS = set("'\"()")
PATHLIKE_RE = re.compile(r"[A-Za-z0-9_.~$/{}*?\[\]@%+-]+")
MESSAGE_OPTS = {"-m", "--message", "-b", "--body", "-t", "--title", "--subject", "--notes"}
# Commands whose MESSAGE_OPTS values are text, never a file name.
MESSAGE_GIT_SUBS = {"commit", "tag", "notes", "stash", "merge", "revert", "cherry-pick"}
SOPS_FILE_RE = re.compile(r"\.sops(\.[a-z0-9]+)?$")
SCANNER_REL = os.path.join("tools", "ws", "denylist-scan")
# grep-like programs: short options that take a value (the pattern is not a file name).
PATTERN_PROGS = {
    "grep": "ABCDdefm", "egrep": "ABCDdefm", "fgrep": "ABCDdefm", "rgrep": "ABCDdefm", "zgrep": "ABCDdefm",
    "rg": "ABCEefgjMmrTt", "ag": "ABCGgm", "ack": "ABCgm", "git-grep": "ABCefm",
    "sed": "efl", "awk": "fvF", "gawk": "fvF", "mawk": "fvF",
}
PATTERN_FILE_OPTS = {"-f", "--file", "--regexp-file"}
GREP_RECURSIVE_LONG = {"--recursive", "--dereference-recursive", "--directories=recurse", "--recurse"}
FIND_RUNNERS = {"-exec", "-execdir", "-ok", "-okdir"}
# Programs that only look at names or metadata, never at file contents:
# a .env or key name next to them is not a read (folders still count).
NAME_ONLY = {"test", "[", "[[", "ls", "stat", "realpath", "readlink", "basename", "dirname"}
NAME_ONLY_GIT = {"check-ignore", "ls-files"}


def _name_glob_hits(glob, names, neutral):
    """True when the glob `glob` can match one of the protected `names`
    (fnmatch, a `*` also matches a leading dot, as find and rg do) and is not
    so broad that it also matches the ordinary `neutral` names."""
    if any(fnmatch.fnmatchcase(n, glob) for n in neutral):
        return False
    return any(fnmatch.fnmatchcase(n, glob) for n in names)


def _glob_key_names(glob):
    """Key-like names a glob could match: <stem>.pem / <stem>.key for the
    literal stems the glob starts with (`server.ke?` -> server.key)."""
    stems = {"x", "server", "id", "tls", "private"}
    # A literal stem counts when the extension part does not start with `*`
    # (`deploy.k*` yes; `fix.*key`, a regex idiom, no).
    m = re.match(r"^([A-Za-z0-9_-]+)\.(?!\*)", glob)
    if m:
        stems.add(m.group(1))
    return [s + ext for s in stems for ext in (".pem", ".key")]


ENV_NEUTRAL = ("a", "a.txt", "zzq", "README.md")
KEY_NEUTRAL = ("a", "a.txt", "zzq", "a.zzq", "README.md")


def _env_name(base):
    low = base.lower()
    if low in ENV_ALLOWED or SOPS_FILE_RE.search(low):
        return False
    if low == ".env" or low.startswith(".env."):
        return True
    if g.has_glob(low):
        return _name_glob_hits(low, (".env", ".env.local", ".env.production"), ENV_NEUTRAL)
    return False


def _key_name(base):
    low = base.lower()
    if low.endswith(".pem") or low.endswith(".key"):
        return True
    if g.has_glob(low):
        if re.search(r"\.\*$", low):  # name.* : the extension is fully open
            return False
        return _name_glob_hits(low, _glob_key_names(low), KEY_NEUTRAL)
    return False


_glob_reaches = g.glob_reaches


_brace_expand = g.brace_expand


def _protected_dirs(home):
    denylist = os.path.normpath(os.path.join(home, DENYLIST_REL))
    return denylist, os.path.dirname(denylist), os.path.normpath(os.path.join(home, SOPS_REL))


def _classify_one(path, home, names):
    denylist, deny_dir, sops_dir = _protected_dirs(home)
    base = os.path.basename(path.rstrip(os.sep))
    globbed = g.has_glob(path)
    if path == denylist or path == deny_dir or (globbed and _glob_reaches(path, deny_dir)):
        return "denylist", "the local denylist is never read by agents; use tools/ws/denylist-scan"
    if g.is_under(path, sops_dir) or (globbed and _glob_reaches(path, sops_dir)):
        return "sops", "~/.config/sops/ holds the age key; agents never read it"
    if not names:
        return None, None
    if _env_name(base):
        return "env", f"{base} may hold secrets; only .env.example is readable"
    if _key_name(base):
        return "key", f"{base} looks like a private key or certificate"
    return None, None


def _homes(home):
    out = [home]
    real = os.path.realpath(home)
    if real != home:
        out.append(real)
    return out


def _variants(path):
    """The path and its real path (symlinks that already exist resolved)."""
    out = [path]
    if not g.has_glob(path):
        try:
            real = os.path.realpath(path)
        except (OSError, ValueError):
            real = path
        if real != path:
            out.append(real)
    return out


def classify(path, home, names=True, links=()):
    """Return (kind, reason) for a secret path, else (None, None). path is absolute.

    names=False checks only the protected folders (for a grep pattern or a
    sed script, which are not file names). links are (link, target) pairs
    made with `ln -s` earlier on the same line.
    """
    for alias in g.path_aliases(path, links):
        for variant in _variants(alias):
            for h in _homes(home):
                kind, reason = _classify_one(variant, h, names)
                if kind:
                    return kind, reason
    return None, None


def reaches_protected_dir(path, home, links=()):
    """True when path is ~/.config/sops, the denylist folder, or a folder
    above either (a recursive reader started there reads them)."""
    for alias in g.path_aliases(path, links):
        for variant in _variants(alias):
            for h in _homes(home):
                _denylist, deny_dir, sops_dir = _protected_dirs(h)
                if g.glob_ancestor(variant, sops_dir) or g.glob_ancestor(variant, deny_dir):
                    return True
    return False


def _check_file_tool(payload, project, home):
    ti = payload.get("tool_input") or {}
    cwd = g.payload_cwd(payload)
    tool = payload.get("tool_name")
    for field in ("file_path", "notebook_path", "path"):
        val = ti.get(field)
        if isinstance(val, str) and val:
            kind, reason = classify(g.expand_path(val, cwd, project, home), home)
            if kind:
                return reason
    if tool != "Grep":
        return None
    # Grep reads file contents: below a folder above the protected ones it
    # reaches them, and its file glob counts. Glob only lists names.
    root = ti.get("path") if isinstance(ti.get("path"), str) and ti.get("path") else cwd
    root_abs = g.expand_path(root, cwd, project, home)
    if reaches_protected_dir(root_abs, home):
        return (f"Grep over {root_abs} reaches ~/.config/sops/ or the local denylist; "
                "search a narrower folder")
    pattern = ti.get("glob")
    if isinstance(pattern, str) and pattern:
        for alt in _brace_expand(pattern.lstrip("!")):
            for cand in (alt, os.path.basename(alt)):
                kind, reason = classify(g.expand_path(os.path.join(root, cand), cwd, project, home), home)
                if kind:
                    return reason
    return None


def _code_pieces(text):
    """Path-like substrings of code that mention a trigger (/.config/ or .env)."""
    for piece in PATHLIKE_RE.findall(text):
        if not any(t in piece for t in CODE_TRIGGERS):
            continue
        yield piece
        k = piece.find("/.config/")
        if k >= 0:
            # os.environ["HOME"] + "/.config/..." and similar: also try it home-relative.
            yield "~" + piece[k:]


def _is_message_value(seg, idx):
    tok = seg[idx]
    if any(tok.startswith(opt + "=") for opt in MESSAGE_OPTS if opt.startswith("--")):
        return True
    return idx > 0 and seg[idx - 1] in MESSAGE_OPTS


def _prog(cmd):
    """Program name of a stripped command; `git grep` counts as git-grep."""
    if not cmd:
        return ""
    base = os.path.basename(str(cmd[0]))
    if base == "git":
        parts = g.git_parts(cmd)
        if parts and str(parts[0]) == "grep":
            return "git-grep"
    return base


def _text_indexes(cmd):
    """Indexes (in cmd) of words that are text, not file names: message
    values of git commit/tag/... and gh, and the pattern or script of
    grep-like programs, sed and awk."""
    out = set()
    if not cmd:
        return out
    base = os.path.basename(str(cmd[0]))
    parts = g.git_parts(cmd) if base == "git" else None
    if base in NAME_ONLY or (parts and str(parts[0]) in NAME_ONLY_GIT):
        return set(range(1, len(cmd)))
    if base == "gh" or (parts and str(parts[0]) in MESSAGE_GIT_SUBS):
        for k in range(1, len(cmd)):
            if str(cmd[k - 1]) in MESSAGE_OPTS:
                out.add(k)
    prog = _prog(cmd)
    value_short = PATTERN_PROGS.get(prog)
    if value_short is None:
        return out
    start = 1
    if prog == "git-grep":
        start = next((k for k in range(1, len(cmd)) if str(cmd[k]) == "grep"), len(cmd) - 1) + 1
    explicit = False
    first_pos = None
    k = start
    while k < len(cmd):
        t = str(cmd[k])
        if t == "--":
            if first_pos is None and k + 1 < len(cmd):
                first_pos = k + 1
            break
        if t.startswith("--"):
            name = t.split("=", 1)[0]
            if name in ("--regexp", "--expression"):
                explicit = True
                if "=" not in t and k + 1 < len(cmd):
                    out.add(k + 1)
                    k += 1
                else:
                    out.add(k)
            elif name in PATTERN_FILE_OPTS:
                explicit = True
                k += 0 if "=" in t else 1
            k += 1
            continue
        if t.startswith("-") and len(t) > 1 and not g.is_redirect(t):
            for j, ch in enumerate(t[1:], start=1):
                if ch in value_short:
                    attached = t[j + 1 :]
                    if ch == "e" or (prog in ("awk", "gawk", "mawk") and ch == "v"):
                        explicit = explicit or ch == "e"
                        if attached:
                            out.add(k)
                        elif k + 1 < len(cmd):
                            out.add(k + 1)
                    elif ch == "f":
                        explicit = True
                    if not attached:
                        k += 1
                    break
            k += 1
            continue
        if g.is_redirect(t):
            k += 2
            continue
        if first_pos is None:
            first_pos = k
        k += 1
    if not explicit and first_pos is not None:
        out.add(first_pos)
    return out


def _candidates(seg, cmd=None):
    """(path-like string, names) for one raw segment. names is False for
    words that are text (a message, a grep pattern, a sed script): only
    the protected folders count there, not .env/key names."""
    cmd = g.strip_wrappers(seg) if cmd is None else cmd
    echo_like = bool(cmd) and os.path.basename(str(cmd[0])) in ECHO_LIKE
    offset = len(seg) - len(cmd) if cmd else len(seg)
    text_idx = {k + offset for k in _text_indexes(cmd)}
    for idx, tok in enumerate(seg):
        if echo_like:
            # echo/printf arguments are text, not files; only redirect targets count.
            if idx == 0 or not g.is_redirect(seg[idx - 1]):
                continue
        if g.is_redirect(tok):
            continue
        names = idx not in text_idx
        pieces = {tok}
        pieces.update(p for p in PIECE_SPLIT_RE.split(tok) if p)
        if (
            any(t in tok for t in CODE_TRIGGERS)
            and CODE_CHARS & set(tok)
            and not _is_message_value(seg, idx)
        ):
            pieces.update(_code_pieces(tok))
        for p in pieces:
            p = p.lstrip("@")
            if p:
                for cand in _brace_expand(p):
                    yield cand, names


def _scanner_path(project):
    """Real path of <project>/tools/ws/denylist-scan, when the project comes
    from CLAUDE_PROJECT_DIR and the scanner is a file inside it; else None."""
    if not os.environ.get("CLAUDE_PROJECT_DIR"):
        return None
    real_project = os.path.realpath(project)
    real = os.path.realpath(os.path.join(project, SCANNER_REL))
    if not os.path.isfile(real) or not g.is_under(real, real_project):
        return None
    return real


def _denylist_exempt(cmd, cwds, project, home):
    """The program is the project's denylist scanner (or `just denylist|ci`)."""
    if not cmd:
        return False
    base = os.path.basename(str(cmd[0]))
    if base == "just" and len(cmd) > 1 and str(cmd[1]) in ("denylist", "ci") and not g.is_dynamic(cmd[1]):
        return True
    scanner = _scanner_path(project)
    if scanner is None:
        return False
    word = cmd[0]
    if re.match(r"^python[0-9.]*$", base) and not g.is_dynamic(cmd[0]):
        rest = [t for t in cmd[1:] if not g.is_redirect(str(t))]
        while rest and str(rest[0]) in ("-u", "-B", "-E", "-I", "-s", "-S", "-q", "-O", "-OO"):
            rest = rest[1:]
        if not rest or str(rest[0]).startswith("-"):
            return False
        word = rest[0]
    if not g._literal_path_word(word) or (isinstance(word, g.Word) and word.globs):
        return False
    return all(os.path.realpath(g.expand_path(str(word), c, project, home)) == scanner for c in cwds)


def _short_letters(tok):
    t = str(tok)
    if t.startswith("-") and not t.startswith("--") and len(t) > 1:
        return t[1:]
    return ""


def _recursive_roots(cmd):
    """Folders a recursive reader starts from (words, `.` when implied), or None."""
    if not cmd:
        return None
    prog = _prog(cmd)
    args = g._plain_args(cmd)
    words = [str(a) for a in args]
    if prog in ("grep", "egrep", "fgrep", "zgrep", "rgrep"):
        recursive = prog == "rgrep"
        for k, t in enumerate(words):
            if t == "--":
                break
            if t in GREP_RECURSIVE_LONG or (t in ("-d", "--directories") and k + 1 < len(words)
                                            and words[k + 1] == "recurse"):
                recursive = True
            letters = _short_letters(t)
            for ch in letters:
                if ch in "rR":
                    recursive = True
                if ch in PATTERN_PROGS["grep"]:
                    break
        if not recursive:
            return None
    elif prog not in ("rg", "ag", "ack"):
        if prog == "find":
            if not any(w in FIND_RUNNERS for w in words):
                return None
            roots = []
            for w in words:
                if w.startswith("-") and w not in ("-H", "-L", "-P"):
                    break
                if w in ("(", "!", ","):
                    break
                if w not in ("-H", "-L", "-P"):
                    roots.append(w)
            return roots or ["."]
        if prog in ("tar", "bsdtar"):
            first = words[0] if words else ""
            if not ("--create" in words or "c" in _short_letters(first) or
                    (first and not first.startswith("-") and "c" in first) or
                    any("c" in _short_letters(w) for w in words)):
                return None
            return [w for w in words[1:] if not w.startswith("-")]
        if prog in ("cp", "scp"):
            if not any(w in ("--recursive", "--archive") or set(_short_letters(w)) & set("rRa") for w in words):
                return None
            pos = [w for w in words if not w.startswith("-")]
            return pos[:-1]
        if prog == "rsync":
            pos = [w for w in words if not w.startswith("-")]
            return pos[:-1]
        if prog == "zip":
            if not any(w == "--recurse-paths" or "r" in _short_letters(w) for w in words):
                return None
            pos = [w for w in words if not w.startswith("-")]
            return pos[1:]
        return None
    # grep -r / rg / ag / ack: positionals after the pattern; none means `.`.
    text_idx = _text_indexes(cmd)
    value_short = PATTERN_PROGS.get(prog, "")
    roots = []
    k = 1
    while k < len(cmd):
        t = str(cmd[k])
        if g.is_redirect(t):
            k += 2
            continue
        if t.startswith("-") and len(t) > 1 and t != "--":
            letters = _short_letters(t)
            for j, ch in enumerate(letters):
                if ch in value_short:
                    if j == len(letters) - 1:
                        k += 1
                    break
            if t.split("=", 1)[0] in PATTERN_FILE_OPTS | {"--regexp", "--expression", "--glob", "--type",
                                                         "--max-count", "--context"} and "=" not in t:
                k += 1
            k += 1
            continue
        if t != "--" and k not in text_idx:
            roots.append(t)
        k += 1
    return roots or ["."]


def _recursive_reason(cmd, cwds, project, home, links):
    roots = _recursive_roots(cmd)
    if not roots:
        return None
    for root in roots:
        if g.is_dynamic(root) and not g._literal_path_word(root):
            continue
        for cand in _brace_expand(str(root)):
            for c in cwds:
                path = g.expand_path(cand, c, project, home)
                if reaches_protected_dir(path, home, links):
                    return (f"`{_prog(cmd)}` reads {path} recursively, which reaches ~/.config/sops/ or the "
                            "local denylist; aim it at a narrower folder")
    return None


def _decrypt_reason(cmd):
    name, dynamic = g.command_word(cmd)
    args = [str(a) for a in cmd[1:]]
    if dynamic:
        if any(a in SOPS_DECRYPT or a in AGE_DECRYPT for a in args):
            return (f"the command name {cmd[0]} is computed by the shell and has a decrypt flag "
                    "(it could be sops/age); blocked")
        return None
    if name == "sops":
        if any(a in SOPS_DECRYPT for a in args):
            return "sops decryption is blocked; agents never see plaintext secrets"
        if not any(a in SOPS_SAFE for a in args) and any(not a.startswith("-") for a in args):
            return "a bare `sops <file>` opens a decrypted copy; blocked"
    if name in ("age", "rage"):
        if any(a in AGE_DECRYPT or (a.startswith("-") and not a.startswith("--") and "d" in a[1:]) for a in args):
            return "age decryption is blocked; agents never see plaintext secrets"
        encrypting = any(a in AGE_ENCRYPT or a.startswith("--recipient") for a in args)
        if not encrypting and _computed_option(cmd[1:], AGE_VALUE_SHORT):
            return "age with an argument computed by the shell could decrypt (-d); blocked"
    return None


def _computed_option(args, value_short):
    """A word computed by the shell in option position (not a value of -r/-i/-o)."""
    skip_next = False
    for tok in args:
        if skip_next:
            skip_next = False
            continue
        t = str(tok)
        if t == "--":
            return False
        if g.is_dynamic(tok) and not (isinstance(tok, g.Word) and tok.ph.startswith("-")):
            return True
        if t.startswith("-") and not t.startswith("--") and len(t) == 2 and t[1] in value_short:
            skip_next = True
        elif t in ("--recipient", "--recipients-file", "--identity", "--output"):
            skip_next = True
    return False


def _xargs_reader_reason(info, home, cwds, project, lane, links):
    """`... | xargs cat`: the file names come from the pipe."""
    cmd = info["core"]
    if not cmd or "xargs" not in info["wrappers"] or os.path.basename(str(cmd[0])) not in XARGS_READERS:
        return None
    feed = info["feed"]
    if feed is not None:
        for word in feed[0].split():
            for cand in g.brace_expand(word):
                for c in cwds:
                    kind, reason = classify(g.expand_path(cand, c, project, home), home, links=links)
                    if kind:
                        return reason
    if lane and (feed is None or feed[1]):
        return (f"lanes may not feed file names the guard cannot see into `xargs {cmd[0]}`; "
                "name the files directly")
    return None


def _check_bash(payload, project, home):
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command.strip():
        return None
    cwd = g.payload_cwd(payload)
    infos = g.command_infos(command)
    lane = g.is_lane(payload, infos, cwd, project)
    cwds = g.track_cwds(infos, cwd, project, home)
    links = g.line_symlinks(infos, cwds, project, home)
    for info, folders in zip(infos, cwds):
        if info["core"]:
            reason = (_decrypt_reason(info["core"])
                      or _xargs_reader_reason(info, home, folders, project, lane, links)
                      or _recursive_reason(info["core"], folders, project, home, links))
            if reason:
                return reason
    for info, folders in zip(infos, cwds):
        seg = info["raw"]
        exempt = _denylist_exempt(info["core"], folders, project, home)
        for cand, names in _candidates(seg, info["core"]):
            for c in folders:
                kind, reason = classify(g.expand_path(cand, c, project, home), home, names, links)
                if kind == "denylist" and exempt:
                    continue
                if kind:
                    return reason
    every = []
    for folders in cwds:
        every.extend(f for f in folders if f not in every)
    for body in g.code_bodies(command):
        for piece in _code_pieces(body):
            for cand in _brace_expand(piece):
                for c in every or [cwd]:
                    kind, reason = classify(g.expand_path(cand, c, project, home), home, links=links)
                    if kind:
                        return reason
    return None


def check(payload):
    tool = payload.get("tool_name")
    project = g.project_dir(payload)
    home = g.home_dir()
    if tool == "Bash":
        return _check_bash(payload, project, home)
    if tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep", "Glob"):
        return _check_file_tool(payload, project, home)
    return None


if __name__ == "__main__":
    g.run_guard(NAME, check)
