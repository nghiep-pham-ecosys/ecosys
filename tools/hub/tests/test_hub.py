import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _hublib as hl  # noqa: E402

START = HERE.parent / "start"


class ClaudeCommandTest(unittest.TestCase):
    def test_default(self):
        self.assertEqual(
            hl.claude_command(),
            ["claude", "remote-control", "--spawn", "worktree", "--name", "hub"],
        )

    def test_permission_mode(self):
        self.assertEqual(hl.claude_command("x", "auto")[-2:], ["--permission-mode", "auto"])


class LaunchCommandTest(unittest.TestCase):
    CMD = ["claude", "remote-control"]

    def test_wraps_in_tmux(self):
        out = hl.launch_command(self.CMD, use_tmux=True, tmux_found=True, inside_tmux=False)
        self.assertEqual(out, ["tmux", "new-session", "-A", "-s", "hub", *self.CMD])

    def test_no_tmux_when_missing_inside_or_off(self):
        for kw in (
            dict(use_tmux=False, tmux_found=True, inside_tmux=False),
            dict(use_tmux=True, tmux_found=False, inside_tmux=False),
            dict(use_tmux=True, tmux_found=True, inside_tmux=True),
        ):
            self.assertEqual(hl.launch_command(self.CMD, **kw), self.CMD)


class StartDryRunTest(unittest.TestCase):
    def test_dry_run_prints_command(self):
        res = subprocess.run(
            [sys.executable, str(START), "--dry-run", "--no-tmux"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("claude remote-control --spawn worktree --name hub", res.stdout)


if __name__ == "__main__":
    unittest.main()
