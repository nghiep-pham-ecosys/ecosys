import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _harness import PROJECT, WT, HookCase  # noqa: E402


class WorktreeGuardTest(HookCase):
    HOOK = "worktree-guard.py"

    # --- required pair
    def test_block_relative_path(self):
        self.assertBlocked("main-bash", command="git worktree add ../lane-a -b feat/3-x origin/main", contains="relative")

    def test_pass_absolute_under_wt(self):
        self.assertAllowed("main-bash", command=f"git worktree add {WT}/s1-lane-a -b feat/3-x origin/main")

    # --- edge cases
    def test_block_relative_even_inside_wt(self):
        self.assertBlocked("main-bash", command="git worktree add .tmp-session/wt/s1-lane-a -b feat/3-x")

    def test_block_absolute_elsewhere(self):
        self.assertBlocked("main-bash", command="git worktree add /tmp/lane-a -b feat/3-x", contains="outside")

    def test_block_dotdot_escape(self):
        self.assertBlocked("main-bash", command=f"git worktree add {WT}/../../escape -b x")

    def test_block_wt_root_itself(self):
        self.assertBlocked("main-bash", command=f"git worktree add {WT} -b x")

    def test_block_sibling_prefix(self):
        self.assertBlocked("main-bash", command=f"git worktree add {WT}-other/s1 -b x")

    def test_pass_project_dir_variable(self):
        self.assertAllowed("main-bash", command='git worktree add "$CLAUDE_PROJECT_DIR"/.tmp-session/wt/s1-lane-b -b feat/4-y')

    def test_pass_home_tilde(self):
        rel = PROJECT.replace("/home/nghiep", "~", 1)
        self.assertAllowed("main-bash", command=f"git worktree add {rel}/.tmp-session/wt/s1-lane-c")

    def test_block_unknown_variable(self):
        self.assertBlocked("main-bash", command="git worktree add $WTDIR/s1-lane-a")

    def test_options_before_path(self):
        self.assertAllowed("main-bash", command=f"git worktree add -f --lock --reason 'lane a' -B feat/3-x {WT}/s1-a origin/main")
        self.assertBlocked("main-bash", command="git worktree add -b feat/3-x --detach lane-a")

    def test_block_missing_path(self):
        self.assertBlocked("main-bash", command="git worktree add")

    def test_git_dash_c_and_chains(self):
        self.assertBlocked("main-bash", command=f"cd {PROJECT} && git -C projects/lab-to-prod worktree add tmp-lane")

    def test_block_move_out_of_wt(self):
        self.assertBlocked("main-bash", command=f"git worktree move {WT}/s1-a /tmp/elsewhere")

    def test_pass_other_worktree_subcommands(self):
        for cmd in ("git worktree list", f"git worktree remove {WT}/s1-a", "git worktree prune"):
            with self.subTest(cmd=cmd):
                self.assertAllowed("main-bash", command=cmd)

    def test_subagent_same_rule(self):
        self.assertBlocked("sub-bash", command="git worktree add lane-x")
        self.assertAllowed("sub-bash", command=f"git worktree add {WT}/s1-lane-x")


if __name__ == "__main__":
    unittest.main()
