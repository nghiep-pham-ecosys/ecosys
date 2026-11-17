"""Tests for tools/ship/stack-merge. Synthetic data only (repo acme/demo).

The CLI tests run the real executable, which runs the real tools/ship/merge,
with a stateful fake gh first on PATH. The fake behaves like GitHub where it
matters: a merge with --delete-branch closes every open PR based on the
deleted branch, update-branch moves the head and reruns the checks.

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
STACK_MERGE = os.path.join(SHIP, "stack-merge")
sys.path.insert(0, SHIP)

import _shiplib  # noqa: E402
import _stacklib as lib  # noqa: E402

REPO = "acme/demo"


def sha(n, gen=0):
    return f"{n:04d}{gen:04d}".ljust(40, "a")


def green():
    return [
        {"__typename": "CheckRun", "name": "ci-result", "workflowName": "ci", "status": "COMPLETED",
         "conclusion": "SUCCESS", "startedAt": "2026-01-01T09:00:00Z", "completedAt": "2026-01-01T09:01:00Z"},
        {"__typename": "CheckRun", "name": "pr-title", "workflowName": "pr-title", "status": "COMPLETED",
         "conclusion": "SUCCESS", "startedAt": "2026-01-01T09:00:00Z", "completedAt": "2026-01-01T09:01:00Z"},
    ]


def red():
    checks = green()
    checks[0] = dict(checks[0], conclusion="FAILURE")
    return checks


def pending():
    checks = green()
    checks[0] = dict(checks[0], status="IN_PROGRESS", conclusion="")
    return checks


def make_pr(n, base, **over):
    data = {
        "number": n,
        "title": f"feat: step {n}",
        "url": f"https://github.com/{REPO}/pull/{n}",
        "state": "OPEN",
        "isDraft": False,
        "baseRefName": base,
        "headRefName": f"feat/{n}-step",
        "headRefOid": sha(n),
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
        "statusCheckRollup": green(),
    }
    data.update(over)
    return data


def stack(*numbers):
    """A clean stack: the first PR on main, each next one on the branch before it."""
    prs = {}
    base = "main"
    for n in numbers:
        prs[str(n)] = make_pr(n, base)
        base = prs[str(n)]["headRefName"]
    return prs


FAKE_GH = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys
    d = os.environ["FAKE_GH_DIR"]
    path = os.path.join(d, "state.json")
    args = sys.argv[1:]
    with open(os.path.join(d, "calls.log"), "a") as f:
        f.write(json.dumps(args) + "\\n")
    with open(path) as f:
        st = json.load(f)
    prs = st["prs"]
    CONTROL = ("conflict_on_update", "checks_after_update")

    def save():
        with open(path, "w") as f:
            json.dump(st, f)

    def out(obj):
        sys.stdout.write(json.dumps(obj))

    def fail(msg, code=1):
        sys.stderr.write(msg + "\\n")
        sys.exit(code)

    def opt(flag):
        return args[args.index(flag) + 1]

    if args[:2] == ["repo", "view"]:
        out({"nameWithOwner": st["repo"]})
    elif args[:2] == ["pr", "view"]:
        pr = prs.get(args[2])
        if pr is None:
            fail("GraphQL: Could not resolve to a PullRequest")
        out({k: v for k, v in pr.items() if k not in CONTROL})
    elif args[:2] == ["pr", "merge"]:
        pr = prs[args[2]]
        if pr["state"] != "OPEN" or opt("--match-head-commit") != pr["headRefOid"]:
            fail("Head branch was modified")
        pr["state"] = "MERGED"
        pr["mergeCommit"] = {"oid": "c" * 40}
        if "--delete-branch" in args:
            st["deleted"].append(pr["headRefName"])
            for other in prs.values():
                if other["state"] == "OPEN" and other["baseRefName"] == pr["headRefName"]:
                    other["state"] = "CLOSED"
        save()
    elif args[:3] == ["api", "-X", "PATCH"]:
        n = args[3].rsplit("/", 1)[1]
        base = opt("-f").split("=", 1)[1]
        if base in st["deleted"]:
            fail("gh: Validation Failed (HTTP 422)")
        prs[n]["baseRefName"] = base
        save()
        out({"number": int(n), "base": {"ref": base}})
    elif args[:3] == ["api", "-X", "PUT"] and args[3].endswith("/update-branch"):
        n = args[3].split("/")[-2]
        pr = prs[n]
        if opt("-f") != "expected_head_sha=" + pr["headRefOid"]:
            fail("gh: expected_head_sha does not match (HTTP 422)")
        if pr.get("conflict_on_update"):
            fail("gh: merge conflict between base and head (HTTP 422)")
        pr["headRefOid"] = pr["headRefOid"][:4] + "0001" + pr["headRefOid"][8:]
        pr["statusCheckRollup"] = pr.get("checks_after_update", pr["statusCheckRollup"])
        save()
        out({"message": "Updating pull request branch.", "url": "https://example.invalid"})
    else:
        fail("unexpected gh call: %r" % args, 9)
""")


