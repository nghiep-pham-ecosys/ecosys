import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _harness import HOOKS_DIR  # noqa: E402

SETTINGS = os.path.join(os.path.dirname(HOOKS_DIR), "settings.json")


class SettingsTest(unittest.TestCase):
    """settings.json wires the hooks as spec §9.7 says, with the documented deviations."""

    @classmethod
    def setUpClass(cls):
        with open(SETTINGS, encoding="utf-8") as fh:
            cls.settings = json.load(fh)

    def hook_matchers(self, script):
        out = []
        for entry in self.settings["hooks"]["PreToolUse"]:
            if any(script in h["command"] for h in entry["hooks"]):
                out.append(entry["matcher"])
        return out

    def test_secret_path_guard_matcher_covers_all_file_tools(self):
        (matcher,) = self.hook_matchers("secret-path-guard.py")
        self.assertEqual(set(matcher.split("|")),
                         {"Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "Grep", "Glob", "Bash"})

    def test_bash_guards(self):
        # ship-guard also sees the file-writing tools (protected git/gh config).
        self.assertEqual(self.hook_matchers("ship-guard.py"), ["Bash", "Write|Edit|MultiEdit|NotebookEdit"])
        self.assertEqual(self.hook_matchers("worktree-guard.py"), ["Bash"])

    def test_mcp_merge_is_denied(self):
        deny = self.settings["permissions"]["deny"]
        self.assertIn("mcp__plugin_github_github__merge_pull_request", deny)
        self.assertIn("Bash(gh pr merge*)", deny)

    def test_hook_scripts_exist(self):
        for script in ("ship-guard.py", "worktree-guard.py", "secret-path-guard.py"):
            self.assertTrue(os.path.isfile(os.path.join(HOOKS_DIR, script)), script)


if __name__ == "__main__":
    unittest.main()
