#!/usr/bin/env python3
"""public-safe-guard: PreToolUse hook for the file tools and Bash (spec §9.7, §10.2).

Blocks text that holds a term from the local denylist when the text goes
into a public repo (repos.yaml visibility public):

- Write, Edit, MultiEdit, NotebookEdit: the new text (content, new_string,
  edits[].new_string, new_source) or the file name, when the file lies in a
  public repo and is not gitignored there. A lane worktree counts as the
  repo it was made from.
- Bash, when the command text holds a term and the command
  * writes a file in a public repo (redirects, tee, cp/mv/install/ln/rsync
    targets, sed -i, dd of=), or
  * records git text in a public repo (commit, commit-tree, tag, notes,
    merge), or
  * sends text to a public repo with gh (pr/issue create, edit, comment,
    review, close; release and label create/edit; a write `gh api
    repos/<owner>/<repo>/...` call), or sends a GraphQL mutation.

The denylist is ~/.config/nghiep-pham-ecosys/denylist.txt, one term per line,
'#' starts a comment, case-insensitive substring match (as
tools/ws/denylist-scan). The env var PUBLIC_SAFE_GUARD_DENYLIST points to
another file (tests use a synthetic one). The hook never prints a term: a
block names the file (terms masked as ***) or the repo, and a generic
reason. A missing or unreadable denylist allows the call with a one-line
notice. A missing or unreadable repos.yaml makes every repo count as public.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _guardlib as g  # noqa: E402

NAME = "public-safe-guard"
DENYLIST_ENV = "PUBLIC_SAFE_GUARD_DENYLIST"
DENYLIST_REL = os.path.join(".config", "nghiep-pham-ecosys", "denylist.txt")
MANIFEST = "repos.yaml"
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
HOW = "rewrite it in public-safe words (docs/standards/public-safe-writing.md)"

# Writers that only remove or re-permission a file add no text.
NO_TEXT_WRITERS = {"rm", "unlink", "shred", "chmod", "chown"}
GIT_TEXT_SUBS = {"commit", "commit-tree", "tag", "notes", "merge"}
GH_TEXT_SUBS = {
    "pr": {"create", "edit", "comment", "review", "close"},
    "issue": {"create", "edit", "comment", "close"},
    "release": {"create", "edit"},
    "label": {"create", "edit"},
}
READ_METHODS = {"GET", "HEAD"}
ENTRY_RE = re.compile(r"^\s*-\s*\{(.*)\}\s*(?:#.*)?$")
REPO_ENDPOINT_RE = re.compile(r"^repos/[^/]+/([^/]+)(?:/|$)")
UNKNOWN = "(repos.yaml unreadable, so every repo counts as public)"


# ---------------------------------------------------------------- denylist


def denylist_path() -> str:
    return os.environ.get(DENYLIST_ENV) or os.path.join(g.home_dir(), DENYLIST_REL)


def load_terms():
    """Casefolded terms, or None with a notice when the file is missing or unreadable."""
    path = denylist_path()
    if not os.path.isfile(path):
        sys.stderr.write(f"{NAME}: no local denylist file; check skipped\n")
        return None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        sys.stderr.write(f"{NAME}: cannot read the local denylist; check skipped\n")
        return None
    terms = []
    for line in lines:
        term = line.strip()
        if term and not term.startswith("#"):
            terms.append(term.casefold())
    if not terms:
        sys.stderr.write(f"{NAME}: the local denylist is empty; check skipped\n")
        return None
    return terms


def has_term(text, terms) -> bool:
    folded = str(text).casefold()
    return any(t in folded for t in terms)


def mask(text: str, terms) -> str:
    """The text with every term replaced by ***; never returns a term."""
    for term in terms:
        text = re.sub(re.escape(term), "***", text, flags=re.IGNORECASE)
    return "<a path that holds a denylisted term>" if has_term(text, terms) else text


# ---------------------------------------------------------------- repos


def load_manifest(project: str):
    """[(name, real path, visibility)] from repos.yaml, or None when unreadable.

    repos.yaml uses one flow mapping per line; the hook reads it without
    PyYAML so it runs on a bare python3.
    """
    try:
        with open(os.path.join(project, MANIFEST), encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None
    out = []
    for line in text.splitlines():
        m = ENTRY_RE.match(line)
        if not m:
            continue
        fields = {}
        for part in m.group(1).split(","):
            key, sep, val = part.partition(":")
            if sep:
                fields[key.strip()] = val.strip().strip("'\"")
        if fields.get("path") and fields.get("visibility"):
            real = os.path.realpath(os.path.join(project, fields["path"]))
            out.append((fields.get("name", ""), real, fields["visibility"].lower()))
    return out or None


def repo_root(start: str):
    """The nearest folder at or above `start` that holds .git (folder or file)."""
    d = os.path.realpath(start)
    while not os.path.isdir(d):
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def main_root(root: str):
    """For a linked worktree (.git is a file), the folder of the repo it was made from."""
    dotgit = os.path.join(root, ".git")
    if not os.path.isfile(dotgit):
        return None
    try:
        with open(dotgit, encoding="utf-8") as fh:
            first = fh.readline().strip()
    except OSError:
        return None
    if not first.startswith("gitdir:"):
        return None
    gitdir = first[len("gitdir:"):].strip()
    if not os.path.isabs(gitdir):
        gitdir = os.path.join(root, gitdir)
    common = gitdir
    try:
        with open(os.path.join(gitdir, "commondir"), encoding="utf-8") as fh:
            rel = fh.read().strip()
        common = rel if os.path.isabs(rel) else os.path.join(gitdir, rel)
    except OSError:
        pass
    common = os.path.realpath(common)
    if os.path.basename(common) != ".git":
        return None  # a submodule or a bare repo: no work tree folder to match
    return os.path.dirname(common)


def repo_of(start: str, manifest):
    """(visibility, root, name) of the repo that holds `start`; visibility None when unknown."""
    root = repo_root(start)
    if root is None:
        return None, None, None
    if manifest is None:
        return "public", root, UNKNOWN
    cands = {root}
    main = main_root(root)
    if main:
        cands.add(main)
    found = [(vis, name) for name, path, vis in manifest if path in cands]
    for vis, name in found:
        if vis == "public":
            return "public", root, name
    if found:
        return found[0][0], root, found[0][1]
    return None, root, None


def is_ignored(root: str, path: str) -> bool:
    try:
        proc = subprocess.run(["git", "-C", root, "check-ignore", "-q", "--", path],
                              capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def public_file(path: str, manifest):
    """Repo name when `path` is a file in a public repo that git does not ignore, else None."""
    real = os.path.realpath(path)
    vis, root, name = repo_of(os.path.dirname(real), manifest)
    if vis != "public" or is_ignored(root, real):
        return None
    return name


def public_by_name(repo_arg: str, manifest):
    """Name of a public repo named by gh -R / an API endpoint, else None."""
    name = repo_arg.rstrip("/").rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    if manifest is None:
        return name or UNKNOWN
    for entry_name, _path, vis in manifest:
        if entry_name == name and vis == "public":
            return name
    return None


# ---------------------------------------------------------------- file tools


def file_texts(tool: str, ti: dict) -> list:
    if tool == "Write":
        vals = [ti.get("content")]
    elif tool == "Edit":
        vals = [ti.get("new_string")]
    elif tool == "MultiEdit":
        vals = [e.get("new_string") for e in ti.get("edits") or [] if isinstance(e, dict)]
    else:
        vals = [ti.get("new_source")]
    return [v for v in vals if isinstance(v, str)]


def check_file_tool(payload, terms, project, cwd):
    ti = payload.get("tool_input") or {}
    raw = ti.get("file_path") or ti.get("notebook_path")
    if not isinstance(raw, str) or not raw:
        return None
    in_text = any(has_term(t, terms) for t in file_texts(payload.get("tool_name"), ti))
    in_name = has_term(raw, terms)
    if not (in_text or in_name):
        return None
    path = g.expand_path(raw, cwd, project)
    name = public_file(path, load_manifest(project))
    if not name:
        return None
    what = "the text written to" if in_text else "the name of"
    return f"{what} {mask(path, terms)} (public repo {mask(name, terms)}) holds a term from the local denylist; {HOW}"


# ---------------------------------------------------------------- Bash


def _gh_repo_arg(core):
    for k, word in enumerate(core):
        tok = str(word)
        if tok in ("-R", "--repo") and k + 1 < len(core):
            return str(core[k + 1])
        if tok.startswith("--repo="):
            return tok[len("--repo="):]
        if tok.startswith("-R") and len(tok) > 2:
            return tok[2:]
    return None


def _gh_api_target(args, manifest):
    req = g.gh_api_request(args)
    method = str(req["method"]) if req["method"] is not None else None
    has_body = bool(req["fields"]) or req["input"] is not None
    if not (method is not None and method not in READ_METHODS or method is None and has_body):
        return None
    endpoint = g.normalize_endpoint(str(req["endpoint"] or ""))
    if endpoint == "graphql":
        values = " ".join(str(f) for f in req["fields"]).lower()
        return "GitHub (a GraphQL mutation)" if "mutation" in values else None
    m = REPO_ENDPOINT_RE.match(endpoint)
    return public_by_name(m.group(1), manifest) if m else None


def _gh_target(core, gh, folders, manifest):
    group, sub, args = str(gh[0]), gh[1], gh[2]
    if group == "api":
        return _gh_api_target(args, manifest)
    if sub is None or str(sub) not in GH_TEXT_SUBS.get(group, set()):
        return None
    repo_arg = _gh_repo_arg(core)
    if repo_arg:
        return public_by_name(repo_arg, manifest)
    for folder in folders:
        vis, _root, name = repo_of(folder, manifest)
        if vis == "public":
            return name
    return None


def check_bash(payload, terms, project, cwd):
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not has_term(command, terms):
        return None
    home = g.home_dir()
    manifest = load_manifest(project)
    infos = g.command_infos(command)
    cwds = g.track_cwds(infos, cwd, project, home)
    for info, folders in zip(infos, cwds):
        core = info["core"]
        base = os.path.basename(str(core[0])) if core else ""
        if base not in NO_TEXT_WRITERS:
            for target in g.write_targets(info):
                for folder in folders:
                    path = g.expand_path(str(target), folder, project, home)
                    name = public_file(path, manifest)
                    if name:
                        return (f"this command holds a term from the local denylist and writes "
                                f"{mask(path, terms)} in public repo {mask(name, terms)}; {HOW}")
        parts = g.git_parts(core)
        if parts and str(parts[0]) in GIT_TEXT_SUBS:
            dirs = [g.expand_path(str(d), f, project, home) for d in parts[2] for f in folders] or folders
            for d in dirs:
                vis, _root, name = repo_of(d, manifest)
                if vis == "public":
                    return (f"this command holds a term from the local denylist and runs git {parts[0]} "
                            f"in public repo {mask(name, terms)}; {HOW}")
        gh = g.gh_parts(core)
        if gh:
            name = _gh_target(core, gh, folders, manifest)
            if name:
                return (f"this command holds a term from the local denylist and sends text to "
                        f"public repo {mask(name, terms)} with gh; {HOW}")
    return None


# ---------------------------------------------------------------- entry


def check(payload):
    tool = payload.get("tool_name")
    if tool not in FILE_TOOLS and tool != "Bash":
        return None
    terms = load_terms()
    if terms is None:
        return None
    project = g.project_dir(payload)
    cwd = g.payload_cwd(payload)
    if tool in FILE_TOOLS:
        return check_file_tool(payload, terms, project, cwd)
    return check_bash(payload, terms, project, cwd)


if __name__ == "__main__":
    g.run_guard(NAME, check)
