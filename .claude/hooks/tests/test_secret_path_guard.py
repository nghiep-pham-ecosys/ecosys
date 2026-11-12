import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _harness import HOME, LANE, PROJECT, HookCase  # noqa: E402

DENYLIST = HOME + "/.config/nghiep-pham-ecosys/denylist.txt"


def read(path):
    return {"tool_input": {"file_path": path}}


class SecretPathFileToolTest(HookCase):
    HOOK = "secret-path-guard.py"

    # --- required pair
    def test_block_read_env(self):
        self.assertBlocked("main-read", contains=".env", **read(PROJECT + "/.env"))

    def test_pass_read_env_example(self):
        self.assertAllowed("main-read", **read(PROJECT + "/.env.example"))

    # --- edge cases
    def test_block_env_variants(self):
        for p in (".env.local", "projects/lab-to-prod/.env.production", LANE + "/.env"):
            with self.subTest(p=p):
                self.assertBlocked("main-read", **read(p))

    def test_pass_env_lookalikes(self):
        for p in (".envrc.sample", "docs/env.md", ".environment", "src/dotenv.py", "x.env.example.md"):
            with self.subTest(p=p):
                self.assertAllowed("main-read", **read(p))

    def test_block_keys(self):
        for p in ("certs/server.pem", "secrets/deploy.KEY", HOME + "/keys/id.key"):
            with self.subTest(p=p):
                self.assertBlocked("main-read", **read(p))

    def test_pass_key_lookalikes(self):
        for p in ("docs/keyboard.md", "src/pem_utils.py", "keys.txt"):
            with self.subTest(p=p):
                self.assertAllowed("main-read", **read(p))

    def test_block_sops_config_dir(self):
        self.assertBlocked("main-read", **read("~/.config/sops/age/keys.txt"))
        self.assertBlocked("main-read", **read(HOME + "/.config/sops/age/keys.txt"))

    def test_pass_read_encrypted_sops_file(self):
        # Ciphertext is fine to read; decryption is what is blocked.
        self.assertAllowed("main-read", **read(PROJECT + "/private/vault/profile/private.sops.yaml"))

    def test_block_denylist_all_file_tools(self):
        for tool in ("Read", "Edit", "Write"):
            with self.subTest(tool=tool):
                self.assertBlocked("main-read", tool_name=tool, tool_input={"file_path": DENYLIST})

    def test_block_write_env_from_subagent(self):
        self.assertBlocked("sub-write", tool_input={"file_path": LANE + "/.env", "content": "A=1\n"})

    def test_pass_subagent_write(self):
        self.assertAllowed("sub-write", tool_input={"file_path": LANE + "/docs/notes.md", "content": "Acme\n"})

    def test_grep_tool_if_matcher_is_widened(self):
        self.assertBlocked("main-read", tool_name="Grep", tool_input={"pattern": "x", "path": HOME + "/.config/sops"})
        self.assertBlocked("main-read", tool_name="Grep", tool_input={"pattern": "x", "glob": ".env*"})
        self.assertAllowed("main-read", tool_name="Grep", tool_input={"pattern": "x", "glob": "*.py"})


