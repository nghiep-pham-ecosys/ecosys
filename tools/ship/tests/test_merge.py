"""Tests for tools/ship/merge. Synthetic data only (repo acme/demo).

Run: python3 -m unittest discover -s tools/ship/tests -p 'test_*.py'
"""

from __future__ import annotations

import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHIP = os.path.dirname(HERE)
MERGE = os.path.join(SHIP, "merge")
sys.path.insert(0, SHIP)

import _shiplib as lib  # noqa: E402

REPO = "acme/demo"
SHA = "a" * 40
SHA2 = "b" * 40


def run(name, conclusion="SUCCESS", status="COMPLETED", workflow="ci",
        completed="2026-01-01T10:00:00Z"):
    return {
        "__typename": "CheckRun",
        "name": name,
        "workflowName": workflow,
        "status": status,
        "conclusion": "" if status != "COMPLETED" else conclusion,
        "startedAt": "2026-01-01T09:59:00Z",
        "completedAt": completed if status == "COMPLETED" else "0001-01-01T00:00:00Z",
    }


def ctx(name, state="SUCCESS"):
    return {"__typename": "StatusContext", "context": name, "state": state,
            "startedAt": "2026-01-01T09:00:00Z"}


def green():
    return [run("hook-tests"), run("ci-result"), run("pr-title", workflow="pr-title")]


def pr(**over):
    data = {
        "number": 7,
        "title": "docs: example change",
        "url": "https://github.com/acme/demo/pull/7",
        "isDraft": False,
        "state": "OPEN",
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "headRefOid": SHA,
        "baseRefName": "main",
        "statusCheckRollup": green(),
    }
    data.update(over)
    return data


class FakeGh:
    """Stands in for the gh CLI. Each `pr view --json <PR_FIELDS>` call pops
    the next PR payload (the last one repeats)."""

    def __init__(self, views, merge_rc=0, after_state="MERGED", repo=REPO,
                 view_rc=0):
        self.views = list(views)
        self.merge_rc = merge_rc
        self.after_state = after_state
        self.repo = repo
        self.view_rc = view_rc
        self.calls = []

    def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["repo", "view"]:
            return self._ok({"nameWithOwner": self.repo})
        if args[:2] == ["pr", "view"] and args[-1] == lib.PR_FIELDS:
            if self.view_rc:
                return subprocess.CompletedProcess(args, self.view_rc, "", "HTTP 404: Not Found")
            payload = self.views.pop(0) if len(self.views) > 1 else self.views[0]
            return self._ok(payload)
        if args[:2] == ["pr", "view"]:
            return self._ok({"state": self.after_state,
                             "mergeCommit": {"oid": "c" * 40}})
        if args[:2] == ["pr", "merge"]:
            return subprocess.CompletedProcess(
                args, self.merge_rc, "", "" if self.merge_rc == 0 else "head mismatch")
        raise AssertionError(f"unexpected gh call: {args}")

    @staticmethod
    def _ok(obj):
        return subprocess.CompletedProcess([], 0, json.dumps(obj), "")

    @property
    def merge_calls(self):
        return [c for c in self.calls if c[:2] == ["pr", "merge"]]


