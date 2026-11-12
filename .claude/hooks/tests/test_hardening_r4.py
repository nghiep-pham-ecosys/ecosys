"""Round 4 hardening: bypasses from the second adversarial review.

Each block case has near-miss pass cases next to it, so the fixes do not
turn the guards against normal work.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _harness import HOME, PROJECT, WT, HookCase  # noqa: E402
import _guardlib as g  # noqa: E402

SOPS_KEY = HOME + "/.config/sops/age/keys.txt"
DENYLIST = HOME + "/.config/nghiep-pham-ecosys/denylist.txt"


def words(text):
    return [[str(t) for t in cmd] for cmd in g.split_commands(text)]


class Multi(HookCase):
    def blocked(self, cmds, key="sub-bash", contains=None):
        for cmd in cmds:
            with self.subTest(cmd=cmd, key=key):
                self.assertBlocked(key, command=cmd, contains=contains)

    def allowed(self, cmds, key="sub-bash"):
        for cmd in cmds:
            with self.subTest(cmd=cmd, key=key):
                self.assertAllowed(key, command=cmd)


# ====================================================================== parser


class ParserR4Test(unittest.TestCase):
    def test_path_aliases_normalised(self):
        self.assertEqual(g.expand_path("//home/x", "/c", PROJECT), "/home/x")
        self.assertEqual(g.expand_path("///home//x", "/c", PROJECT), "/home/x")
        self.assertEqual(g.expand_path("/proc/self/root/home/x", "/c", PROJECT), "/home/x")
        self.assertEqual(g.expand_path("/proc/4242/root//proc/self/root/etc", "/c", PROJECT), "/etc")
        self.assertEqual(g.expand_path("/proc/self/cwd/a", "/c", PROJECT), "/c/a")
        self.assertEqual(g.expand_path("~+/a", "/c", PROJECT), "/c/a")
        self.assertEqual(g.expand_path("/proc/selfish/root/x", "/c", PROJECT), "/proc/selfish/root/x")

    def test_cwd_tracking(self):
        infos = g.command_infos("cd ~/.config && cd sops; cat age/keys.txt")
        cwds = g.track_cwds(infos, PROJECT, PROJECT, HOME)
        self.assertIn(HOME + "/.config/sops", cwds[-1])
        self.assertIn(PROJECT, cwds[-1])  # a subshell keeps the old cwd
        self.assertIn(HOME, g.track_cwds(g.command_infos("cd; ls"), PROJECT, PROJECT, HOME)[-1])
        self.assertEqual(g.track_cwds(g.command_infos('cd "$X"; ls'), PROJECT, PROJECT, HOME)[-1], [PROJECT])

    def test_same_line_symlinks(self):
        infos = g.command_infos("ln -s ~/.config cfg && cat cfg/x")
        cwds = g.track_cwds(infos, PROJECT, PROJECT, HOME)
        links = g.line_symlinks(infos, cwds, PROJECT, HOME)
        self.assertIn((PROJECT + "/cfg", HOME + "/.config"), links)
        self.assertIn(HOME + "/.config/sops/k", g.path_aliases(PROJECT + "/cfg/sops/k", links))

    def test_env_vars_that_run_commands_are_walked(self):
        self.assertIn(["git", "push"], words("GIT_PAGER='sh -c \"git push\"' git log -1"))
        self.assertIn(["git", "push"], words("GIT_EDITOR='git push; true' git commit --amend"))
        self.assertIn(["gh", "pr", "merge", "3"], words("env GIT_EXTERNAL_DIFF='gh pr merge 3' git diff"))
        self.assertIn(["sops", "-d", "%s"], words("LESSOPEN='|sops -d %s' less s.sops.yaml"))
        self.assertIn(["git", "push"], words("export GIT_SSH_COMMAND='git push'; git fetch"))
        self.assertNotIn(["git", "push"], words("FOO='git push' git log"))

    def test_git_options_that_run_commands_are_walked(self):
        for text in ("git grep -O'git push' foo", "git grep --open-files-in-pager='git push' foo",
                     "git difftool -y -x 'git push' HEAD~1", "git difftool --extcmd='git push'",
                     "git filter-branch -f --tree-filter 'git push' HEAD", "git clone -u 'git push' . /tmp/x",
                     "git fetch --upload-pack='git push' o", "git ls-remote --upload-pack 'git push' .",
                     "git archive --exec='git push' --remote=x HEAD"):
            with self.subTest(text=text):
                self.assertIn(["git", "push"], words(text))
        self.assertNotIn(["git", "push"], words("git grep -O foo 'git push'"))

    def test_source_dev_stdin_here_string(self):
        self.assertIn(["git", "push"], words("source /dev/stdin <<<'git push'"))
        self.assertIn(["git", "push"], words(". /dev/stdin <<< 'git push'"))

    def test_shell_c_positional_arguments(self):
        self.assertIn(["gh", "pr", "merge", "3"], words("bash -c '\"$0\" pr merge 3' gh"))
        self.assertIn(["gh", "pr", "merge", "3"], words("sh -c '$1 pr merge 3' x gh"))

    def test_taskset_is_a_wrapper(self):
        self.assertIn(["sops", "-d", "f"], words("taskset -c 0 sops -d f"))
        self.assertIn(["sops", "-d", "f"], words("taskset 0x1 sops -d f"))


# ====================================================================== worktree-guard


class WorktreeR4Test(Multi):
    HOOK = "worktree-guard.py"

    def test_block_quoting_tricks(self):
        for key in ("main-bash", "sub-bash"):
            self.blocked(["git wor''ktree add /tmp/evil", "git work\\tree add /tmp/evil",
                          'git "worktree" add /tmp/evil', "git $'worktree' add /tmp/evil"], key=key)

    def test_block_aliases_defined_on_the_line(self):
        self.blocked(["git -c alias.wa='worktree add' wa /tmp/evil",
                      "git config alias.wa 'worktree add' && git wa /tmp/evil",
                      "git config set alias.wa 'worktree add'; git wa /tmp/evil"], key="main-bash")
        self.allowed([f"git -c alias.wa='worktree add' wa {WT}/s4-ok"], key="main-bash")

    def test_block_symlink_made_on_the_line(self):
        self.blocked([f"ln -s /tmp {WT}/esc && git worktree add {WT}/esc/x",
                      f"ln -sfn /tmp {WT}/esc; git worktree add {WT}/esc"], key="main-bash", contains="symlink")

    def test_pwd_resolves_against_cwd(self):
        self.allowed(['git worktree add "$PWD/.tmp-session/wt/s4-lane-e"',
                      f'cd {PROJECT} && git worktree add "$PWD/.tmp-session/wt/s4-lane-f"'], key="main-bash")
        self.blocked(['cd /tmp && git worktree add "$PWD/.tmp-session/wt/s4-lane-g"'], key="main-bash")

    def test_pass_normal_worktree_work(self):
        self.allowed([f"git worktree add {WT}/s4-lane-a -b feat/4-x origin/main", "git worktree list",
                      "git status", "echo worktree"], key="main-bash")


# ====================================================================== secret-path-guard


class SecretR4Test(Multi):
    HOOK = "secret-path-guard.py"

    def test_block_path_aliases(self):
        self.blocked([f"cat /{SOPS_KEY}", f"cat //{DENYLIST}", f"cat /proc/self/root{SOPS_KEY}",
                      f"cat /proc/1/root{DENYLIST}", f"cat /proc/thread-self/root{SOPS_KEY}"])
        for path in (f"/{SOPS_KEY}", f"/proc/self/root{DENYLIST}", f"/proc/self/root/{SOPS_KEY}"):
            with self.subTest(path=path):
                self.assertBlocked("main-read", tool_input={"file_path": path})

    def test_block_literal_cd_then_relative_path(self):
        self.blocked(["cd ~/.config && cat sops/age/keys.txt", "cd && cat .config/sops/age/keys.txt",
                      "cd ~/.config && cat nghiep-pham-ecosys/denylist.txt", "pushd ~/.config >/dev/null; cat sops/age/keys.txt",
                      "cd ~ && cat ~+/.config/sops/age/keys.txt", "cd ~/.config; cd sops; cat age/keys.txt",
                      "cd -- ~/.config && cat sops/age/keys.txt"])

    def test_block_symlinks_made_on_the_line(self):
        self.blocked(["ln -s ~/.config cfg && cat cfg/sops/age/keys.txt",
                      "ln -s ~ h; cat h/.config/nghiep-pham-ecosys/denylist.txt",
                      "ln -sf ~/.config/nghiep-pham-ecosys d && cat d/denylist.txt"])

    def test_block_recursive_readers_above_protected_folders(self):
        self.blocked(["find ~/.config -name keys.txt -exec cat {} +", "grep -r AGE-SECRET ~/.config",
                      "grep -Rn AGE ~", "grep --recursive x /home/nghiep/.config", "grep -d recurse x ~/.config",
                      "rg AGE-SECRET ~/.config", "rg AGE ~", "ag x ~/.config", "tar czf /tmp/c.tgz ~/.config",
                      "cp -r ~/.config /tmp/c", "rsync -a ~/.config/ /tmp/c", "grep -r x ~/.conf*",
                      "cd ~ && grep -r AGE ."], contains="recursive")
        for ti in ({"pattern": "AGE-SECRET", "path": HOME + "/.config"},
                   {"pattern": ".", "path": HOME + "/.config", "glob": "*.txt"},
                   {"pattern": "x", "path": HOME}):
            with self.subTest(ti=ti):
                self.assertBlocked("main-read", tool_name="Grep", tool_input=ti)

    def test_pass_recursive_readers_elsewhere(self):
        self.allowed(["grep -rn TODO src/", "grep -rn 'process.env' src/", "rg foo", "rg -n foo . -g '*.ts'",
                      "find . -name '*.py' -exec wc -l {} +", "find ~/.config -maxdepth 1 -type d",
                      "tar czf /tmp/x.tgz src", "cp -r src /tmp/x", "ls -la ~/.config", f"cd {PROJECT} && grep -r foo ."])
        self.assertAllowed("main-read", tool_name="Grep", tool_input={"pattern": "x", "path": PROJECT})
        self.assertAllowed("main-read", tool_name="Grep", tool_input={"pattern": "x"})

    def test_block_key_and_env_globs(self):
        self.blocked(["cat server.ke?", "cat certs/*.pe[m]", "cat certs/*.k*", "cat deploy.k*",
                      "cat certs/*.[pP][eE][mM]", "cat *env", "cat ?env", "find . -name '*env' -exec cat {} +",
                      "find . -maxdepth 1 -iname '*.PEM' -exec cat {} +", "cat .ENV", "cat .Env.local"])
        for glob in ("*.p?m", "*.{pem,key}", "{.env,x}", "*env", "**/*.k?y", "*.{ts,env}"):
            with self.subTest(glob=glob):
                self.assertBlocked("main-read", tool_name="Grep",
                                   tool_input={"pattern": "x", "path": PROJECT, "glob": glob})

    def test_pass_ordinary_globs_and_regexes(self):
        self.allowed(["ls *.md", "cat README.*", "git add *", "cat docs/*", "sed -i 's/api.*key/x/' f.py",
                      "grep -E 'api.*key' src/x.py", "git log --grep 'fix.*key' --oneline", "sed 's/.*env//' f",
                      "rg -n '\\.env' docs/"])
        self.assertAllowed("main-read", tool_name="Grep",
                           tool_input={"pattern": "x", "path": PROJECT, "glob": "*.{ts,tsx}"})

    def test_message_pattern_and_name_only_words(self):
        self.allowed(["git commit -m 'chore: ignore /.env'", "git commit -m 'fix: load .env/.env.local in dev only'",
                      "grep -n .env .gitignore", "test -f .env && echo present", "git check-ignore -v .env",
                      "ls -d .*", "cat .env.sops.yaml"])
        self.assertAllowed("main-read", tool_input={"file_path": PROJECT + "/.env.sops.yaml"})
        # the folders still count in text words, and real reads still count
        self.blocked(["grep -f ~/.config/nghiep-pham-ecosys/denylist.txt README.md", "cat .env",
                      "xxd -b .env", "grep x .env", "git commit -F .env"])

    def test_denylist_scanner_exemption_needs_the_real_scanner(self):
        self.blocked([f"/tmp/x/tools/ws/denylist-scan {DENYLIST}", f"python3 /tmp/x/tools/ws/denylist-scan {DENYLIST}",
                      f"cd /tmp/x && tools/ws/denylist-scan {DENYLIST}",
                      f"tools/w?/denylist-scan {DENYLIST}"], key="main-bash")
        self.allowed([f"tools/ws/denylist-scan {DENYLIST}", f"{PROJECT}/tools/ws/denylist-scan {DENYLIST}",
                      f"python3 {PROJECT}/tools/ws/denylist-scan {DENYLIST}",
                      f'"$CLAUDE_PROJECT_DIR"/tools/ws/denylist-scan {DENYLIST}'], key="main-bash")

    def test_denylist_scanner_exemption_needs_claude_project_dir(self):
        self.assertAllowed("main-bash", command=f"tools/ws/denylist-scan {DENYLIST}")
        from _harness import run_hook

        code, _err = run_hook(self.HOOK, "main-bash", project_env=False,
                              command=f"tools/ws/denylist-scan {DENYLIST}")
        self.assertEqual(code, 2)

    def test_block_decrypt_through_env_and_wrappers(self):
        self.blocked(["GIT_PAGER='sops -d s.sops.yaml' git log -1", "LESSOPEN='|sops -d %s' less s.sops.yaml",
                      "taskset -c 0 sops -d s.sops.yaml", "git difftool --extcmd='sops -d s.sops.yaml' HEAD"],
                     key="main-bash")
        self.allowed(["GIT_PAGER=cat git log -1", "LESSOPEN='|lesspipe %s' less README.md"], key="main-bash")


# ====================================================================== ship-guard


class ShipR4Test(Multi):
    HOOK = "ship-guard.py"

    def test_block_git_env_commands(self):
        self.blocked(["GIT_PAGER='sh -c \"git push\"' git log -1", "GIT_EDITOR='git push; true' git commit --amend",
                      "GIT_EXTERNAL_DIFF='git push' git diff", "GIT_SEQUENCE_EDITOR='git push' git rebase -i HEAD~2",
                      "GIT_SSH_COMMAND='git push' git fetch", "export PAGER='git push'; git log"])
        self.blocked(["GIT_PAGER='gh pr merge 3' git log -1", "GIT_SSH_COMMAND='gh pr merge 3' git fetch",
                      "EDITOR='gh pr merge 3' git commit"], key="main-bash")
        self.allowed(["GIT_PAGER=cat git log -1", "GIT_EDITOR=true git rebase --continue", "PAGER=less git log"])

    def test_block_git_options_that_run_commands(self):
        self.blocked(["git grep -O'git push' foo", "git difftool -y -x 'git push' HEAD~1",
                      "git filter-branch -f --tree-filter 'git push' HEAD", "git clone -u 'sh -c \"git push\"' . /tmp/x",
                      "git fetch --upload-pack='git push' origin"])
        self.blocked(["git ls-remote -u 'gh pr merge 3' .", "git grep -O'gh pr merge 3' x"], key="main-bash")
        self.allowed(["git grep -n foo", "git difftool --tool=vimdiff HEAD~1", "git fetch origin"])

    def test_block_source_stdin_and_positional_args(self):
        self.blocked(["source /dev/stdin <<<'git push'", ". /dev/stdin <<< 'git push'"])
        self.blocked(["bash -c '\"$0\" pr merge 3' gh", "sh -c '$1 pr merge 3' x gh"], key="main-bash")
        self.allowed(["bash -c 'echo \"$0\"' hello"], key="main-bash")

    def test_safety_net_reads_shell_text_arguments(self):
        self.blocked(["tmux new-session -d 'git push'", "at now <<< 'git push'", "ssh host 'git push'"])
        self.blocked(["tmux new -d 'gh pr merge 3'", "at now <<< 'gh pr merge 3'"], key="main-bash")
        self.allowed(["tmux ls", "git commit -m 'docs: explain git push rules'", "test \"$x\" = 'git push'",
                      "python3 -c \"print('hello world')\""])
        self.allowed(["gh pr create --title x --body 'never run gh pr merge 3 by hand'"], key="main-bash")

    def test_block_merge_tool_after_cd_and_through_globs(self):
        self.blocked(["cd tools/ship && ./merge 3", "cd tools && ship/merge 3", "tools/sh?p/merge 3",
                      "tools/shi[p]/merge 3", "tools/*/merge 3", "tools/{ship,x}/merge 3", "cd tools/sh?p && ./merge 3",
                      f"ln -s {PROJECT}/tools/ship/merge m && ./m 3", "D=tools/ship; $D/merge 3", '"$X"/merge 3',
                      "python3 -m pdb tools/ship/merge"], contains="merge")
        self.allowed(["cd tools/ship && cat merge", "cd tools/ship && python3 -m unittest discover",
                      "sed -n 1,20p tools/ship/merge", "python3 -m py_compile tools/ship/merge",
                      "ruff check tools/ship/merge", "git merge --no-ff feat/x"])
        self.allowed(["cd tools/ship && ./merge 3", "tools/sh?p/merge 3"], key="main-bash")

    def test_block_lane_clone_flags(self):
        self.blocked(["gh repo clone o/r /tmp/r -- -c core.hooksPath=/dev/null",
                      "git clone -c core.hooksPath=/dev/null https://x/r /tmp/r",
                      "git clone --template=/tmp/t https://x/r /tmp/r", "git clone --config=alias.p=push https://x/r"])
        self.allowed(["gh repo clone o/r /tmp/r", "gh repo clone o/r /tmp/r -- --depth 1",
                      "git clone --depth 1 https://x/r /tmp/r"])


if __name__ == "__main__":
    unittest.main()
