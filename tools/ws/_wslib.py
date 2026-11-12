"""Shared logic for the workspace tools (tools/ws/sync, tools/ws/status).

Spec section 4.5: repos.yaml lists every public-safe repo of the org with its
local path. Repos whose names must not appear in public files (for example a
job-related coding exercise) live in a private overlay with the same schema,
private/ops/repos.private.yaml; when that file exists it is merged in, and its
rows are marked "private-manifest" in the output.
`sync` clones missing repos and fast-forwards clean ones on their default
branch; it also points core.hooksPath at a repo's .githooks/ folder when the
repo has one. `status` prints one line per repo. Neither tool ever merges,
rebases, resets or stashes.

Stdlib + PyYAML only.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

DEFAULT_URL_TEMPLATE = "https://github.com/{org}/{name}.git"
NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
REQUIRED_KEYS = ("name", "path", "visibility", "area", "default_branch")
VISIBILITIES = ("public", "private")
# Private overlay manifest, relative to the workspace root. It is read only when
# it exists (it lives in the private ops repo, which may not be cloned yet).
PRIVATE_MANIFEST = "private/ops/repos.private.yaml"
PRIVATE_MARK = "private-manifest"


class ManifestError(ValueError):
    """repos.yaml is missing, malformed or unsafe."""


@dataclass(frozen=True)
class Repo:
    name: str
    path: str
    visibility: str
    area: str
    default_branch: str
    # True for a repo that comes from the private overlay manifest.
    private_manifest: bool = field(default=False, compare=False)


@dataclass
class Manifest:
    org: str
    repos: list[Repo] = field(default_factory=list)


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------


def load_manifest(manifest_path: Path) -> Manifest:
    """Read and validate repos.yaml. Raise ManifestError on any problem."""
    return parse_manifest(_read_yaml(manifest_path))


def load_workspace_manifest(
    manifest_path: Path,
    private_path: Path | None = None,
) -> tuple[Manifest, Path | None]:
    """Load the public manifest and merge the private overlay when it exists.

    Returns (manifest, overlay path actually loaded, or None). Pass
    private_path=None to skip the overlay.
    """
    manifest = load_manifest(manifest_path)
    if private_path is None or not Path(private_path).is_file():
        return manifest, None
    try:
        overlay = parse_manifest(_read_yaml(private_path), private_manifest=True)
    except ManifestError as exc:
        raise ManifestError(f"{private_path}: {exc}") from exc
    return merge_manifests(manifest, overlay), Path(private_path)


def merge_manifests(public: Manifest, overlay: Manifest) -> Manifest:
    """Append the overlay repos to the public ones. Names and paths must not collide."""
    if overlay.org != public.org:
        raise ManifestError(f"private manifest org '{overlay.org}' differs from '{public.org}'")
    names = {r.name for r in public.repos}
    paths = {str(PurePosixPath(r.path)) for r in public.repos}
    for repo in overlay.repos:
        where = f"private manifest repo '{repo.name}'"
        if repo.name in names:
            raise ManifestError(f"{where}: name collides with repos.yaml")
        if str(PurePosixPath(repo.path)) in paths:
            raise ManifestError(f"{where}: path '{repo.path}' collides with repos.yaml")
    return Manifest(org=public.org, repos=[*public.repos, *overlay.repos])


def _read_yaml(manifest_path: Path) -> object:
    try:
        import yaml  # PyYAML; imported here so --help works without it
    except ImportError as exc:  # pragma: no cover - environment issue
        raise ManifestError(
            "PyYAML is not installed for this python3. "
            "Use the system python3 or install pyyaml."
        ) from exc

    try:
        text = Path(manifest_path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read {manifest_path}: {exc.strerror}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"{manifest_path}: invalid YAML: {exc}") from exc
    return data


def parse_manifest(data: object, *, private_manifest: bool = False) -> Manifest:
    """Validate a manifest mapping. With private_manifest=True every repo must be
    private, and the repos are marked as coming from the private overlay."""
    if not isinstance(data, dict):
        raise ManifestError("manifest must be a mapping with 'org' and 'repos'")
    org = data.get("org")
    if not isinstance(org, str) or not NAME_RE.match(org):
        raise ManifestError("'org' must be a GitHub org name")
    raw_repos = data.get("repos")
    if not isinstance(raw_repos, list) or not raw_repos:
        raise ManifestError("'repos' must be a non-empty list")

    repos: list[Repo] = []
    names: set[str] = set()
    paths: set[str] = set()
    for i, raw in enumerate(raw_repos):
        where = f"repos[{i}]"
        if not isinstance(raw, dict):
            raise ManifestError(f"{where}: must be a mapping")
        extra = set(raw) - set(REQUIRED_KEYS)
        if extra:
            # A per-repo 'org' or 'url' would let the tools touch repos
            # outside the workspace org. Refuse unknown keys outright.
            raise ManifestError(f"{where}: unknown keys {sorted(extra)}")
        for key in REQUIRED_KEYS:
            if not isinstance(raw.get(key), str) or not raw[key].strip():
                raise ManifestError(f"{where}: '{key}' must be a non-empty string")
        repo = Repo(**{k: raw[k].strip() for k in REQUIRED_KEYS}, private_manifest=private_manifest)
        where = f"repo '{repo.name}'"
        if not NAME_RE.match(repo.name):
            raise ManifestError(f"{where}: invalid name")
        if not NAME_RE.match(repo.default_branch.replace("/", "")):
            raise ManifestError(f"{where}: invalid default_branch")
        if repo.visibility not in VISIBILITIES:
            raise ManifestError(f"{where}: visibility must be public or private")
        if private_manifest and repo.visibility != "private":
            raise ManifestError(f"{where}: a private manifest lists only private repos")
        check_path(repo.path, where)
        norm = str(PurePosixPath(repo.path))
        if repo.name in names:
            raise ManifestError(f"{where}: duplicate name")
        if norm in paths:
            raise ManifestError(f"{where}: duplicate path '{repo.path}'")
        names.add(repo.name)
        paths.add(norm)
        repos.append(repo)
    return Manifest(org=org, repos=repos)


def check_path(path: str, where: str) -> None:
    """A repo path must be relative and stay inside the workspace root."""
    p = PurePosixPath(path)
    if p.is_absolute() or path.startswith("~") or "\\" in path:
        raise ManifestError(f"{where}: path must be relative to the workspace root")
    if any(part == ".." for part in p.parts):
        raise ManifestError(f"{where}: path must not contain '..'")


def add_manifest_args(parser) -> None:
    """--root, --manifest, --private-manifest and --no-private-manifest, shared by the ws tools."""
    parser.add_argument("--root", type=Path, default=None, help="workspace root (default: the folder that holds tools/)")
    parser.add_argument("--manifest", type=Path, default=None, help="manifest file (default: <root>/repos.yaml)")
    parser.add_argument("--private-manifest", type=Path, default=None, metavar="PATH",
                        help=f"private overlay manifest, merged when it exists (default: <root>/{PRIVATE_MANIFEST})")
    parser.add_argument("--no-private-manifest", action="store_true", help="ignore the private overlay manifest")


def manifest_paths(args) -> tuple[Path, Path, Path | None]:
    """(root, public manifest path, private overlay path or None) from parsed args."""
    root = (args.root or default_root()).resolve()
    manifest_path = args.manifest or root / "repos.yaml"
    if args.no_private_manifest:
        return root, manifest_path, None
    return root, manifest_path, args.private_manifest or root / PRIVATE_MANIFEST


def clone_url(template: str, org: str, repo: Repo) -> str:
    return template.format(org=org, name=repo.name)


# --------------------------------------------------------------------------
# Git helpers
# --------------------------------------------------------------------------


@dataclass
class GitResult:
    code: int
    out: str
    err: str


def git(cwd: Path, *args: str, timeout: int = 120) -> GitResult:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")  # never hang on a credential prompt
    env.setdefault("LC_ALL", "C")
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return GitResult(124, "", f"git {args[0]} timed out after {timeout}s")
    return GitResult(proc.returncode, proc.stdout.strip(), proc.stderr.strip())


def first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def repo_dir(root: Path, repo: Repo) -> Path:
    return (root / repo.path).resolve() if repo.path != "." else root.resolve()


def is_git_worktree(path: Path) -> bool:
    """True if `path` is the top level of its own git work tree."""
    if not path.is_dir():
        return False
    res = git(path, "rev-parse", "--show-toplevel")
    if res.code != 0:
        return False
    return Path(res.out).resolve() == path.resolve()


def current_branch(path: Path) -> str | None:
    """Branch name, or None on a detached HEAD. Works on an unborn branch."""
    res = git(path, "symbolic-ref", "--short", "-q", "HEAD")
    return res.out if res.code == 0 and res.out else None


def dirty_count(path: Path) -> int:
    """Number of changed, staged or untracked entries (ignored files excluded)."""
    res = git(path, "status", "--porcelain=v1")
    if res.code != 0:
        return -1
    return len([line for line in res.out.splitlines() if line.strip()])


def has_commits(path: Path) -> bool:
    return git(path, "rev-parse", "--verify", "-q", "HEAD").code == 0


def upstream_ref(path: Path) -> str | None:
    res = git(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    return res.out if res.code == 0 and res.out else None


def ahead_behind(path: Path) -> tuple[int, int] | None:
    """(ahead, behind) of HEAD vs its upstream, or None if unknown."""
    if upstream_ref(path) is None:
        return None
    res = git(path, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if res.code != 0:
        return None
    try:
        ahead, behind = (int(x) for x in res.out.split())
    except ValueError:
        return None
    return ahead, behind


def upstream_gone(path: Path) -> bool:
    """True when the current branch tracks an upstream whose ref no longer exists."""
    branch = current_branch(path)
    if branch is None:
        return False
    res = git(path, "for-each-ref", "--format=%(upstream)|%(upstream:track)", f"refs/heads/{branch}")
    if res.code != 0 or not res.out:
        return False  # unborn branch or git error: nothing to compare
    upstream, _, track = res.out.partition("|")
    return bool(upstream) and track.strip() == "[gone]"


def origin_url(path: Path) -> str | None:
    res = git(path, "remote", "get-url", "origin")
    return res.out if res.code == 0 and res.out else None


def normalize_remote(url: str) -> str:
    """Reduce a remote URL to host/owner/name so https and ssh forms compare equal."""
    u = url.strip()
    u = re.sub(r"^[a-z+]+://", "", u, flags=re.IGNORECASE)  # https://, ssh://, file://
    u = re.sub(r"^[^@/]+@", "", u)  # git@ or user@
    u = re.sub(r"^([^/:]+):(?!//)", r"\1/", u)  # scp-like host:owner/name
    u = u.rstrip("/")
    if u.lower().endswith(".git"):
        u = u[:-4]
    return u.rstrip("/").lower()


HOOKS_DIR = ".githooks"


def hooks_path(path: Path) -> str | None:
    """Effective core.hooksPath (any config scope), or None when unset."""
    res = git(path, "config", "--get", "core.hooksPath")
    return res.out if res.code == 0 and res.out else None


def ensure_hooks(path: Path, *, dry_run: bool = False) -> tuple[str, bool]:
    """Point core.hooksPath at .githooks/ when the repo has that folder and the
    setting is unset. Only .git/config is written; the work tree is not touched.

    Returns (note, failed). The note is "" when there is nothing to report.
    A hooksPath already set to another value is reported, never overwritten.
    """
    if not (path / HOOKS_DIR).is_dir():
        return "", False
    current = hooks_path(path)
    if current == HOOKS_DIR:
        return "", False
    if current is not None:
        return f"hooks: core.hooksPath is {current}, not {HOOKS_DIR}; left as is", False
    if dry_run:
        return f"hooks: would set core.hooksPath={HOOKS_DIR}", False
    res = git(path, "config", "--local", "core.hooksPath", HOOKS_DIR)
    if res.code != 0:
        return f"hooks: could not set core.hooksPath: {first_line(res.err)}", True
    return f"hooks: set core.hooksPath={HOOKS_DIR}", False


# --------------------------------------------------------------------------
# Sync
# --------------------------------------------------------------------------


@dataclass
class SyncResult:
    repo: Repo
    action: str  # cloned | fast-forwarded | up-to-date | skipped | error | dry-run
    message: str

    @property
    def is_error(self) -> bool:
        return self.action == "error"


def sync_repo(
    root: Path,
    org: str,
    repo: Repo,
    *,
    dry_run: bool = False,
    url_template: str = DEFAULT_URL_TEMPLATE,
) -> SyncResult:
    path = repo_dir(root, repo)
    url = clone_url(url_template, org, repo)

    # Missing clone ---------------------------------------------------------
    if not is_git_worktree(path):
        if repo.path == ".":
            return SyncResult(repo, "error", "workspace root is not a git repo (never cloned by sync)")
        if path.exists() and (not path.is_dir() or any(path.iterdir())):
            return SyncResult(repo, "error", "path exists but is not a git repo; not touched")
        if dry_run:
            return SyncResult(repo, "dry-run", f"would clone {url}")
        path.parent.mkdir(parents=True, exist_ok=True)
        res = git(path.parent, "clone", "--quiet", url, str(path), timeout=600)
        if res.code != 0:
            return SyncResult(repo, "error", f"clone failed: {first_line(res.err)}")
        return _with_hooks(SyncResult(repo, "cloned", f"cloned {url}"), path, dry_run=False)

    # Existing clone ----------------------------------------------------------
    actual = origin_url(path)
    if actual is None:
        return SyncResult(repo, "skipped", "skipped: no origin remote")
    if normalize_remote(actual) != normalize_remote(url):
        return SyncResult(repo, "skipped", f"skipped: origin is {actual}, expected {url}")

    # Hooks are checked after the fetch and fast-forward, which may bring .githooks/ in.
    return _with_hooks(_sync_existing(path, repo, dry_run=dry_run), path, dry_run=dry_run)


def _with_hooks(result: SyncResult, path: Path, *, dry_run: bool) -> SyncResult:
    """Run ensure_hooks and append its note; a failed config write is an error."""
    note, failed = ensure_hooks(path, dry_run=dry_run)
    if not note:
        return result
    action = "error" if failed else result.action
    return SyncResult(result.repo, action, f"{result.message}; {note}")


def _sync_existing(path: Path, repo: Repo, *, dry_run: bool) -> SyncResult:
    """Fetch (no prune: stale remote-tracking refs stay until removed by hand),
    then fast-forward only a clean default branch."""
    if dry_run:
        prefix = "would fetch"
    else:
        res = git(path, "fetch", "--quiet", "origin", timeout=600)
        if res.code != 0:
            return SyncResult(repo, "error", f"fetch failed: {first_line(res.err)}")
        prefix = "fetched"

    dirty = dirty_count(path)
    branch = current_branch(path)
    reasons = []
    if dirty != 0:
        reasons.append("dirty" if dirty < 0 else f"dirty ({dirty} change{'s' if dirty != 1 else ''})")
    if branch is None:
        reasons.append("detached HEAD")
    elif branch != repo.default_branch:
        reasons.append(f"on branch {branch}")
    if reasons:
        return SyncResult(repo, "skipped", f"{prefix}; skipped: " + ", ".join(reasons))

    if not has_commits(path):
        return SyncResult(repo, "skipped", f"{prefix}; skipped: no commits on {branch} yet")
    if upstream_gone(path):
        return SyncResult(repo, "skipped", f"{prefix}; skipped: upstream of {branch} is gone")
    if upstream_ref(path) is None:
        return SyncResult(repo, "skipped", f"{prefix}; skipped: no upstream for {branch}")
    counts = ahead_behind(path)
    if counts is None:
        # Unborn local branch with an upstream, or a broken ref: do not guess.
        return SyncResult(repo, "skipped", f"{prefix}; skipped: cannot compare with upstream")
    ahead, behind = counts
    note = " (as of last fetch)" if dry_run else ""
    if behind == 0:
        extra = f", ahead {ahead}" if ahead else ""
        return SyncResult(repo, "dry-run" if dry_run else "up-to-date", f"{prefix}; up to date{extra}{note}")
    if ahead > 0:
        return SyncResult(
            repo, "skipped", f"{prefix}; skipped: diverged (ahead {ahead}, behind {behind}){note}"
        )
    if dry_run:
        return SyncResult(repo, "dry-run", f"{prefix}; would fast-forward {behind} commit(s){note}")
    res = git(path, "merge", "--ff-only", "--quiet", "@{upstream}")
    if res.code != 0:
        return SyncResult(repo, "error", f"fast-forward failed: {first_line(res.err)}")
    return SyncResult(repo, "fast-forwarded", f"{prefix}; fast-forwarded {behind} commit(s)")


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------

PR_UNKNOWN = "?"
PR_SKIPPED = "-"


@dataclass
class RepoStatus:
    repo: Repo
    present: bool
    branch: str | None = None
    dirty: int = 0
    ahead_behind: tuple[int, int] | None = None
    prs: str = PR_SKIPPED
    has_commits: bool = True
    has_origin: bool = True
    upstream_gone: bool = False

    @property
    def off_default(self) -> bool:
        return self.present and self.branch != self.repo.default_branch

    @property
    def is_dirty(self) -> bool:
        return self.present and self.dirty != 0

    @property
    def problems(self) -> list[str]:
        if not self.present:
            return ["missing"]
        out = []
        if self.is_dirty:
            out.append("dirty")
        if self.off_default:
            out.append("off default branch")
        if not self.has_commits:
            out.append("no commits")
        if not self.has_origin:
            out.append("no origin")
        if self.upstream_gone:
            out.append("upstream gone")
        return out


def repo_status(root: Path, repo: Repo) -> RepoStatus:
    path = repo_dir(root, repo)
    if not is_git_worktree(path):
        return RepoStatus(repo, present=False)
    return RepoStatus(
        repo,
        present=True,
        branch=current_branch(path),
        dirty=dirty_count(path),
        ahead_behind=ahead_behind(path),
        has_commits=has_commits(path),
        has_origin=origin_url(path) is not None,
        upstream_gone=upstream_gone(path),
    )


def open_pr_count(org: str, name: str, *, timeout: int = 30) -> str:
    """Open PR count via gh, or '?' if gh is missing or fails."""
    cmd = [
        "gh", "pr", "list", "--repo", f"{org}/{name}",
        "--state", "open", "--json", "number", "--limit", "500",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return PR_UNKNOWN
    if proc.returncode != 0:
        return PR_UNKNOWN
    try:
        data = json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return PR_UNKNOWN
    return str(len(data)) if isinstance(data, list) else PR_UNKNOWN


def collect_status(root: Path, manifest: Manifest, *, use_gh: bool = True) -> list[RepoStatus]:
    statuses = [repo_status(root, r) for r in manifest.repos]
    if use_gh:
        with ThreadPoolExecutor(max_workers=8) as pool:
            counts = list(pool.map(lambda r: open_pr_count(manifest.org, r.name), manifest.repos))
        for st, count in zip(statuses, counts):
            st.prs = count
    return statuses


def format_ahead_behind(ab: tuple[int, int] | None) -> str:
    if ab is None:
        return "-"
    return f"+{ab[0]}/-{ab[1]}"


def format_status_table(statuses: list[RepoStatus]) -> str:
    header = ("REPO", "PATH", "BRANCH", "DIRTY", "AHEAD/BEHIND", "PRS", "NOTE")
    rows = [header]
    for st in statuses:
        if not st.present:
            note = ", ".join([PRIVATE_MARK, "missing"] if st.repo.private_manifest else ["missing"])
            rows.append((st.repo.name, st.repo.path, "-", "-", "-", st.prs, note))
            continue
        note = [PRIVATE_MARK] if st.repo.private_manifest else []
        if st.branch is None:
            note.append("detached")
        elif st.off_default:
            note.append(f"not {st.repo.default_branch}")
        if not st.has_commits:
            note.append("no commits")
        if not st.has_origin:
            note.append("no origin")
        if st.upstream_gone:
            note.append("upstream gone")
        rows.append(
            (
                st.repo.name,
                st.repo.path,
                st.branch or "(detached)",
                "?" if st.dirty < 0 else str(st.dirty),
                format_ahead_behind(st.ahead_behind),
                st.prs,
                ", ".join(note),
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip() for row in rows]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Local VS Code workspace
# --------------------------------------------------------------------------

PUBLIC_WORKSPACE = "nghiep-pham-ecosys.code-workspace"
LOCAL_WORKSPACE = "nghiep-pham-ecosys.local.code-workspace"
LOCAL_WORKSPACE_HEADER = (
    "// Generated by tools/ws/workspace (just ws-workspace): the public workspace plus\n"
    "// the repos of the private manifest. Gitignored (*.local.code-workspace); do not edit.\n"
)


def strip_jsonc_comments(text: str) -> str:
    """Drop whole-line // comments (the only kind the workspace files use)."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def build_local_workspace(manifest: Manifest, base: dict | None) -> dict:
    """The public workspace (folders, settings, extensions) plus a folder for each
    repo of the manifest that it does not list yet, private-manifest repos included.

    Without a base workspace the folders come from the manifest alone.
    """
    data = dict(base) if base else {}
    folders = [dict(f) for f in data.get("folders", []) if isinstance(f, dict)]
    listed = {str(PurePosixPath(f.get("path", ""))) for f in folders}
    for repo in manifest.repos:
        norm = str(PurePosixPath(repo.path))
        if norm in listed:
            continue
        name = f"{repo.name} (root)" if norm == "." else repo.name
        folders.append({"name": name, "path": repo.path})
        listed.add(norm)
    data["folders"] = folders
    return data


def render_workspace(data: dict) -> str:
    """JSON with one folder per line, like the public workspace file."""
    rest = {k: v for k, v in data.items() if k != "folders"}
    folder_lines = ",\n".join(
        "    { " + ", ".join(f"{json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}"
                           for k, v in f.items()) + " }"
        for f in data.get("folders", [])
    )
    body = json.dumps(rest, indent=2, ensure_ascii=False)
    out = '{\n  "folders": [\n' + folder_lines + "\n  ]"
    if rest:
        out += ",\n" + body[2:]  # body starts with "{\n"
    else:
        out += "\n}"
    return LOCAL_WORKSPACE_HEADER + out + "\n"


def default_root() -> Path:
    """The workspace root is two levels above tools/ws, wherever the tool is run from."""
    return Path(__file__).resolve().parents[2]