class MergeTest(unittest.TestCase):
    def go(self, views, **kw):
        gh = kw.pop("gh", None) or FakeGh(views)
        sleeps = []
        out = io.StringIO()
        kw.setdefault("repo", REPO)
        code = lib.merge(7, runner=gh, sleep=sleeps.append, out=out, **kw)
        return code, gh, sleeps, out.getvalue()

    def assertRefused(self, views, fragment, **kw):
        code, gh, _, text = self.go(views, **kw)
        self.assertEqual(code, lib.EXIT_REFUSED, text)
        self.assertIn("VERDICT: REFUSED acme/demo#7", text)
        self.assertIn(fragment, text)
        self.assertEqual(gh.merge_calls, [], "must not merge")
        return text

    # --- happy path -------------------------------------------------------

    def test_happy_path_merges_with_pinned_head(self):
        code, gh, sleeps, text = self.go([pr()])
        self.assertEqual(code, lib.EXIT_OK, text)
        self.assertEqual(sleeps, [20.0])
        self.assertEqual(gh.merge_calls, [[
            "pr", "merge", "7", "--repo", REPO, "--squash",
            "--match-head-commit", SHA, "--delete-branch",
        ]])
        self.assertIn("VERDICT: MERGED acme/demo#7", text)

    def test_reads_checks_twice(self):
        _, gh, _, _ = self.go([pr()])
        views = [c for c in gh.calls if c[:2] == ["pr", "view"] and c[-1] == lib.PR_FIELDS]
        self.assertEqual(len(views), 2)

    def test_custom_wait_seconds(self):
        _, _, sleeps, _ = self.go([pr()], wait_seconds=3)
        self.assertEqual(sleeps, [3])

    def test_resolves_repo_when_not_given(self):
        code, gh, _, _ = self.go([pr()], repo=None)
        self.assertEqual(code, lib.EXIT_OK)
        self.assertEqual(gh.calls[0][:2], ["repo", "view"])
        self.assertIn(REPO, gh.merge_calls[0])

    def test_dry_run_does_not_merge(self):
        code, gh, _, text = self.go([pr()], dry_run=True)
        self.assertEqual(code, lib.EXIT_OK)
        self.assertEqual(gh.merge_calls, [])
        self.assertIn("VERDICT: DRY-RUN", text)
        self.assertIn("--match-head-commit " + SHA, text)

    def test_neutral_and_skipped_optional_checks_pass(self):
        checks = green() + [run("docs-preview", "SKIPPED"), run("lint", "NEUTRAL")]
        code, _, _, text = self.go([pr(statusCheckRollup=checks)])
        self.assertEqual(code, lib.EXIT_OK, text)

    def test_newer_success_supersedes_older_failure(self):
        checks = green() + [run("pr-title", "FAILURE", workflow="pr-title",
                                completed="2026-01-01T08:00:00Z")]
        code, _, _, text = self.go([pr(statusCheckRollup=checks)])
        self.assertEqual(code, lib.EXIT_OK, text)

    def test_status_context_success_counts(self):
        checks = green() + [ctx("external/scan")]
        code, _, _, text = self.go([pr(statusCheckRollup=checks)])
        self.assertEqual(code, lib.EXIT_OK, text)

    def test_mergeable_unknown_retried_once(self):
        code, gh, sleeps, text = self.go([pr(mergeable="UNKNOWN"), pr(), pr()])
        self.assertEqual(code, lib.EXIT_OK, text)
        self.assertEqual(sleeps, [lib.MERGEABLE_RETRY_SECONDS, 20.0])

    # --- refusals ---------------------------------------------------------

    def test_refuses_draft(self):
        self.assertRefused([pr(isDraft=True, mergeStateStatus="DRAFT")], "draft")

    def test_refuses_not_open(self):
        for state in ("CLOSED", "MERGED"):
            with self.subTest(state=state):
                self.assertRefused([pr(state=state)], f"PR is {state}, not OPEN")

    def test_refuses_conflicting(self):
        self.assertRefused([pr(mergeable="CONFLICTING", mergeStateStatus="DIRTY")],
                           "merge conflicts")

    def test_refuses_mergeable_unknown_twice(self):
        text = self.assertRefused([pr(mergeable="UNKNOWN")], "mergeability")
        self.assertNotIn("read 1:", text)

    def test_refuses_failing_check_conclusions(self):
        for conclusion in ("FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED",
                           "STARTUP_FAILURE", "STALE"):
            with self.subTest(conclusion=conclusion):
                checks = green() + [run("gitleaks", conclusion)]
                self.assertRefused([pr(statusCheckRollup=checks)],
                                   f"failing checks: ci / gitleaks ({conclusion})")

    def test_refuses_failing_status_context(self):
        for state in ("FAILURE", "ERROR"):
            with self.subTest(state=state):
                checks = green() + [ctx("external/scan", state)]
                self.assertRefused([pr(statusCheckRollup=checks)], "external/scan")

    def test_refuses_pending_checks(self):
        for status in ("QUEUED", "IN_PROGRESS", "WAITING", "PENDING"):
            with self.subTest(status=status):
                checks = green() + [run("tool-tests", status=status)]
                self.assertRefused([pr(statusCheckRollup=checks)],
                                   f"pending checks: ci / tool-tests ({status})")

    def test_refuses_pending_status_context(self):
        checks = green() + [ctx("external/scan", "PENDING")]
        self.assertRefused([pr(statusCheckRollup=checks)], "pending checks")

    def test_refuses_pending_rerun_even_if_older_run_passed(self):
        checks = green() + [run("pr-title", status="IN_PROGRESS", workflow="pr-title")]
        self.assertRefused([pr(statusCheckRollup=checks)], "pending checks: pr-title / pr-title")

    def test_refuses_no_checks(self):
        self.assertRefused([pr(statusCheckRollup=[])], "no checks at all")

    def test_refuses_missing_required_checks(self):
        checks = [run("hook-tests"), run("pr-title", workflow="pr-title")]
        self.assertRefused([pr(statusCheckRollup=checks)],
                           "required check 'ci-result' is missing")
        checks = [run("hook-tests"), run("ci-result")]
        self.assertRefused([pr(statusCheckRollup=checks)],
                           "required check 'pr-title' is missing")

    def test_refuses_skipped_required_check(self):
        checks = [run("ci-result", "SKIPPED"), run("pr-title", workflow="pr-title")]
        self.assertRefused([pr(statusCheckRollup=checks)],
                           "required check 'ci-result' did not succeed (SKIPPED)")

    def test_custom_required_list(self):
        checks = [run("build")]
        code, _, _, text = self.go([pr(statusCheckRollup=checks)], required=["build"])
        self.assertEqual(code, lib.EXIT_OK, text)
        self.assertRefused([pr(statusCheckRollup=checks)],
                           "required check 'tests' is missing", required=["tests"])

    def test_refuses_head_change_between_reads(self):
        self.assertRefused([pr(), pr(headRefOid=SHA2)], "head moved between reads")

    def test_refuses_new_check_between_reads(self):
        later = green() + [run("late-check")]
        self.assertRefused([pr(), pr(statusCheckRollup=later)],
                           "checks changed between reads: ci / late-check appeared")

    def test_refuses_check_turning_red_between_reads(self):
        later = [run("hook-tests", "FAILURE"), run("ci-result"),
                 run("pr-title", workflow="pr-title")]
        self.assertRefused([pr(), pr(statusCheckRollup=later)], "read 2: failing checks")

    def test_refuses_draft_on_second_read(self):
        self.assertRefused([pr(), pr(isDraft=True)], "read 2: PR is a draft")

    # --- errors -----------------------------------------------------------

    def test_merge_command_failure(self):
        gh = FakeGh([pr()], merge_rc=1, after_state="OPEN")
        code, _, _, text = self.go([], gh=gh)
        self.assertEqual(code, lib.EXIT_MERGE_FAILED)
        self.assertIn("VERDICT: FAILED", text)
        self.assertIn("head mismatch", text)

    def test_merge_error_after_successful_merge_is_merged(self):
        # gh exits 1 when its branch delete races the repo's auto-delete, but the PR is merged.
        gh = FakeGh([pr()], merge_rc=1, after_state="MERGED")
        code, _, _, text = self.go([], gh=gh)
        self.assertEqual(code, lib.EXIT_OK, text)
        self.assertIn("VERDICT: MERGED acme/demo#7", text)
        self.assertIn("ignored", text)

    def test_merge_not_confirmed(self):
        gh = FakeGh([pr()], after_state="OPEN")
        code, _, _, text = self.go([], gh=gh)
        self.assertEqual(code, lib.EXIT_MERGE_FAILED)
        self.assertIn("VERDICT: UNCONFIRMED", text)

    def test_gh_read_error(self):
        gh = FakeGh([pr()], view_rc=1)
        code, _, _, text = self.go([], gh=gh)
        self.assertEqual(code, lib.EXIT_ERROR)
        self.assertIn("VERDICT: ERROR", text)
        self.assertEqual(gh.merge_calls, [])

    def test_bad_repo_argument(self):
        code, gh, _, text = self.go([pr()], repo="not a repo")
        self.assertEqual(code, lib.EXIT_ERROR)
        self.assertEqual(gh.calls, [])


