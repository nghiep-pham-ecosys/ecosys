"""Tests for tools/ws (sync, status, denylist-scan).

Each test builds throwaway git repos in a temp dir: bare "remotes" plus
a workspace root. No network, no gh (status runs with --no-gh, and gh is
replaced by a fake script where PR counting is tested). Synthetic names only.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

WS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS_DIR))

import _wslib as ws  # noqa: E402

ORG = "example-org"


def run(cmd, cwd=None, env=None, check=True):
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise AssertionError(f"{cmd} failed: {proc.stderr}")
    return proc


def git(cwd, *args):
    return run(["git", *args], cwd=cwd).stdout.strip()


class GitSandbox(unittest.TestCase):
    """Temp dir with isolated git config, bare remotes and a workspace root."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._old_env = dict(os.environ)
        empty_cfg = self.tmp / "gitconfig"
        empty_cfg.write_text("")
        os.environ.update(
            {
                "GIT_CONFIG_GLOBAL": str(empty_cfg),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Test User",
                "GIT_AUTHOR_EMAIL": "test@example.com",
                "GIT_COMMITTER_NAME": "Test User",
                "GIT_COMMITTER_EMAIL": "test@example.com",
            }
        )
        os.environ.pop("CI", None)
        self.remotes = self.tmp / "remotes"
        self.remotes.mkdir()
        self.root = self.tmp / "ws"
        self.root.mkdir()
        self.url_template = str(self.remotes) + "/{name}.git"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_env)
        self._tmp.cleanup()

    # helpers ---------------------------------------------------------------

    def make_remote(self, name: str) -> Path:
        """Bare remote with one commit on main."""
        bare = self.remotes / f"{name}.git"
        run(["git", "init", "--bare", "-q", "-b", "main", str(bare)])
        seed = self.tmp / f"seed-{name}"
        run(["git", "clone", "-q", str(bare), str(seed)])
        git(seed, "checkout", "-q", "-b", "main")
        (seed / "README.md").write_text("Acme demo\n")
        git(seed, "add", "README.md")
        git(seed, "commit", "-q", "-m", "init")
        git(seed, "push", "-q", "-u", "origin", "main")
        return bare

    def push_remote_hooks(self, name: str) -> None:
        """Add a .githooks/pre-push file to the remote's main."""
        side = self.tmp / f"side-{name}-hooks"
        run(["git", "clone", "-q", str(self.remotes / f"{name}.git"), str(side)])
        (side / ".githooks").mkdir()
        (side / ".githooks" / "pre-push").write_text("#!/bin/sh\nexit 0\n")
        git(side, "add", ".githooks")
        git(side, "commit", "-q", "-m", "add hooks")
        git(side, "push", "-q", "origin", "main")

    def push_remote_commit(self, name: str, filename: str = "new.txt") -> str:
        """Add one commit to the remote's main from a side clone; return its sha."""
        side = self.tmp / f"side-{name}-{filename}"
        run(["git", "clone", "-q", str(self.remotes / f"{name}.git"), str(side)])
        (side / filename).write_text("more\n")
        git(side, "add", filename)
        git(side, "commit", "-q", "-m", f"add {filename}")
        git(side, "push", "-q", "origin", "main")
        return git(side, "rev-parse", "HEAD")

    def repo(self, name: str, path: str | None = None, branch: str = "main") -> ws.Repo:
        return ws.Repo(name=name, path=path or f"projects/{name}", visibility="public", area="lab", default_branch=branch)

    def clone_into_ws(self, name: str) -> Path:
        dest = self.root / "projects" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "-q", str(self.remotes / f"{name}.git"), str(dest)])
        return dest

    def sync(self, repo: ws.Repo, dry_run: bool = False) -> ws.SyncResult:
        return ws.sync_repo(self.root, ORG, repo, dry_run=dry_run, url_template=self.url_template)

    def write_manifest(self, repos: list[ws.Repo]) -> Path:
        lines = [f"org: {ORG}", "repos:"]
        for r in repos:
            lines.append(
                f"  - {{ name: {r.name}, path: {r.path}, visibility: {r.visibility}, "
                f"area: {r.area}, default_branch: {r.default_branch} }}"
            )
        path = self.tmp / "repos.yaml"
        path.write_text("\n".join(lines) + "\n")
        return path


