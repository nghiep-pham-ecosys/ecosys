import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _harness import LANE, PROJECT, HookCase  # noqa: E402


class ShipGuardLaneTest(HookCase):
    HOOK = "ship-guard.py"

    # --- required pair: one block case, one near-miss pass case
    def test_block_push_from_wt_cwd(self):
        self.assertBlocked("sub-wt-bash", command="git push origin feat/3-x", contains="git push")

    def test_pass_status_from_wt_cwd(self):
        self.assertAllowed("sub-wt-bash", command="git status -sb")

    # --- lane detection
    def test_subagent_at_root_is_lane(self):
        # Captured payloads: subagent cwd is the root, not the worktree.
        self.assertBlocked("sub-bash", command="git push")

    def test_main_cd_into_wt_is_lane(self):
        self.assertBlocked("main-bash", command=f"cd {LANE} && git push -u origin HEAD")

    def test_main_git_dash_c_into_wt_is_lane(self):
        self.assertBlocked("main-bash", command=f"git -C {LANE} push")

    def test_main_cd_relative_into_wt_is_lane(self):
        self.assertBlocked("main-bash", command="cd .tmp-session/wt/s1-lane-a; git reset --hard HEAD~1")

    def test_main_push_outside_wt_passes(self):
        # The orchestrator may push; permissions ask first.
        self.assertAllowed("main-bash", command="git push origin docs/1-readme")

    def test_project_dir_fallback_from_cwd(self):
        self.assertBlocked("sub-wt-bash", command="git push", project_env=False)

    # --- lane block list
    def test_block_reset_hard(self):
        self.assertBlocked("sub-bash", command="git reset --hard origin/main")

    def test_pass_reset_soft(self):
        self.assertAllowed("sub-bash", command="git reset --soft HEAD~1")

    def test_block_clean_force_variants(self):
        for cmd in ("git clean -fd", "git clean -xfd", "git clean --force", "git clean -f"):
            with self.subTest(cmd=cmd):
                self.assertBlocked("sub-bash", command=cmd)

    def test_pass_clean_dry_run(self):
        self.assertAllowed("sub-bash", command="git clean -nd")

    def test_block_no_verify(self):
        self.assertBlocked("sub-bash", command='git commit --no-verify -m "feat: x"', contains="--no-verify")

    def test_block_commit_dash_n(self):
        for cmd in ('git commit -n -m "x"', 'git commit -anm "x"'):
            with self.subTest(cmd=cmd):
                self.assertBlocked("sub-bash", command=cmd)

    def test_pass_commit_message_with_n_text(self):
        self.assertAllowed("sub-bash", command='git commit -m "-n is not a flag here" -m "Refs ecosys#3"')

    def test_block_hookspath_override(self):
        self.assertBlocked("sub-bash", command='git -c core.hooksPath=/dev/null commit -m "x"')

    def test_block_gh_pr_create_and_workflow_run(self):
        for cmd in ('gh pr create --fill', "gh workflow run ci.yml", "gh issue create -t x -b y", "gh run rerun 42"):
            with self.subTest(cmd=cmd):
                self.assertBlocked("sub-bash", command=cmd)

    def test_pass_gh_read_commands(self):
        for cmd in ("gh pr view 3 --json state", "gh pr checks 3", "gh run list -L 5", "gh search repos x"):
            with self.subTest(cmd=cmd):
                self.assertAllowed("sub-bash", command=cmd)

    def test_block_gh_api_writes(self):
        for cmd in (
            "gh api -X POST repos/example/acme/issues -f title=x",
            "gh api --method=PATCH repos/example/acme",
            "gh api -XDELETE repos/example/acme/git/refs/heads/x",
            "gh api repos/example/acme/issues -f title=x",
            "gh api repos/example/acme/labels -F name=bug",
            "gh api repos/example/acme/issues --input body.json",
            "gh api graphql -f query='mutation { addStar(input:{}) { clientMutationId } }'",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("sub-bash", command=cmd)

    def test_pass_gh_api_reads(self):
        for cmd in (
            "gh api repos/example/acme/pulls/3",
            "gh api -X GET search/issues -f q=repo:example/acme",
            "gh api graphql -f query='query { viewer { login } }'",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed("sub-bash", command=cmd)

    def test_block_lane_running_merge_tool(self):
        self.assertBlocked("sub-bash", command="tools/ship/merge 12")

    def test_block_lane_merge_tool_any_form(self):
        for cmd in (
            "python3 tools/ship/merge 3",
            f"python3 {PROJECT}/tools/ship/merge 3",
            f"/usr/bin/python3 -u {LANE}/tools/ship/merge 3",
            "bash tools/ship/merge 3",
            "sh ./tools/ship/merge 3",
            "env FOO=1 tools/ship/merge 3",
            "env python3 tools/ship/merge 3",
            "./tools/ship/../ship/merge 3",
            "uv run tools/ship/merge 3",
            '"$CLAUDE_PROJECT_DIR"/tools/ship/merge 3',
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("sub-bash", command=cmd, contains="merge")

    def test_block_merge_tool_from_wt_cwd_and_relative(self):
        self.assertBlocked("sub-wt-bash", command="python3 tools/ship/merge 3")
        self.assertBlocked("sub-bash", command="python3 merge 3", cwd=PROJECT + "/tools/ship")

    def test_pass_lane_touching_merge_tool_source(self):
        # A lane may edit, stage and inspect the merge tool; it may not run it.
        for cmd in (
            "git add tools/ship/merge",
            "git diff -- tools/ship/merge",
            "cat tools/ship/merge",
            "grep -n def tools/ship/merge",
            "chmod +x tools/ship/merge",
            "python3 -m unittest tools/ship/tests/test_merge.py",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed("sub-bash", command=cmd)

    # --- git long-option abbreviations (git accepts any unique prefix)
    def test_block_abbreviated_long_options(self):
        for cmd in (
            "git reset --h",
            "git reset --har origin/main",
            "git reset --hard",
            'git commit --no-verif -m "x"',
            'git commit --no-veri -m "x"',
            "git merge --no-verify feat/x",
            "git clean --forc -d",
            "git clean --fo",
            "git clean --force=1",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("sub-bash", command=cmd)

    def test_pass_long_options_that_are_not_prefixes(self):
        for cmd in ("git reset --soft HEAD~1", "git reset --mixed", "git clean --dry-run -d",
                    'git commit --no-edit --amend', "git merge --no-ff feat/x"):
            with self.subTest(cmd=cmd):
                self.assertAllowed("sub-bash", command=cmd)

    # --- git aliases and injected config
    def test_block_git_aliases(self):
        for cmd in (
            "git -c alias.p=push p origin HEAD",
            "git -c Alias.P='!git push' p",
            "git --config-env=alias.p=PUSH_ALIAS p",
            "git --config-env alias.p=PUSH_ALIAS p",
            "git config alias.p push",
            "git config --global alias.p push",
            "git config --local alias.p '!sh -c \"git push\"'",
            "git config set alias.p push",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("sub-bash", command=cmd, contains="alias")

    def test_block_git_config_env_injection(self):
        for cmd in (
            "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.p GIT_CONFIG_VALUE_0=push git p",
            "GIT_CONFIG_KEY_0=core.hooksPath git commit -m x",
            "env GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/dev/null git commit -m x",
            "env -i GIT_CONFIG_PARAMETERS=\"'alias.p'='push'\" git p",
            "export GIT_CONFIG_COUNT=1; git p",
            "sudo GIT_CONFIG_VALUE_0=push git p",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("sub-bash", command=cmd, contains="GIT_CONFIG")

    def test_pass_git_config_text_and_other_keys(self):
        for cmd in (
            'git commit -m "docs: GIT_CONFIG_COUNT=1 is blocked for lanes"',
            "git config user.name Example",
            "GIT_TRACE=1 git status",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed("sub-bash", command=cmd)
        # Reading an alias is harmless but still names alias.*; blocking it is accepted.
        self.assertBlocked("sub-bash", command="git config --get alias.st")

    # --- here-documents
    def test_pass_commit_message_heredocs(self):
        for cmd in (
            "git commit -F - <<'MSG'\nfeat: add guard\n\nLanes never git push; see .env notes.\nMSG",
            "git commit -m \"$(cat <<'EOF'\nfix: stop reading .env\n\ngit push and gh pr merge stay with the orchestrator\nEOF\n)\"",
            "cat > docs/x.md <<'E'\nNever commit .env or server.pem\ngit reset --hard is blocked\nE",
            "cat <<-\tEOF > docs/y.md\n\tgit push\n\tEOF",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed("sub-bash", command=cmd)

    def test_block_heredoc_fed_to_shell(self):
        for cmd in (
            "bash <<'X'\ngit push origin HEAD\nX",
            "sh -s <<X\ngit status\ngit push\nX",
            "cat <<'X' | bash\ngit push\nX",
            "sudo zsh <<\"X\"\ngit reset --hard\nX",
            "bash <<< 'git push'",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("sub-bash", command=cmd)

    def test_commands_after_heredoc_still_checked(self):
        self.assertBlocked("sub-bash", command="cat > a.txt <<'E'\nhello\nE\ngit push")
        # No terminator: the text stays commands (fail closed).
        self.assertBlocked("sub-bash", command="cat <<'E'\ngit push")
        # Arithmetic shift is not a here-document.
        self.assertBlocked("sub-bash", command="echo $((1<<2))\ngit push")

    # --- parsing robustness
    def test_block_hidden_in_chains_and_wrappers(self):
        for cmd in (
            "git status && git push",
            "git status; git push",
            "false || git push",
            "git status\ngit push",
            "env GIT_TRACE=1 git push",
            "timeout 60 git push",
            "bash -c 'git push origin HEAD'",
            'echo "$(git push)"',
            "echo `git push`",
            "( git push )",
            "{ git push; }",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("sub-bash", command=cmd)

    def test_pass_quoted_text_is_not_a_command(self):
        self.assertAllowed("sub-bash", command='git commit -m "docs: explain why lanes never git push"')
        self.assertAllowed("sub-bash", command="echo 'git push is for the orchestrator'")

    def test_unbalanced_quotes_still_checked(self):
        self.assertBlocked("sub-bash", command="git push 'oops")


class ShipGuardEveryoneTest(HookCase):
    HOOK = "ship-guard.py"

    def test_block_raw_gh_pr_merge_main(self):
        self.assertBlocked("main-bash", command="gh pr merge 12 --squash", contains="tools/ship/merge")

    def test_pass_merge_tool_main(self):
        self.assertAllowed("main-bash", command="tools/ship/merge 12")

    def test_block_gh_pr_merge_with_repo_flag(self):
        self.assertBlocked("main-bash", command="gh pr -R example/acme merge 12")

    def test_block_api_merge(self):
        self.assertBlocked("main-bash", command="gh api -X PUT repos/example/acme/pulls/12/merge -f merge_method=squash")

    def test_pass_api_merge_status_read(self):
        self.assertAllowed("main-bash", command="gh api repos/example/acme/pulls/12/merge")

    def test_block_graphql_merges_for_everyone(self):
        for key in ("main-bash", "sub-bash"):
            for cmd in (
                "gh api graphql -f query='mutation { mergePullRequest(input:{pullRequestId:\"PR_x\"}) { clientMutationId } }'",
                "gh api graphql -f query='mutation($id:ID!){ enablePullRequestAutoMerge(input:{pullRequestId:$id}) { clientMutationId } }' -f id=PR_x",
                "gh api graphql --raw-field query='mutation { mergeBranch(input:{repositoryId:\"R\",base:\"main\",head:\"x\"}) { clientMutationId } }'",
                "gh api /graphql -F query='mutation{MERGEPULLREQUEST(input:{}){clientMutationId}}'",
                "gh api graphql -F query=@merge.graphql",
                "gh api graphql -f query=@-",
                "gh api graphql --input query.json",
            ):
                with self.subTest(key=key, cmd=cmd):
                    self.assertBlocked(key, command=cmd)

    def test_pass_graphql_read_main(self):
        self.assertAllowed("main-bash", command="gh api graphql -f query='query { viewer { login } }'")
        # The orchestrator may still send other mutations (permissions ask for POSTs).
        self.assertAllowed("main-bash", command="gh api graphql -f query='mutation { addStar(input:{starrableId:\"x\"}) { clientMutationId } }'")

    def test_block_rest_branch_merge(self):
        self.assertBlocked("main-bash", command="gh api repos/example/acme/merges -f base=main -f head=feat/x")
        self.assertBlocked("main-bash", command="gh api -X POST repos/example/acme/merges --input m.json")

    def test_block_gh_alias_set_and_import(self):
        for key in ("main-bash", "sub-bash"):
            for cmd in ("gh alias set pm 'pr merge --squash'", "gh alias set --shell pm 'gh pr merge $1'",
                        "gh alias import aliases.yml", "gh alias import - < aliases.yml"):
                with self.subTest(key=key, cmd=cmd):
                    self.assertBlocked(key, command=cmd, contains="gh alias")

    def test_pass_gh_alias_list(self):
        self.assertAllowed("main-bash", command="gh alias list")
        self.assertAllowed("sub-bash", command="gh alias list")

    def test_pass_main_writes_outside_lane(self):
        # The orchestrator opens PRs and runs workflows (permissions ask first).
        for cmd in ("gh pr create --fill", "gh workflow run ci.yml", "gh api -X POST repos/example/acme/issues -f title=x"):
            with self.subTest(cmd=cmd):
                self.assertAllowed("main-bash", command=cmd)

    def test_pass_non_bash_tool(self):
        self.assertAllowed("main-read", tool_input={"file_path": PROJECT + "/README.md"})


if __name__ == "__main__":
    unittest.main()