STUB = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    d = os.environ["FAKE_GH_DIR"]
    args = sys.argv[1:]
    with open(os.path.join(d, "calls.log"), "a") as f:
        f.write(json.dumps(args) + "\\n")
    if args[:2] == ["pr", "view"] and "statusCheckRollup" in args[-1]:
        with open(os.path.join(d, "view.json")) as f:
            sys.stdout.write(f.read())
    elif args[:2] == ["pr", "view"]:
        sys.stdout.write(json.dumps({"state": "MERGED", "mergeCommit": {"oid": "c" * 40}}))
    elif args[:2] == ["pr", "merge"]:
        pass
    else:
        sys.stderr.write("unexpected: %r\\n" % args)
        sys.exit(9)
""")


class CliTest(unittest.TestCase):
    """Runs the real executable with a stub gh first on PATH (FAKE_GH_DIR)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        stub = os.path.join(self.dir, "gh")
        with open(stub, "w") as f:
            f.write(STUB)
        os.chmod(stub, os.stat(stub).st_mode | stat.S_IXUSR)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, view, *extra):
        with open(os.path.join(self.dir, "view.json"), "w") as f:
            json.dump(view, f)
        env = dict(os.environ, FAKE_GH_DIR=self.dir,
                   PATH=self.dir + os.pathsep + os.environ.get("PATH", ""))
        proc = subprocess.run(
            [sys.executable, MERGE, "7", "--repo", REPO, "--wait-seconds", "0", *extra],
            capture_output=True, text=True, env=env, timeout=60,
        )
        log = os.path.join(self.dir, "calls.log")
        calls = []
        if os.path.exists(log):
            with open(log) as f:
                calls = [json.loads(line) for line in f]
        return proc, calls

    def test_cli_happy_path(self):
        proc, calls = self.cli(pr())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("VERDICT: MERGED", proc.stdout)
        self.assertIn(["pr", "merge", "7", "--repo", REPO, "--squash",
                       "--match-head-commit", SHA, "--delete-branch"], calls)

    def test_cli_refuses_draft(self):
        proc, calls = self.cli(pr(isDraft=True))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("VERDICT: REFUSED", proc.stdout)
        self.assertFalse([c for c in calls if c[:2] == ["pr", "merge"]])

    def test_cli_dry_run(self):
        proc, calls = self.cli(pr(), "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("VERDICT: DRY-RUN", proc.stdout)
        self.assertFalse([c for c in calls if c[:2] == ["pr", "merge"]])

    def test_cli_rejects_bad_number(self):
        proc = subprocess.run([sys.executable, MERGE, "0"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