class ManifestTests(unittest.TestCase):
    def base(self, **over):
        repo = {"name": "alpha", "path": "projects/alpha", "visibility": "public", "area": "lab", "default_branch": "main"}
        repo.update(over)
        return {"org": ORG, "repos": [repo]}

    def test_valid_manifest(self):
        m = ws.parse_manifest(self.base())
        self.assertEqual(m.org, ORG)
        self.assertEqual(m.repos[0].path, "projects/alpha")

    def test_rejects_unsafe_paths(self):
        for bad in ("../outside", "/abs/path", "~/x", "projects/../../x"):
            with self.subTest(path=bad), self.assertRaises(ws.ManifestError):
                ws.parse_manifest(self.base(path=bad))

    def test_rejects_unknown_keys_such_as_per_repo_org(self):
        data = self.base()
        data["repos"][0]["org"] = "someone-else"
        with self.assertRaises(ws.ManifestError):
            ws.parse_manifest(data)

    def test_rejects_duplicates_and_missing_keys(self):
        data = self.base()
        data["repos"].append(dict(data["repos"][0]))
        with self.assertRaises(ws.ManifestError):
            ws.parse_manifest(data)
        data = self.base()
        del data["repos"][0]["default_branch"]
        with self.assertRaises(ws.ManifestError):
            ws.parse_manifest(data)

    def test_real_manifest_is_valid(self):
        real = WS_DIR.parents[1] / "repos.yaml"
        if not real.is_file():
            self.skipTest("repos.yaml not present")
        m = ws.load_manifest(real)
        self.assertEqual([r.path for r in m.repos if r.path == "."], ["."])

    def test_normalize_remote(self):
        a = ws.normalize_remote("https://github.com/Example-Org/alpha.git")
        b = ws.normalize_remote("git@github.com:example-org/alpha")
        c = ws.normalize_remote("ssh://git@github.com/example-org/alpha.git/")
        self.assertEqual(a, "github.com/example-org/alpha")
        self.assertEqual(a, b)
        self.assertEqual(a, c)


