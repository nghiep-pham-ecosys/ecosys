import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _harness  # noqa: E402,F401  (puts the hooks dir on sys.path)
import _guardlib as g  # noqa: E402


class SplitCommandsTest(unittest.TestCase):
    def words(self, text):
        return [c[0] for c in g.split_commands(text)]

    def test_separators(self):
        self.assertEqual(self.words("a; b && c || d | e & f"), ["a", "b", "c", "d", "e", "f"])

    def test_newlines_and_continuations(self):
        self.assertEqual(self.words("a \\\n --flag\nb"), ["a", "b"])

    def test_quotes_keep_text_together(self):
        self.assertEqual(g.split_commands('git commit -m "a; b && c"'), [["git", "commit", "-m", "a; b && c"]])

    def test_wrappers_stripped(self):
        cmds = g.split_commands("FOO=1 env -u BAR sudo -u root nice -n 5 timeout -s KILL 30 git push")
        self.assertIn(["git", "push"], cmds)

    def test_nested_shells(self):
        cmds = g.split_commands("bash -lc 'cd /x && git push'; eval \"gh pr merge 1\"")
        self.assertIn(["git", "push"], cmds)
        self.assertIn(["gh", "pr", "merge", "1"], cmds)

    def test_command_substitution_in_quotes(self):
        self.assertIn(["git", "push"], g.split_commands('echo "result: $(git push)"'))


class HeredocTest(unittest.TestCase):
    def words(self, text):
        return [c[0] for c in g.split_commands(text)]

    def test_body_is_dropped_for_data_readers(self):
        for opener in ("<<EOF", "<<'EOF'", '<<"EOF"', "<< EOF", "<<\\EOF"):
            with self.subTest(opener=opener):
                text = f"cat > f.md {opener}\ngit push\nrm -rf /\nEOF\nls"
                self.assertEqual(self.words(text), ["cat", "ls"])

    def test_dash_form_strips_tabs(self):
        self.assertEqual(self.words("cat <<-EOF\n\tgit push\n\tEOF\nls"), ["cat", "ls"])

    def test_two_heredocs_on_one_line(self):
        self.assertEqual(self.words("diff <<A <<B\nx\nA\ny\nB\nls"), ["diff", "ls"])

    def test_redirect_target_kept(self):
        self.assertIn(["cat", ">", "docs/x.md", "<<", "E"], g.split_commands("cat > docs/x.md <<'E'\nbody\nE"))

    def test_shell_body_is_commands(self):
        self.assertIn(["git", "push"], g.split_commands("bash <<'X'\ngit push\nX"))
        self.assertIn(["git", "push"], g.split_commands("cat <<X | sh\ngit push\nX"))

    def test_herestring_to_shell_is_commands(self):
        self.assertIn(["git", "push"], g.split_commands("bash <<< 'git push'"))
        self.assertNotIn(["git", "push"], g.split_commands("cat <<< 'git push'"))

    def test_code_bodies(self):
        self.assertEqual(g.code_bodies("python3 - <<'PY'\nprint(1)\nPY"), ["print(1)"])
        self.assertEqual(g.code_bodies("cat <<'E'\nprint(1)\nE"), [])

    def test_unterminated_heredoc_stays_commands(self):
        self.assertIn(["git", "push"], g.split_commands("cat <<E\ngit push"))

    def test_heredoc_inside_command_substitution(self):
        cmds = g.split_commands('git commit -m "$(cat <<\'EOF\'\nfix: x\n\ngit push later\nEOF\n)"')
        self.assertNotIn(["git", "push", "later"], cmds)


class LongOptTest(unittest.TestCase):
    def test_prefixes(self):
        for tok in ("--h", "--har", "--hard", "--hard=x"):
            self.assertTrue(g.long_opt(tok, "--hard"), tok)
        for tok in ("--", "-h", "--hardx", "--soft", "hard"):
            self.assertFalse(g.long_opt(tok, "--hard"), tok)


class GitGhPartsTest(unittest.TestCase):
    def test_git_global_options(self):
        sub, args, chdirs, configs = g.git_parts(["git", "-C", "/w", "-c", "a=b", "--no-pager", "push", "-u"])
        self.assertEqual((sub, args, chdirs, configs), ("push", ["-u"], ["/w"], ["a=b"]))

    def test_git_config_env(self):
        self.assertEqual(g.git_parts(["git", "--config-env=alias.p=X", "p"])[3], ["alias.p=X"])
        self.assertEqual(g.git_parts(["git", "--config-env", "alias.p=X", "p"])[3], ["alias.p=X"])

    def test_not_git(self):
        self.assertIsNone(g.git_parts(["gitk"]))

    def test_gh_parts(self):
        self.assertEqual(g.gh_parts(["gh", "pr", "merge", "3"]), ("pr", "merge", ["3"]))
        self.assertEqual(g.gh_parts(["gh", "api", "x"]), ("api", None, ["x"]))

    def test_gh_api_request(self):
        req = g.gh_api_request(["-XPOST", "repos/a/b/issues", "-ftitle=x", "-H", "Accept: y"])
        self.assertEqual(req["method"], "POST")
        self.assertEqual(req["endpoint"], "repos/a/b/issues")
        self.assertEqual(req["fields"], ["title=x"])


class PathTest(unittest.TestCase):
    def test_expand_path(self):
        self.assertEqual(g.expand_path("~/x", "/c", "/p", "/h"), "/h/x")
        self.assertEqual(g.expand_path("$HOME/x", "/c", "/p", "/h"), "/h/x")
        self.assertEqual(g.expand_path("${CLAUDE_PROJECT_DIR}/x", "/c", "/p", "/h"), "/p/x")
        self.assertEqual(g.expand_path("a/../b", "/c", "/p", "/h"), "/c/b")

    def test_is_under(self):
        self.assertTrue(g.is_under("/p/.tmp-session/wt/a", "/p/.tmp-session/wt"))
        self.assertFalse(g.is_under("/p/.tmp-session/wt-x", "/p/.tmp-session/wt"))

    def test_project_dir_fallback_strips_wt(self):
        old = os.environ.pop("CLAUDE_PROJECT_DIR", None)
        try:
            self.assertEqual(g.project_dir({"cwd": "/p/.tmp-session/wt/s1-a/src"}), "/p")
            self.assertEqual(g.project_dir({"cwd": "/p"}), "/p")
        finally:
            if old is not None:
                os.environ["CLAUDE_PROJECT_DIR"] = old


if __name__ == "__main__":
    unittest.main()