class SecretPathBashTest(HookCase):
    HOOK = "secret-path-guard.py"

    # --- required pair
    def test_block_cat_env(self):
        self.assertBlocked("main-bash", command="cat .env")

    def test_pass_cat_env_example(self):
        self.assertAllowed("main-bash", command="cat .env.example")

    # --- edge cases
    def test_block_env_forms(self):
        for cmd in (
            "source .env.local",
            "cat < .env",
            "docker run --env-file=.env acme/app",
            "grep TOKEN .env*",
            "cp .env.example .env",
            "cat projects/lab-to-prod/.env | head",
            "f=.env; cat $f",
            "bash -c 'cat .env'",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("main-bash", command=cmd)

    def test_pass_text_mentions(self):
        for cmd in (
            'git commit -m "docs: never read .env files"',
            "echo '.env*' >> .gitignore",
            "grep -rn dotenv src/",
            "ls -la",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed("main-bash", command=cmd)

    def test_block_echo_redirect_into_env(self):
        self.assertBlocked("main-bash", command="echo TOKEN=x > .env")

    def test_block_keys(self):
        for cmd in ("openssl x509 -in cert.pem -text", "cat *.pem", "ssh-keygen -y -f deploy.key"):
            with self.subTest(cmd=cmd):
                self.assertBlocked("main-bash", command=cmd)

    def test_block_sops_dir_expansions(self):
        for cmd in (
            "cat ~/.config/sops/age/keys.txt",
            'cat "$HOME"/.config/sops/age/keys.txt',
            "cat ${HOME}/.config/sops/age/keys.txt",
            "ls " + HOME + "/.config/sops",
            "SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt true",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("main-bash", command=cmd)

    def test_block_decryption(self):
        for cmd in (
            "sops -d private/vault/profile/private.sops.yaml",
            "sops --decrypt x.sops.json",
            "sops decrypt x.sops.yaml",
            "sops exec-env x.sops.env 'printenv'",
            "sops private/vault/profile/private.sops.yaml",
            "age -d -i id.txt secret.age",
            "age --decrypt secret.age",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("main-bash", command=cmd)

    def test_pass_encryption_and_ciphertext_reads(self):
        for cmd in (
            "sops -e -i private/vault/profile/private.sops.yaml",
            "sops --version",
            "age -r age1examplepublickey -o out.age in.txt",
            "git diff private/vault/profile/private.sops.yaml",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed("main-bash", command=cmd)

    def test_block_denylist_in_bash(self):
        for cmd in (
            "cat ~/.config/nghiep-pham-ecosys/denylist.txt",
            "grep -c -f ~/.config/nghiep-pham-ecosys/denylist.txt README.md",
            "ls ~/.config/nghiep-pham-ecosys",
            "cat ~/.config/nghiep-pham-ecosys/*",
            "tools/ws/denylist-scan README.md; cat ~/.config/nghiep-pham-ecosys/denylist.txt",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("main-bash", command=cmd)

    def test_block_globs_in_directory_components(self):
        for cmd in (
            "cat ~/.config/nghiep-*/denylist.txt",
            "cat ~/.config/*/denylist.txt",
            "cat ~/.config/nghiep-pham-ecosy?/deny*",
            "cat ~/.config/[n]ghiep-pham-ecosys/denylist.txt",
            "ls ~/.config/nghiep-*",
            "cat ~/.config/s*/age/keys.txt",
            "cat $HOME/.config/so?s/age/*",
            "cat ~/.config/{sops,git}/age/keys.txt",
            "cat ~/.config/{nghiep-pham-ecosys,x}/denylist.txt",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("main-bash", command=cmd)

    def test_pass_globs_elsewhere_in_config(self):
        for cmd in ("ls ~/.config/git/*", "cat ~/.config/gh/*.yml", "ls ~/.conf*"):
            with self.subTest(cmd=cmd):
                self.assertAllowed("main-bash", command=cmd)

    def test_glob_tool_and_grep_glob_in_directory(self):
        self.assertBlocked("main-read", tool_name="Grep",
                           tool_input={"pattern": "x", "path": HOME + "/.config", "glob": "nghiep-*/denylist.txt"})
        self.assertBlocked("main-read", **read(HOME + "/.config/nghiep-*/denylist.txt"))

    def test_block_paths_inside_quoted_code(self):
        for cmd in (
            "python3 -c \"open('" + DENYLIST + "')\"",
            "python3 -c \"print(open('/home/nghiep/.config/nghiep-pham-ecosys/denylist.txt').read())\"",
            "python3 -c \"import os; print(open(os.environ['HOME'] + '/.config/sops/age/keys.txt').read())\"",
            "python3 -c \"import pathlib; pathlib.Path('~/.config/sops/age/keys.txt').expanduser().read_text()\"",
            "python3 -c 'print(open(\".env\").read())'",
            "node -e \"console.log(require('fs').readFileSync('.env.local', 'utf8'))\"",
            "python3 -c \"from dotenv import dotenv_values; print(dotenv_values('projects/x/.env'))\"",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked("main-bash", command=cmd)

    def test_block_paths_in_interpreter_heredoc(self):
        self.assertBlocked("main-bash", command="python3 <<'PY'\nprint(open('" + DENYLIST + "').read())\nPY")
        self.assertBlocked("main-bash", command="python3 - <<PY\nimport os\nprint(open('.env').read())\nPY")

    def test_pass_code_near_misses(self):
        for cmd in (
            "python3 -c \"print(open('.env.example').read())\"",
            "python3 -c \"import os; print(os.environ.get('HOME'))\"",
            "python3 <<'PY'\nprint(open('.env.example').read())\nPY",
            'git commit -m "fix: stop reading .env (and ~/.config/sops) in tests"',
            "gh pr create --title 'docs: never read .env' --body \"Explains why ('.env' stays local)\"",
            "echo '.env*' >> .gitignore",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed("main-bash", command=cmd)

    # --- here-documents: bodies are data unless an interpreter reads them
    def test_pass_heredoc_bodies_that_mention_secrets(self):
        for cmd in (
            "git commit -F - <<'MSG'\nfeat: add guard\n\nNever read .env; only .env.example.\nMSG",
            "git commit -m \"$(cat <<'EOF'\nfix: stop reading .env\n\nRefs ecosys#3\nEOF\n)\"",
            "cat > docs/x.md <<'E'\nNever commit .env or server.pem\nE",
            "cat > docs/y.md <<\"E\"\nKeys live in ~/.config/sops/age/keys.txt\nE",
            "cat > docs/z.md <<E\ncat ~/.config/nghiep-pham-ecosys/denylist.txt is blocked\nE",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed("main-bash", command=cmd)

    def test_heredoc_redirect_targets_still_checked(self):
        self.assertBlocked("main-bash", command="cat > .env <<'E'\nTOKEN=x\nE")
        self.assertBlocked("main-bash", command="cat <<'E' > deploy.key\nx\nE")
        self.assertBlocked("main-bash", command="cat > docs/x.md <<'E'\nok\nE\ncat .env")

    def test_heredoc_fed_to_shell_is_checked(self):
        self.assertBlocked("main-bash", command="bash <<'X'\ncat .env\nX")
        self.assertBlocked("main-bash", command="cat <<'X' | sh\ncat ~/.config/sops/age/keys.txt\nX")

    def test_pass_denylist_scanner(self):
        for cmd in (
            "tools/ws/denylist-scan --list ~/.config/nghiep-pham-ecosys/denylist.txt README.md",
            "python3 tools/ws/denylist-scan ~/.config/nghiep-pham-ecosys/denylist.txt",
            "just denylist ~/.config/nghiep-pham-ecosys/denylist.txt",
            "just ci",
        ):
            with self.subTest(cmd=cmd):
                self.assertAllowed("main-bash", command=cmd)

    def test_scanner_exemption_does_not_cover_env(self):
        self.assertBlocked("main-bash", command="tools/ws/denylist-scan .env")

    def test_relative_paths_resolve_against_cwd(self):
        self.assertBlocked("main-bash", command="cat denylist.txt", cwd=HOME + "/.config/nghiep-pham-ecosys")
        self.assertBlocked("main-bash", command="cat age/keys.txt", cwd=HOME + "/.config/sops")


class FailClosedTest(HookCase):
    def test_bad_json_blocks_every_hook(self):
        from _harness import run_raw

        for hook in ("ship-guard.py", "secret-path-guard.py", "worktree-guard.py"):
            with self.subTest(hook=hook):
                code, err = run_raw(hook, "not json")
                self.assertEqual(code, 2)
                self.assertIn("not valid JSON", err)

    def test_hooks_are_executable_python(self):
        from _harness import HOOKS_DIR

        for hook in ("ship-guard.py", "secret-path-guard.py", "worktree-guard.py"):
            with self.subTest(hook=hook):
                path = os.path.join(HOOKS_DIR, hook)
                self.assertTrue(os.access(path, os.X_OK), f"{hook} must be executable")
                with open(path, encoding="utf-8") as fh:
                    self.assertEqual(fh.readline().strip(), "#!/usr/bin/env python3")


if __name__ == "__main__":
    unittest.main()