class PrivateOverlayTests(unittest.TestCase):
    """Private overlay manifest (private/ops/repos.private.yaml): merge, collisions, marks."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.public = self.write("repos.yaml", ORG, [("alpha", "projects/alpha", "public"), ("ops", "private/ops", "private")])

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, org, rows):
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"org: {org}", "repos:"]
        for name, rpath, vis in rows:
            lines.append(f"  - {{ name: {name}, path: {rpath}, visibility: {vis}, area: lab, default_branch: main }}")
        path.write_text("\n".join(lines) + "\n")
        return path

    def test_overlay_is_merged_and_marked(self):
        overlay = self.write("private/ops/repos.private.yaml", ORG, [("secret-demo", "projects/secret-demo", "private")])
        m, loaded = ws.load_workspace_manifest(self.public, overlay)
        self.assertEqual(loaded, overlay)
        self.assertEqual([r.name for r in m.repos], ["alpha", "ops", "secret-demo"])
        self.assertEqual([r.private_manifest for r in m.repos], [False, False, True])

    def test_missing_overlay_is_skipped(self):
        m, loaded = ws.load_workspace_manifest(self.public, self.dir / "private/ops/repos.private.yaml")
        self.assertIsNone(loaded)
        self.assertEqual([r.name for r in m.repos], ["alpha", "ops"])
        m, loaded = ws.load_workspace_manifest(self.public, None)
        self.assertIsNone(loaded)

    def test_name_collision_is_an_error(self):
        overlay = self.write("o.yaml", ORG, [("alpha", "projects/alpha-2", "private")])
        with self.assertRaisesRegex(ws.ManifestError, "name collides"):
            ws.load_workspace_manifest(self.public, overlay)

    def test_path_collision_is_an_error(self):
        overlay = self.write("o.yaml", ORG, [("other", "projects/alpha/", "private")])
        with self.assertRaisesRegex(ws.ManifestError, "path 'projects/alpha/' collides"):
            ws.load_workspace_manifest(self.public, overlay)

    def test_overlay_gets_the_same_validation(self):
        for rows, msg in (([("x", "../outside", "private")], "relative|'\\.\\.'"),
                          ([("x", "projects/x", "public")], "only private repos"),
                          ([("x", "projects/x", "private"), ("x", "projects/y", "private")], "duplicate name")):
            with self.subTest(msg=msg):
                overlay = self.write("o.yaml", ORG, rows)
                with self.assertRaisesRegex(ws.ManifestError, msg):
                    ws.load_workspace_manifest(self.public, overlay)

    def test_overlay_org_must_match(self):
        overlay = self.write("o.yaml", "someone-else", [("x", "projects/x", "private")])
        with self.assertRaisesRegex(ws.ManifestError, "differs"):
            ws.load_workspace_manifest(self.public, overlay)

    def test_status_table_marks_private_manifest_rows(self):
        overlay = self.write("o.yaml", ORG, [("secret-demo", "projects/secret-demo", "private")])
        m, _ = ws.load_workspace_manifest(self.public, overlay)
        table = ws.format_status_table([ws.repo_status(self.dir, r) for r in m.repos])
        lines = {line.split()[0]: line for line in table.splitlines()[1:]}
        self.assertIn("private-manifest, missing", lines["secret-demo"])
        self.assertNotIn("private-manifest", lines["alpha"])

    def test_real_overlay_is_valid_when_present(self):
        root = WS_DIR.parents[1]
        overlay = root / ws.PRIVATE_MANIFEST
        if not overlay.is_file():
            self.skipTest("private overlay not present")
        m, loaded = ws.load_workspace_manifest(root / "repos.yaml", overlay)
        self.assertEqual(loaded, overlay)
        self.assertTrue(any(r.private_manifest for r in m.repos))


class WorkspaceFileTests(unittest.TestCase):
    """tools/ws/workspace: the gitignored local VS Code workspace."""

    BASE = {
        "folders": [{"name": "ecosys (root)", "path": "."}, {"name": "alpha", "path": "projects/alpha"}],
        "settings": {"files.exclude": {".tmp-session": True}},
        "extensions": {"recommendations": ["redhat.vscode-yaml"]},
    }

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "repos.yaml").write_text(
            f"org: {ORG}\nrepos:\n"
            "  - { name: ecosys, path: ., visibility: public, area: ecosys, default_branch: main }\n"
            "  - { name: alpha, path: projects/alpha, visibility: public, area: lab, default_branch: main }\n"
            "  - { name: beta, path: projects/beta, visibility: public, area: lab, default_branch: main }\n"
        )
        (self.root / ws.PUBLIC_WORKSPACE).write_text(json.dumps(self.BASE, indent=2))

    def tearDown(self):
        self._tmp.cleanup()

    def add_overlay(self, rows="  - { name: secret-demo, path: projects/secret-demo, visibility: private, area: jobs, default_branch: main }\n"):
        path = self.root / ws.PRIVATE_MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"org: {ORG}\nrepos:\n{rows}")

    def run_tool(self, *args):
        return run([sys.executable, str(WS_DIR / "workspace"), "--root", str(self.root), *args], check=False)

    def read_local(self):
        text = (self.root / ws.LOCAL_WORKSPACE).read_text()
        self.assertTrue(text.startswith("// Generated by tools/ws/workspace"))
        return json.loads(ws.strip_jsonc_comments(text))

    def test_writes_public_plus_private_folders(self):
        self.add_overlay()
        proc = self.run_tool()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("1 from the private manifest", proc.stdout)
        data = self.read_local()
        self.assertEqual([f["path"] for f in data["folders"]],
                         [".", "projects/alpha", "projects/beta", "projects/secret-demo"])
        self.assertEqual(data["folders"][0]["name"], "ecosys (root)")  # names kept from the base file
        self.assertEqual(data["settings"], self.BASE["settings"])
        self.assertEqual(data["extensions"], self.BASE["extensions"])
        # the public file is not changed
        self.assertEqual(json.loads((self.root / ws.PUBLIC_WORKSPACE).read_text()), self.BASE)

    def test_without_overlay_only_public_folders(self):
        proc = self.run_tool()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("no private manifest found", proc.stdout)
        paths = [f["path"] for f in self.read_local()["folders"]]
        self.assertEqual(paths, [".", "projects/alpha", "projects/beta"])

    def test_no_private_manifest_flag_and_stdout(self):
        self.add_overlay()
        proc = self.run_tool("--no-private-manifest", "--stdout")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("secret-demo", proc.stdout)
        self.assertFalse((self.root / ws.LOCAL_WORKSPACE).exists())

    def test_collision_fails_and_writes_nothing(self):
        self.add_overlay("  - { name: alpha, path: projects/alpha-2, visibility: private, area: jobs, default_branch: main }\n")
        proc = self.run_tool()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("collides", proc.stderr)
        self.assertFalse((self.root / ws.LOCAL_WORKSPACE).exists())

    def test_without_base_file_folders_come_from_manifest(self):
        (self.root / ws.PUBLIC_WORKSPACE).unlink()
        self.add_overlay()
        data = json.loads(ws.strip_jsonc_comments(self.run_tool("--stdout").stdout))
        self.assertEqual([f["name"] for f in data["folders"]], ["ecosys (root)", "alpha", "beta", "secret-demo"])

    def test_local_workspace_is_gitignored(self):
        gitignore = WS_DIR.parents[1] / ".gitignore"
        self.assertIn("*.local.code-workspace", gitignore.read_text().splitlines())
        self.assertTrue(ws.LOCAL_WORKSPACE.endswith(".local.code-workspace"))


class SyncTests(GitSandbox):
    def test_clones_missing_repo(self):
        self.make_remote("alpha")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "cloned", result.message)
        self.assertTrue((self.root / "projects/alpha/README.md").is_file())

    def test_dry_run_does_not_clone(self):
        self.make_remote("alpha")
        result = self.sync(self.repo("alpha"), dry_run=True)
        self.assertEqual(result.action, "dry-run")
        self.assertIn("would clone", result.message)
        self.assertFalse((self.root / "projects/alpha").exists())

    def test_root_entry_is_never_cloned(self):
        result = self.sync(self.repo("ecosys", path="."))
        self.assertEqual(result.action, "error")
        self.assertIn("never cloned", result.message)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_fast_forwards_clean_repo_on_default_branch(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        new_sha = self.push_remote_commit("alpha")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "fast-forwarded", result.message)
        self.assertIn("1 commit", result.message)
        self.assertEqual(git(clone, "rev-parse", "HEAD"), new_sha)

    def test_dry_run_does_not_fetch_or_move(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        before = git(clone, "rev-parse", "HEAD")
        self.push_remote_commit("alpha")
        result = self.sync(self.repo("alpha"), dry_run=True)
        self.assertEqual(result.action, "dry-run")
        self.assertEqual(git(clone, "rev-parse", "HEAD"), before)
        self.assertEqual(git(clone, "rev-parse", "origin/main"), before)

    def test_up_to_date(self):
        self.make_remote("alpha")
        self.clone_into_ws("alpha")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "up-to-date", result.message)

    def test_skips_dirty_repo(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        before = git(clone, "rev-parse", "HEAD")
        (clone / "README.md").write_text("local edit\n")
        self.push_remote_commit("alpha")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "skipped")
        self.assertIn("skipped: dirty", result.message)
        self.assertEqual(git(clone, "rev-parse", "HEAD"), before)
        self.assertEqual((clone / "README.md").read_text(), "local edit\n")

    def test_untracked_file_counts_as_dirty(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        (clone / "scratch.txt").write_text("x\n")
        result = self.sync(self.repo("alpha"))
        self.assertIn("skipped: dirty", result.message)

    def test_skips_repo_on_other_branch(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        main_before = git(clone, "rev-parse", "main")
        git(clone, "checkout", "-q", "-b", "feature/x")
        self.push_remote_commit("alpha")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "skipped")
        self.assertIn("skipped: on branch feature/x", result.message)
        self.assertEqual(git(clone, "rev-parse", "--abbrev-ref", "HEAD"), "feature/x")
        self.assertEqual(git(clone, "rev-parse", "main"), main_before)

    def test_skips_diverged_repo(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        (clone / "local.txt").write_text("l\n")
        git(clone, "add", "local.txt")
        git(clone, "commit", "-q", "-m", "local")
        local_sha = git(clone, "rev-parse", "HEAD")
        self.push_remote_commit("alpha")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "skipped")
        self.assertIn("diverged", result.message)
        self.assertEqual(git(clone, "rev-parse", "HEAD"), local_sha)

    def test_skips_origin_mismatch(self):
        self.make_remote("alpha")
        self.make_remote("other")
        clone = self.clone_into_ws("alpha")
        git(clone, "remote", "set-url", "origin", str(self.remotes / "other.git"))
        before = git(clone, "rev-parse", "HEAD")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "skipped")
        self.assertIn("origin is", result.message)
        self.assertEqual(git(clone, "rev-parse", "HEAD"), before)

    def test_non_git_path_is_not_touched(self):
        target = self.root / "projects" / "alpha"
        target.mkdir(parents=True)
        (target / "keep.txt").write_text("k\n")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "error")
        self.assertEqual(sorted(p.name for p in target.iterdir()), ["keep.txt"])

    def test_fetch_does_not_prune_stale_remote_branches(self):
        self.make_remote("alpha")
        side = self.tmp / "side-alpha-branch"
        run(["git", "clone", "-q", str(self.remotes / "alpha.git"), str(side)])
        git(side, "push", "-q", "origin", "main:feature/old")
        clone = self.clone_into_ws("alpha")
        git(side, "push", "-q", "origin", "--delete", "feature/old")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "up-to-date", result.message)
        self.assertEqual(run(["git", "rev-parse", "-q", "--verify", "refs/remotes/origin/feature/old"],
                             cwd=clone, check=False).returncode, 0)

    def test_skips_when_upstream_is_gone(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        git(clone, "update-ref", "-d", "refs/remotes/origin/main")
        result = self.sync(self.repo("alpha"))
        # The fetch brings origin/main back, so the upstream is found again.
        self.assertEqual(result.action, "up-to-date", result.message)
        git(clone, "config", "branch.main.merge", "refs/heads/vanished")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "skipped")
        self.assertIn("upstream of main is gone", result.message)

    def test_clone_sets_hooks_path_when_repo_has_githooks(self):
        self.make_remote("alpha")
        self.push_remote_hooks("alpha")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "cloned", result.message)
        self.assertIn("hooks: set core.hooksPath=.githooks", result.message)
        self.assertEqual(git(self.root / "projects/alpha", "config", "--get", "core.hooksPath"), ".githooks")

    def test_clone_without_githooks_leaves_hooks_path_unset(self):
        self.make_remote("alpha")
        result = self.sync(self.repo("alpha"))
        self.assertNotIn("hooks", result.message)
        proc = run(["git", "config", "--get", "core.hooksPath"], cwd=self.root / "projects/alpha", check=False)
        self.assertNotEqual(proc.returncode, 0)

    def test_ensure_hooks_on_existing_clone(self):
        self.make_remote("alpha")
        self.push_remote_hooks("alpha")
        clone = self.clone_into_ws("alpha")  # plain clone: hooksPath unset

        result = self.sync(self.repo("alpha"), dry_run=True)
        self.assertIn("hooks: would set core.hooksPath=.githooks", result.message)
        self.assertNotEqual(run(["git", "config", "--get", "core.hooksPath"], cwd=clone, check=False).returncode, 0)

        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "up-to-date", result.message)
        self.assertIn("hooks: set core.hooksPath=.githooks", result.message)
        self.assertEqual(git(clone, "config", "--get", "core.hooksPath"), ".githooks")

        result = self.sync(self.repo("alpha"))  # already set: nothing to report
        self.assertNotIn("hooks", result.message)

    def test_ensure_hooks_after_fast_forward_brings_githooks(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        self.push_remote_hooks("alpha")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "fast-forwarded", result.message)
        self.assertIn("hooks: set core.hooksPath=.githooks", result.message)
        self.assertEqual(git(clone, "config", "--get", "core.hooksPath"), ".githooks")

    def test_ensure_hooks_runs_even_when_ff_is_skipped(self):
        self.make_remote("alpha")
        self.push_remote_hooks("alpha")
        clone = self.clone_into_ws("alpha")
        (clone / "scratch.txt").write_text("x\n")
        result = self.sync(self.repo("alpha"))
        self.assertEqual(result.action, "skipped")
        self.assertIn("hooks: set core.hooksPath=.githooks", result.message)
        self.assertEqual((clone / "scratch.txt").read_text(), "x\n")

    def test_ensure_hooks_keeps_other_hooks_path(self):
        self.make_remote("alpha")
        self.push_remote_hooks("alpha")
        clone = self.clone_into_ws("alpha")
        git(clone, "config", "core.hooksPath", "custom-hooks")
        result = self.sync(self.repo("alpha"))
        self.assertIn("core.hooksPath is custom-hooks", result.message)
        self.assertEqual(git(clone, "config", "--get", "core.hooksPath"), "custom-hooks")

    def test_cli_dry_run_and_exit_code(self):
        self.make_remote("alpha")
        manifest = self.write_manifest([self.repo("alpha")])
        cmd = [sys.executable, str(WS_DIR / "sync"), "--root", str(self.root), "--manifest", str(manifest),
               "--url-template", self.url_template]
        proc = run(cmd + ["--dry-run"], check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("would clone", proc.stdout)
        self.assertFalse((self.root / "projects/alpha").exists())
        proc = run(cmd, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue((self.root / "projects/alpha/.git").exists())


class OverlayCliTests(GitSandbox):
    def write_overlay(self, rows: list[ws.Repo]) -> Path:
        lines = [f"org: {ORG}", "repos:"]
        for r in rows:
            lines.append(f"  - {{ name: {r.name}, path: {r.path}, visibility: private, area: jobs, default_branch: main }}")
        path = self.root / ws.PRIVATE_MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n")
        return path

    def sync_cli(self, manifest, *extra):
        cmd = [sys.executable, str(WS_DIR / "sync"), "--root", str(self.root), "--manifest", str(manifest),
               "--url-template", self.url_template, *extra]
        return run(cmd, check=False)

    def test_sync_includes_and_marks_overlay_repos(self):
        self.make_remote("alpha")
        self.make_remote("secret-demo")
        manifest = self.write_manifest([self.repo("alpha")])
        self.write_overlay([self.repo("secret-demo")])
        proc = self.sync_cli(manifest)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        line = next(l for l in proc.stdout.splitlines() if l.startswith("secret-demo"))
        self.assertIn("[private-manifest] cloned", line)
        self.assertNotIn("private-manifest", next(l for l in proc.stdout.splitlines() if l.startswith("alpha")))
        self.assertTrue((self.root / "projects/secret-demo/.git").exists())

    def test_sync_no_private_manifest_flag(self):
        self.make_remote("alpha")
        manifest = self.write_manifest([self.repo("alpha")])
        self.write_overlay([self.repo("secret-demo")])
        proc = self.sync_cli(manifest, "--no-private-manifest", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("secret-demo", proc.stdout)

    def test_sync_collision_exits_2(self):
        manifest = self.write_manifest([self.repo("alpha")])
        self.write_overlay([self.repo("alpha", path="projects/alpha-2")])
        proc = self.sync_cli(manifest, "--dry-run")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("name collides", proc.stderr)

    def test_sync_picks_up_overlay_cloned_in_the_same_run(self):
        # Fresh machine: the ops repo carrying the overlay is cloned by this run.
        self.make_remote("ops")
        side = self.tmp / "side-ops"
        run(["git", "clone", "-q", str(self.remotes / "ops.git"), str(side)])
        (side / "repos.private.yaml").write_text(
            f"org: {ORG}\nrepos:\n"
            "  - { name: secret-demo, path: projects/secret-demo, visibility: private, area: jobs, default_branch: main }\n")
        git(side, "add", "repos.private.yaml")
        git(side, "commit", "-q", "-m", "overlay")
        git(side, "push", "-q", "origin", "main")
        self.make_remote("secret-demo")
        manifest = self.write_manifest([self.repo("ops", path="private/ops")])
        proc = self.sync_cli(manifest)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[private-manifest] cloned", proc.stdout)
        self.assertTrue((self.root / "projects/secret-demo/.git").exists())

    def test_status_marks_overlay_rows(self):
        self.make_remote("alpha")
        self.clone_into_ws("alpha")
        manifest = self.write_manifest([self.repo("alpha")])
        self.write_overlay([self.repo("secret-demo")])
        cmd = [sys.executable, str(WS_DIR / "status"), "--root", str(self.root), "--manifest", str(manifest), "--no-gh"]
        proc = run(cmd, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        line = next(l for l in proc.stdout.splitlines() if l.startswith("secret-demo"))
        self.assertIn("private-manifest, missing", line)


class StatusTests(GitSandbox):
    def status_cli(self, repos, *extra):
        manifest = self.write_manifest(repos)
        cmd = [sys.executable, str(WS_DIR / "status"), "--root", str(self.root), "--manifest", str(manifest), "--no-gh", *extra]
        return run(cmd, check=False)

    def test_missing_clone_detected(self):
        st = ws.repo_status(self.root, self.repo("alpha"))
        self.assertFalse(st.present)
        self.assertEqual(st.problems, ["missing"])
        table = ws.format_status_table([st])
        self.assertIn("missing", table)

    def test_fields_for_clean_repo(self):
        self.make_remote("alpha")
        self.clone_into_ws("alpha")
        st = ws.repo_status(self.root, self.repo("alpha"))
        self.assertTrue(st.present)
        self.assertEqual(st.branch, "main")
        self.assertEqual(st.dirty, 0)
        self.assertEqual(st.ahead_behind, (0, 0))
        self.assertEqual(st.prs, "-")
        self.assertEqual(st.problems, [])

    def test_dirty_count_and_ahead_behind(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        (clone / "local.txt").write_text("l\n")
        git(clone, "add", "local.txt")
        git(clone, "commit", "-q", "-m", "local")
        self.push_remote_commit("alpha")
        git(clone, "fetch", "-q")
        (clone / "a.txt").write_text("a\n")
        (clone / "b.txt").write_text("b\n")
        st = ws.repo_status(self.root, self.repo("alpha"))
        self.assertEqual(st.dirty, 2)
        self.assertEqual(st.ahead_behind, (1, 1))
        self.assertIn("+1/-1", ws.format_status_table([st]))

    def test_strict_passes_when_clean_on_main(self):
        self.make_remote("alpha")
        self.clone_into_ws("alpha")
        proc = self.status_cli([self.repo("alpha")], "--strict")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("alpha", proc.stdout)

    def test_strict_fails_on_dirty_off_branch_or_missing(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        (clone / "x.txt").write_text("x\n")
        proc = self.status_cli([self.repo("alpha")], "--strict")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("dirty", proc.stderr)

        (clone / "x.txt").unlink()
        git(clone, "checkout", "-q", "-b", "feature/y")
        proc = self.status_cli([self.repo("alpha")], "--strict")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("off default branch", proc.stderr)

        proc = self.status_cli([self.repo("beta")], "--strict")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing", proc.stderr)

    def test_no_commits_is_noted_and_fails_strict(self):
        self.make_remote("alpha")
        clone = self.root / "projects" / "alpha"
        clone.mkdir(parents=True)
        git(clone, "init", "-q", "-b", "main")
        git(clone, "remote", "add", "origin", str(self.remotes / "alpha.git"))
        st = ws.repo_status(self.root, self.repo("alpha"))
        self.assertEqual(st.problems, ["no commits"])
        self.assertIn("no commits", ws.format_status_table([st]))
        proc = self.status_cli([self.repo("alpha")], "--strict")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("strict: alpha: no commits", proc.stderr)

    def test_no_origin_is_noted_and_fails_strict(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        git(clone, "remote", "remove", "origin")
        st = ws.repo_status(self.root, self.repo("alpha"))
        self.assertEqual(st.problems, ["no origin"])
        self.assertIn("no origin", ws.format_status_table([st]))
        proc = self.status_cli([self.repo("alpha")], "--strict")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("strict: alpha: no origin", proc.stderr)

    def test_upstream_gone_is_noted_and_fails_strict(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        git(clone, "update-ref", "-d", "refs/remotes/origin/main")
        st = ws.repo_status(self.root, self.repo("alpha"))
        self.assertEqual(st.problems, ["upstream gone"])
        self.assertIn("upstream gone", ws.format_status_table([st]))
        proc = self.status_cli([self.repo("alpha")], "--strict")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("strict: alpha: upstream gone", proc.stderr)

    def test_no_upstream_configured_is_not_gone(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        git(clone, "branch", "--unset-upstream")
        st = ws.repo_status(self.root, self.repo("alpha"))
        self.assertFalse(st.upstream_gone)
        self.assertEqual(st.problems, [])

    def test_without_strict_exit_zero_even_when_dirty(self):
        self.make_remote("alpha")
        clone = self.clone_into_ws("alpha")
        (clone / "x.txt").write_text("x\n")
        proc = self.status_cli([self.repo("alpha"), self.repo("beta")])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("missing", proc.stdout)

    def _fake_gh(self, body: str) -> None:
        bindir = self.tmp / "bin"
        bindir.mkdir(exist_ok=True)
        gh = bindir / "gh"
        gh.write_text("#!/bin/sh\n" + body + "\n")
        gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
        os.environ["PATH"] = f"{bindir}{os.pathsep}{os.environ['PATH']}"

    def test_pr_count_from_gh(self):
        self._fake_gh("echo '" + json.dumps([{"number": 1}, {"number": 7}]) + "'")
        self.assertEqual(ws.open_pr_count(ORG, "alpha"), "2")

    def test_pr_count_unknown_when_gh_fails(self):
        self._fake_gh("echo 'auth required' >&2; exit 4")
        self.assertEqual(ws.open_pr_count(ORG, "alpha"), "?")

    def test_pr_count_unknown_when_gh_missing(self):
        os.environ["PATH"] = str(self.tmp / "empty-bin")
        self.assertEqual(ws.open_pr_count(ORG, "alpha"), "?")


class DenylistScanTests(GitSandbox):
    SCAN = WS_DIR / "denylist-scan"

    def setUp(self):
        super().setUp()
        self.repo_dir = self.tmp / "public-repo"
        self.repo_dir.mkdir()
        git(self.repo_dir, "init", "-q", "-b", "main")
        self.denylist = self.tmp / "denylist.txt"
        self.denylist.write_text("# synthetic terms\nExample Co\nacme-internal\n\n")

    def add(self, rel: str, text: str) -> None:
        p = self.repo_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        git(self.repo_dir, "add", rel)

    def scan(self, *args, denylist=None):
        dl = str(denylist or self.denylist)
        return run([sys.executable, str(self.SCAN), "--denylist", dl, *args], cwd=self.repo_dir, check=False)

    def test_reports_file_and_line_without_the_term(self):
        self.add("docs/a.md", "line one\nworked at EXAMPLE CO last year\n")
        self.add("ok.txt", "nothing here\n")
        proc = self.scan()
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.strip().splitlines(), ["docs/a.md:2"])
        out = (proc.stdout + proc.stderr).lower()
        self.assertNotIn("example co", out)

    def test_masks_term_in_file_name(self):
        self.add("notes/acme-internal-plan.md", "clean text\n")
        proc = self.scan()
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.strip(), "notes/***-plan.md:name")
        self.assertNotIn("acme-internal", (proc.stdout + proc.stderr).lower())

    def test_clean_repo_passes(self):
        self.add("a.txt", "hello world\n")
        proc = self.scan()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(proc.stdout, "")

    def test_untracked_files_are_not_scanned(self):
        self.add("a.txt", "hello\n")
        (self.repo_dir / "local.txt").write_text("Example Co\n")
        proc = self.scan()
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_staged_scans_index_content(self):
        self.add("a.txt", "Example Co\n")
        (self.repo_dir / "a.txt").write_text("clean now\n")  # work tree differs from index
        self.assertEqual(self.scan().returncode, 0)
        proc = self.scan("--staged")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.strip(), "a.txt:1")

    def test_binary_files_are_skipped(self):
        p = self.repo_dir / "img.bin"
        p.write_bytes(b"\0\x01Example Co")
        git(self.repo_dir, "add", "img.bin")
        self.assertEqual(self.scan().returncode, 0)

    def test_missing_denylist_is_silent_in_ci(self):
        self.add("a.txt", "Example Co\n")
        os.environ["CI"] = "true"
        proc = self.scan(denylist=self.tmp / "absent.txt")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout + proc.stderr, "")

    def test_missing_denylist_warns_locally(self):
        proc = self.scan(denylist=self.tmp / "absent.txt")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("skipped", proc.stderr)


if __name__ == "__main__":
    unittest.main()