class CliTest(unittest.TestCase):
    """Runs tools/ship/stack-merge (and through it tools/ship/merge) against the fake gh."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        stub = os.path.join(self.dir, "gh")
        with open(stub, "w") as f:
            f.write(FAKE_GH)
        os.chmod(stub, os.stat(stub).st_mode | stat.S_IXUSR)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, prs, *numbers, extra=()):
        with open(os.path.join(self.dir, "state.json"), "w") as f:
            json.dump({"repo": REPO, "prs": prs, "deleted": []}, f)
        env = dict(os.environ, FAKE_GH_DIR=self.dir,
                   PATH=self.dir + os.pathsep + os.environ.get("PATH", ""))
        proc = subprocess.run(
            [sys.executable, STACK_MERGE, *map(str, numbers), "--repo", REPO, "--wait-seconds", "0",
             "--poll-seconds", "0.01", "--check-timeout", "5", *extra],
            capture_output=True, text=True, env=env, timeout=120,
        )
        with open(os.path.join(self.dir, "state.json")) as f:
            state = json.load(f)
        calls = []
        log = os.path.join(self.dir, "calls.log")
        if os.path.exists(log):
            with open(log) as f:
                calls = [json.loads(line) for line in f]
        return proc, state["prs"], calls

    @staticmethod
    def writes(calls):
        """The calls that change something on GitHub, in order, as short labels."""
        out = []
        for c in calls:
            if c[:2] == ["pr", "merge"]:
                out.append(f"merge {c[2]}")
            elif c[:3] == ["api", "-X", "PATCH"]:
                out.append(f"retarget {c[3].rsplit('/', 1)[1]} {c[5].split('=', 1)[1]}")
            elif c[:3] == ["api", "-X", "PUT"]:
                out.append(f"update {c[3].split('/')[-2]}")
        return out

    def test_three_pr_stack_merged_in_order(self):
        proc, prs, calls = self.cli(stack(41, 42, 43), 41, 42, 43)
        text = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, text)
        self.assertEqual([prs[n]["state"] for n in ("41", "42", "43")], ["MERGED"] * 3)
        self.assertEqual(self.writes(calls), [
            "retarget 42 main", "merge 41", "update 42",
            "retarget 43 main", "merge 42", "update 43",
            "merge 43",
        ])
        self.assertIn("VERDICT: MERGED acme/demo stack #41 #42 #43", text)
        # Every merge pinned the head that its checks were read on.
        merges = [c for c in calls if c[:2] == ["pr", "merge"]]
        self.assertEqual(merges[1][merges[1].index("--match-head-commit") + 1], sha(42)[:4] + "0001" + sha(42)[8:])

    def test_without_retarget_github_closes_the_next_pr(self):
        # The fake reproduces the bug the tool exists for: a plain merge of the
        # bottom PR closes the PR above it.
        prs = stack(41, 42)
        with open(os.path.join(self.dir, "state.json"), "w") as f:
            json.dump({"repo": REPO, "prs": prs, "deleted": []}, f)
        env = dict(os.environ, FAKE_GH_DIR=self.dir,
                   PATH=self.dir + os.pathsep + os.environ.get("PATH", ""))
        subprocess.run([sys.executable, os.path.join(SHIP, "merge"), "41", "--repo", REPO,
                        "--wait-seconds", "0"], capture_output=True, text=True, env=env, timeout=60)
        with open(os.path.join(self.dir, "state.json")) as f:
            self.assertEqual(json.load(f)["prs"]["42"]["state"], "CLOSED")

    def test_stops_on_refused_merge_and_restores_the_stack(self):
        prs = stack(41, 42, 43)
        prs["41"]["statusCheckRollup"] = red()
        proc, prs, calls = self.cli(prs, 41, 42, 43)
        text = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 1, text)
        self.assertIn("VERDICT: REFUSED acme/demo#41", text)  # from tools/ship/merge
        self.assertIn("VERDICT: STOPPED acme/demo stack", text)
        self.assertEqual(self.writes(calls), ["retarget 42 main", "retarget 42 feat/41-step"])
        self.assertEqual([prs[n]["state"] for n in ("41", "42", "43")], ["OPEN"] * 3)
        self.assertEqual(prs["42"]["baseRefName"], "feat/41-step")
        self.assertIn("left: #41, #42, #43", text)

    def test_stops_on_update_branch_conflict(self):
        prs = stack(41, 42, 43)
        prs["42"]["conflict_on_update"] = True
        proc, prs, calls = self.cli(prs, 41, 42, 43)
        text = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 1, text)
        self.assertEqual(self.writes(calls), ["retarget 42 main", "merge 41", "update 42"])
        self.assertEqual(prs["41"]["state"], "MERGED")
        self.assertEqual((prs["42"]["state"], prs["42"]["baseRefName"]), ("OPEN", "main"))
        self.assertEqual((prs["43"]["state"], prs["43"]["baseRefName"]), ("OPEN", "feat/42-step"))
        self.assertIn("merge conflict between base and head", text)
        self.assertIn("merged: #41", text)
        self.assertIn("left: #42 (retargeted to main), #43", text)
        self.assertIn("tools/ship/stack-merge --repo acme/demo 42 43", text)

    def test_stops_on_red_check_after_update(self):
        prs = stack(41, 42)
        prs["42"]["checks_after_update"] = red()
        proc, prs, calls = self.cli(prs, 41, 42)
        text = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 1, text)
        self.assertEqual(self.writes(calls), ["retarget 42 main", "merge 41", "update 42"])
        self.assertEqual(prs["42"]["state"], "OPEN")
        self.assertIn("red checks on #42", text)

    def test_stops_when_checks_stay_pending(self):
        prs = stack(41, 42)
        prs["42"]["checks_after_update"] = pending()
        proc, _, calls = self.cli(prs, 41, 42, extra=("--check-timeout", "0.3"))
        text = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 1, text)
        self.assertIn("timed out after 0.3 s", text)
        self.assertNotIn("merge 42", self.writes(calls))

    def test_refuses_a_list_that_is_not_a_stack(self):
        cases = {
            "first not on main": dict(stack(41, 42), **{"41": make_pr(41, "develop")}),
            "gap in the chain": dict(stack(41, 42), **{"42": make_pr(42, "feat/other")}),
            "closed PR": dict(stack(41, 42), **{"42": make_pr(42, "feat/41-step", state="CLOSED")}),
            "draft PR": dict(stack(41, 42), **{"42": make_pr(42, "feat/41-step", isDraft=True)}),
        }
        for label, prs in cases.items():
            with self.subTest(label):
                proc, _, calls = self.cli(prs, 41, 42)
                text = proc.stdout + proc.stderr
                self.assertEqual(proc.returncode, 1, text)
                self.assertIn("not a stack to merge in this order", text)
                self.assertEqual(self.writes(calls), [])

    def test_accepts_a_pr_already_retargeted_to_main(self):
        prs = stack(41, 42)
        prs["42"]["baseRefName"] = "main"
        proc, prs, calls = self.cli(prs, 41, 42)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self.writes(calls), ["merge 41", "update 42", "merge 42"])

    def test_dry_run_changes_nothing(self):
        proc, prs, calls = self.cli(stack(41, 42, 43), 41, 42, 43, extra=("--dry-run",))
        text = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, text)
        self.assertEqual(self.writes(calls), [])
        self.assertIn("would retarget #42 to main", text)
        self.assertIn("VERDICT: DRY-RUN acme/demo#41", text)  # from tools/ship/merge
        self.assertIn("VERDICT: DRY-RUN acme/demo stack", text)

    def test_rejects_bad_arguments(self):
        for argv in (["0"], ["4", "4"], ["4", "--poll-seconds", "0"]):
            with self.subTest(argv=argv):
                proc = subprocess.run([sys.executable, STACK_MERGE, *argv], capture_output=True, text=True)
                self.assertEqual(proc.returncode, 2)


class FakeRunner:
    """In-process gh: each `pr view` of a PR pops its next payload (the last repeats)."""

    def __init__(self, views):
        self.views = {n: list(v) for n, v in views.items()}
        self.calls = []

    def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["pr", "view"]:
            queue = self.views[int(args[2])]
            payload = queue.pop(0) if len(queue) > 1 else queue[0]
            return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
        if args[:3] == ["api", "-X", "PATCH"]:
            base = args[5].split("=", 1)[1]
            return subprocess.CompletedProcess(args, 0, json.dumps({"base": {"ref": base}}), "")
        if args[:3] == ["api", "-X", "PUT"]:
            return subprocess.CompletedProcess(args, 0, "{}", "")
        raise AssertionError(f"unexpected gh call: {args}")


class Clock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class WaitTest(unittest.TestCase):
    def wait(self, views, timeout=100.0, poll=10.0, required=("ci-result", "pr-title")):
        runner = FakeRunner({42: views})
        clock = Clock()
        lines = []
        pr = lib.wait_for_green(runner, clock.sleep, clock, 42, REPO, required, sha(42),
                                timeout, poll, lines.append)
        return pr, clock, lines

    def test_waits_for_head_to_move_then_for_checks(self):
        new = sha(42, 1)
        views = [make_pr(42, "main"), make_pr(42, "main", headRefOid=new, statusCheckRollup=[]),
                 make_pr(42, "main", headRefOid=new, statusCheckRollup=pending()),
                 make_pr(42, "main", headRefOid=new)]
        pr, clock, lines = self.wait(views)
        self.assertEqual(pr.sha, new)
        self.assertEqual(clock.sleeps, [10.0, 10.0, 10.0])
        self.assertTrue(any("waiting for update-branch" in line for line in lines))
        self.assertTrue(any("no checks yet" in line for line in lines))

    def test_missing_required_check_is_not_green(self):
        only_ci = green()[:1]
        views = [make_pr(42, "main", headRefOid=sha(42, 1), statusCheckRollup=only_ci)]
        with self.assertRaises(lib.Stop) as ctx:
            self.wait(views, timeout=25.0)
        self.assertIn("not reported yet: pr-title", ctx.exception.reason)

    def test_timeout_is_bounded_and_sleeps_between_reads(self):
        with self.assertRaises(lib.Stop) as ctx:
            self.wait([make_pr(42, "main")], timeout=25.0, poll=10.0)
        self.assertIn("timed out after 25 s", ctx.exception.reason)
        self.assertIn("waiting for update-branch", ctx.exception.reason)

    def test_red_check_stops_at_once(self):
        views = [make_pr(42, "main", headRefOid=sha(42, 1), statusCheckRollup=red())]
        with self.assertRaises(lib.Stop) as ctx:
            self.wait(views)
        self.assertIn("red checks on #42", ctx.exception.reason)

    def test_conflict_after_update_stops(self):
        views = [make_pr(42, "main", headRefOid=sha(42, 1), mergeable="CONFLICTING")]
        with self.assertRaises(lib.Stop) as ctx:
            self.wait(views)
        self.assertIn("merge conflicts", ctx.exception.reason)

    def test_closed_pr_stops(self):
        with self.assertRaises(lib.Stop):
            self.wait([make_pr(42, "main", state="CLOSED")])


class StackInProcessTest(unittest.TestCase):
    def test_merge_failure_keeps_retarget_and_returns_merge_code(self):
        # Exit 3 means the merge may have happened: do not put the old base back.
        runner = FakeRunner({41: [make_pr(41, "main")], 42: [make_pr(42, "feat/41-step")]})
        out = io.StringIO()
        code = lib.stack_merge([41, 42], repo=REPO, runner=runner,
                               merge_runner=lambda *a: lib.EXIT_MERGE_FAILED, out=out,
                               sleep=lambda s: None)
        self.assertEqual(code, lib.EXIT_MERGE_FAILED)
        patches = [c for c in runner.calls if c[:3] == ["api", "-X", "PATCH"]]
        self.assertEqual(len(patches), 1)
        self.assertIn("VERDICT: FAILED", out.getvalue())

    def test_merge_runner_gets_the_merge_tool_settings(self):
        seen = []

        def merge_runner(number, repo, required, wait, dry_run, out):
            seen.append((number, repo, list(required), wait, dry_run))
            return lib.EXIT_OK

        runner = FakeRunner({41: [make_pr(41, "main")]})
        code = lib.stack_merge([41], repo=REPO, required=["build"], wait_seconds=7,
                               runner=runner, merge_runner=merge_runner, out=io.StringIO())
        self.assertEqual(code, lib.EXIT_OK)
        self.assertEqual(seen, [(41, REPO, ["build"], 7, False)])

    def test_gh_error_after_a_merge_reports_it_as_merged(self):
        calls = {"n": 0}
        base = FakeRunner({41: [make_pr(41, "main")], 42: [make_pr(42, "feat/41-step")]})

        def runner(args):
            if args[:2] == ["pr", "view"] and args[2] == "42":
                calls["n"] += 1
                if calls["n"] == 3:  # the read after the merge of #41
                    return subprocess.CompletedProcess(args, 1, "", "HTTP 502")
            return base(args)

        out = io.StringIO()
        code = lib.stack_merge([41, 42], repo=REPO, runner=runner,
                               merge_runner=lambda *a: lib.EXIT_OK, out=out)
        self.assertEqual(code, lib.EXIT_ERROR)
        self.assertIn("merged: #41", out.getvalue())
        self.assertIn("left: #42 (retargeted to main)", out.getvalue())

    def test_merge_tool_path_is_the_sibling_executable(self):
        self.assertEqual(lib.MERGE_TOOL, os.path.join(SHIP, "merge"))
        self.assertEqual(lib.EXIT_STOPPED, _shiplib.EXIT_REFUSED)


if __name__ == "__main__":
    unittest.main()
