"""public-safe-guard: denylisted terms never go into a public repo.

Every test runs against a synthetic workspace in a temp folder (its own
repos.yaml and git repos) and a synthetic denylist named by
PUBLIC_SAFE_GUARD_DENYLIST. The real local denylist is never read: the
helper refuses to run the hook without the variable.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _harness import build_payload, run_raw  # noqa: E402

HOOK = "public-safe-guard.py"
TERM = "Acme Widgets"  # synthetic term
NEAR_MISS = "Acme widget"  # one letter short: not a substring of the term
DENYLIST = "# synthetic test denylist\n\nAcme Widgets\n# Example Co\nglobex-internal\n"

MANIFEST = """# synthetic manifest
org: example-org
repos:
  - { name: ecosys,      path: .,                    visibility: public,  area: ecosys, default_branch: main }
  - { name: ops,         path: private/ops,          visibility: private, area: ecosys, default_branch: main }
  - { name: demo-public, path: projects/demo-public, visibility: public,  area: lab,    default_branch: main }
"""

GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]


def git(*args):
    subprocess.run(["git", *GIT_ID, *args], check=True, capture_output=True)


class PublicSafeGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="psg-")
        root = cls.root = os.path.realpath(os.path.join(cls.tmp, "ws"))
        os.makedirs(root)
        with open(os.path.join(root, "repos.yaml"), "w", encoding="utf-8") as fh:
            fh.write(MANIFEST)
        with open(os.path.join(root, ".gitignore"), "w", encoding="utf-8") as fh:
            fh.write("private/\nprojects/\n.tmp-session/\n")
        git("init", "-q", "-b", "main", root)
        git("-C", root, "commit", "-q", "--allow-empty", "-m", "init")
        for rel in ("private/ops", "projects/demo-public"):
            path = os.path.join(root, rel)
            os.makedirs(path)
            git("init", "-q", "-b", "main", path)
            git("-C", path, "commit", "-q", "--allow-empty", "-m", "init")
        cls.lane = os.path.join(root, ".tmp-session/wt/s1-lane-a")
        cls.ops_lane = os.path.join(root, ".tmp-session/wt/s1-ops")
        git("-C", root, "worktree", "add", "-q", cls.lane, "-b", "feat/1-x")
        git("-C", os.path.join(root, "private/ops"), "worktree", "add", "-q", cls.ops_lane, "-b", "feat/2-y")
        cls.denylist = os.path.join(cls.tmp, "denylist.txt")
        with open(cls.denylist, "w", encoding="utf-8") as fh:
            fh.write(DENYLIST)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ------------------------------------------------------------ helpers

    def run_guard(self, key, denylist=None, project=None, **kw):
        kw.setdefault("cwd", self.root)
        payload = build_payload(key, **kw)
        env = {"PUBLIC_SAFE_GUARD_DENYLIST": denylist or self.denylist,
               "CLAUDE_PROJECT_DIR": project or self.root}
        self.assertTrue(env["PUBLIC_SAFE_GUARD_DENYLIST"].startswith(self.tmp), "tests use a synthetic denylist only")
        return run_raw(HOOK, json.dumps(payload), env_extra=env)

    def blocked(self, key, **kw):
        code, err = self.run_guard(key, **kw)
        self.assertEqual(code, 2, f"expected block; stderr={err!r}")
        self.assertIn("public-safe-guard", err)
        self.assertNotIn("acme widgets", err.lower(), "a block must never print the term")
        return err

    def allowed(self, key, **kw):
        code, err = self.run_guard(key, **kw)
        self.assertEqual(code, 0, f"expected pass; stderr={err!r}")
        return err

    def write(self, path, content, key="sub-write", **kw):
        return {"key": key, "tool_name": "Write",
                "tool_input": {"file_path": path, "content": content}, **kw}

    def p(self, rel):
        return os.path.join(self.root, rel)

    # ------------------------------------------------------------ required pair (file tools)

    def test_block_write_term_into_public_repo(self):
        err = self.blocked(**self.write(self.p("docs/notes.md"), f"# Notes\n\nWe met {TERM} today.\n"))
        self.assertIn("docs/notes.md", err)
        self.assertIn("public repo ecosys", err)

    def test_pass_near_miss(self):
        self.allowed(**self.write(self.p("docs/notes.md"), f"# Notes\n\n{NEAR_MISS} and AcmeWidgets.\n"))

    # ------------------------------------------------------------ file tools: edge cases

    def test_block_is_case_insensitive(self):
        self.blocked(**self.write(self.p("docs/notes.md"), "ACME WIDGETS"))

    def test_block_public_child_repo(self):
        err = self.blocked(**self.write(self.p("projects/demo-public/README.md"), TERM))
        self.assertIn("demo-public", err)

    def test_pass_private_repo(self):
        self.allowed(**self.write(self.p("private/ops/notes.md"), TERM))

    def test_pass_gitignored_path_in_public_repo(self):
        self.allowed(**self.write(self.p(".tmp-session/checklist.md"), TERM))

    def test_block_lane_worktree_of_public_repo(self):
        self.blocked(**self.write(os.path.join(self.lane, "docs/notes.md"), TERM))

    def test_pass_lane_worktree_of_private_repo(self):
        self.allowed(**self.write(os.path.join(self.ops_lane, "notes.md"), TERM))

    def test_block_relative_path_against_cwd(self):
        self.blocked(**self.write("docs/notes.md", TERM, key="main-read"))

    def test_block_term_in_file_name_masked(self):
        err = self.blocked(**self.write(self.p(f"docs/{TERM.lower()} notes.md"), "clean text"))
        self.assertIn("***", err)

    def test_block_edit_new_string(self):
        self.blocked("sub-write", tool_name="Edit",
                     tool_input={"file_path": self.p("README.md"), "old_string": "x", "new_string": f"see {TERM}"})

    def test_pass_edit_term_only_in_old_string(self):
        self.allowed("sub-write", tool_name="Edit",
                     tool_input={"file_path": self.p("README.md"), "old_string": TERM, "new_string": "a client"})

    def test_block_multiedit(self):
        self.blocked("sub-write", tool_name="MultiEdit",
                     tool_input={"file_path": self.p("README.md"),
                                 "edits": [{"old_string": "a", "new_string": "b"},
                                           {"old_string": "c", "new_string": TERM.lower()}]})

    def test_block_notebook_edit(self):
        self.blocked("sub-write", tool_name="NotebookEdit",
                     tool_input={"notebook_path": self.p("lab/demo.ipynb"), "new_source": f"print('{TERM}')"})

    def test_comment_lines_are_not_terms(self):
        self.allowed(**self.write(self.p("docs/notes.md"), "Example Co is a synthetic name."))

    def test_second_term(self):
        self.blocked(**self.write(self.p("docs/notes.md"), "host GLOBEX-INTERNAL.example.com"))

    def test_missing_denylist_allows_with_notice(self):
        err = self.allowed(denylist=os.path.join(self.tmp, "absent.txt"),
                           **self.write(self.p("docs/notes.md"), TERM))
        self.assertIn("no local denylist", err)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_missing_manifest_counts_every_repo_as_public(self):
        bare = os.path.join(self.tmp, "no-manifest")
        os.makedirs(bare, exist_ok=True)
        git("init", "-q", bare)
        self.blocked(project=bare, cwd=bare, **self.write(os.path.join(bare, "x.md"), TERM))

    def test_missing_manifest_masks_term_in_gh_repo_name(self):
        bare = os.path.join(self.tmp, "no-manifest")
        os.makedirs(bare, exist_ok=True)
        for command in ("gh issue create -R example-org/globex-internal --title x --body y",
                        "gh issue create --repo=example-org/Globex-Internal --title x --body y",
                        "gh api -X POST repos/example-org/globex-internal/issues -f title=x"):
            with self.subTest(command=command):
                err = self.blocked("main-bash", project=bare, cwd=bare, command=command)
                self.assertNotIn("globex-internal", err.lower(), "a block must never print the term")
                self.assertIn("***", err)

    def test_other_tools_pass(self):
        self.allowed("main-read", tool_input={"file_path": self.p("docs/notes.md")})

    # ------------------------------------------------------------ Bash

    def test_block_bash_heredoc_into_public_repo(self):
        self.blocked("main-bash", command=f"cat > docs/x.md <<'EOF'\n{TERM}\nEOF")

    def test_pass_bash_near_miss(self):
        self.allowed("main-bash", command=f"echo '{NEAR_MISS}' > docs/x.md")

    def test_pass_bash_heredoc_into_private_repo(self):
        self.allowed("main-bash", command=f"cat > private/ops/x.md <<'EOF'\n{TERM}\nEOF")

    def test_block_bash_tee_after_cd(self):
        self.blocked("main-bash", command=f"cd projects/demo-public && echo '{TERM}' | tee README.md")

    def test_pass_bash_read_only_mention(self):
        self.allowed("main-bash", command=f"grep -rn '{TERM}' docs")

    def test_pass_bash_rm_of_named_file(self):
        self.allowed("main-bash", command=f"rm 'docs/{TERM.lower()}.md'")

    def test_block_git_commit_message_in_public_repo(self):
        err = self.blocked("main-bash", command=f'git commit -m "docs: add {TERM} page"')
        self.assertIn("git commit", err)

    def test_block_git_commit_in_lane_worktree(self):
        self.blocked("sub-bash", command=f'git -C {self.lane} commit -m "add {TERM}"')

    def test_pass_git_commit_in_private_repo(self):
        self.allowed("main-bash", command=f'git -C private/ops commit -m "notes on {TERM}"')

    def test_block_gh_issue_create_public_repo(self):
        self.blocked("main-bash", command=f'gh issue create -R example-org/demo-public --title "{TERM}" --body x')

    def test_pass_gh_issue_create_private_repo(self):
        self.allowed("main-bash", command=f'gh issue create -R example-org/ops --title "{TERM}" --body x')

    def test_block_gh_pr_create_from_cwd(self):
        self.blocked("main-bash", command=f'gh pr create --title "feat: x" --body "about {TERM}"')

    def test_pass_gh_read_with_term(self):
        self.allowed("main-bash", command=f'gh issue list -R example-org/demo-public --search "{TERM}"')

    def test_block_gh_api_write_to_public_repo(self):
        self.blocked("main-bash", command=f"gh api repos/example-org/demo-public/issues -f title='{TERM}'")

    def test_pass_gh_api_read(self):
        self.allowed("main-bash", command=f"gh api 'repos/example-org/demo-public/issues?q={TERM}'")

    def test_block_graphql_mutation(self):
        self.blocked("main-bash",
                     command=f"gh api graphql -f query='mutation {{ addComment(input: {{body: \"{TERM}\"}}) {{ id }} }}'")

    def test_pass_fd_redirects_to_private_repo(self):
        for redir in ("2>&1", ">&2", "1>&2", "&>/dev/null", "2>/dev/null"):
            with self.subTest(redir=redir):
                self.allowed("main-bash",
                             command=f'gh pr create -R example-org/ops --title "feat: x" --body "about {TERM}" {redir}')

    def test_pass_fd_redirect_in_public_cwd_without_write(self):
        self.allowed("main-bash", command=f"grep -rn '{TERM}' docs 2>&1")

    def test_block_file_redirects_into_public_repo(self):
        for redir in ("> docs/x.md", ">> docs/x.md", "2> docs/x.md", "&> docs/x.md", "2>&1 > docs/x.md"):
            with self.subTest(redir=redir):
                self.blocked("main-bash", command=f"echo '{TERM}' {redir}")


if __name__ == "__main__":
    unittest.main()
