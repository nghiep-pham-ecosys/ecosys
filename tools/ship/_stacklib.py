"""Logic for tools/ship/stack-merge.

A stack is a list of PRs where each one is based on the branch of the one
before it. GitHub closes a PR, it does not retarget it, when its base branch is
deleted by a merge. So the tool merges a stack bottom-up and, for each PR:

1. checks that the PR is open and based on `main`;
2. retargets the next PR to `main` (PATCH /pulls/<n> base=main);
3. runs tools/ship/merge on the PR, with the same --require and --wait-seconds,
   in its own subprocess, so every check of the merge tool applies;
4. updates the next PR's branch on the server (PUT /pulls/<n>/update-branch,
   pinned to the head it read), so nothing is pushed from this machine;
5. waits, with a timeout, until the next PR's head has moved and its checks
   are green.

It stops at the first refusal, conflict, red check or timeout and prints the
PRs that are left. When the merge tool refuses a PR, the next PR gets its old
base back, so the stack looks as it did before the run.

Stdlib only. The gh runner, the merge runner, the sleep and the clock are
parameters so tests can replace them.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable, Sequence, TextIO

import _shiplib

STACK_FIELDS = (
    "number,state,isDraft,baseRefName,headRefName,headRefOid,mergeable,statusCheckRollup"
)
DEFAULT_BASE = "main"
DEFAULT_POLL_SECONDS = 30.0
DEFAULT_CHECK_TIMEOUT = 1800.0
MERGE_TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "merge")

# Exit codes (the same meaning as tools/ship/merge).
EXIT_OK = _shiplib.EXIT_OK
EXIT_STOPPED = _shiplib.EXIT_REFUSED
EXIT_ERROR = _shiplib.EXIT_ERROR
EXIT_MERGE_FAILED = _shiplib.EXIT_MERGE_FAILED

Runner = _shiplib.Runner
Sleeper = _shiplib.Sleeper
Clock = Callable[[], float]
# merge_runner(number, repo, required, wait_seconds, dry_run, out) -> exit code
MergeRunner = Callable[[int, str, Sequence[str], float, bool, TextIO], int]


class Stop(Exception):
    """The stack cannot go on. `left` is the index of the first PR not merged."""

    def __init__(self, reason: str, left: int, code: int = EXIT_STOPPED, note: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.left = left
        self.code = code
        self.note = note


def run_merge_tool(number: int, repo: str, required: Sequence[str], wait_seconds: float,
                   dry_run: bool, out: TextIO) -> int:
    """Run tools/ship/merge in a subprocess and copy its output line by line."""
    cmd = [
        sys.executable, MERGE_TOOL, str(number), "--repo", repo,
        "--require=" + ",".join(required), "--wait-seconds", f"{wait_seconds:g}",
    ]
    if dry_run:
        cmd.append("--dry-run")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert proc.stdout is not None
    for line in proc.stdout:
        out.write(line)
    return proc.wait()


@dataclass(frozen=True)
class Pr:
    number: int
    state: str
    draft: bool
    base: str
    head: str
    sha: str
    raw: dict

    @classmethod
    def from_json(cls, data: dict, number: int) -> "Pr":
        return cls(
            number=int(data.get("number") or number),
            state=str(data.get("state") or "").upper(),
            draft=bool(data.get("isDraft")),
            base=str(data.get("baseRefName") or ""),
            head=str(data.get("headRefName") or ""),
            sha=str(data.get("headRefOid") or ""),
            raw=data,
        )


def view(runner: Runner, number: int, repo: str) -> Pr:
    data = _shiplib._gh_json(
        runner, ["pr", "view", str(number), "--repo", repo, "--json", STACK_FIELDS]
    )
    return Pr.from_json(data, number)


def retarget(runner: Runner, number: int, repo: str, base: str) -> None:
    data = _shiplib._gh_json(
        runner, ["api", "-X", "PATCH", f"repos/{repo}/pulls/{number}", "-f", f"base={base}"]
    )
    got = str((data.get("base") or {}).get("ref") or "")
    if got != base:
        raise _shiplib.GhError(f"retarget of #{number} to {base} returned base {got or '?'}")


def update_branch(runner: Runner, number: int, repo: str, sha: str) -> None:
    """Merge the base into the PR branch on GitHub, pinned to the head we read."""
    args = ["api", "-X", "PUT", f"repos/{repo}/pulls/{number}/update-branch",
            "-f", f"expected_head_sha={sha}"]
    proc = runner(args)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise _shiplib.GhError(msg or f"exit {proc.returncode}")


def check_chain(prs: Sequence[Pr], base: str) -> list[str]:
    """Every reason the list is not a stack that can be merged in this order."""
    reasons = []
    for i, pr in enumerate(prs):
        if pr.state != "OPEN":
            reasons.append(f"#{pr.number} is {pr.state or 'in an unknown state'}, not OPEN")
        if pr.draft:
            reasons.append(f"#{pr.number} is a draft")
        if not pr.head:
            reasons.append(f"#{pr.number} has no head branch name")
        allowed = [base] if i == 0 else [base, prs[i - 1].head]
        if pr.base not in allowed:
            want = " or ".join(repr(a) for a in allowed)
            reasons.append(f"#{pr.number} is based on {pr.base!r}, expected {want}")
    heads = [pr.head for pr in prs]
    if len(set(heads)) != len(heads):
        reasons.append("two PRs share a head branch")
    return reasons


def wait_for_green(runner: Runner, sleep: Sleeper, clock: Clock, number: int, repo: str,
                   required: Sequence[str], old_sha: str, timeout: float, poll: float,
                   say: Callable[[str], None]) -> Pr:
    """Poll the PR until its head is not old_sha and every check is green.

    Raise Stop on a red check, a conflict, a closed PR or the timeout. Missing
    or pending checks mean "not yet": a new head needs a moment before its
    checks are registered.
    """
    deadline = clock() + timeout
    last = ""
    while True:
        pr = view(runner, number, repo)
        if pr.state != "OPEN":
            raise Stop(f"#{number} is {pr.state} while waiting for its checks", 0)
        if pr.sha == old_sha:
            status = f"waiting for update-branch to move the head of #{number} off {old_sha[:7]}"
        else:
            if str(pr.raw.get("mergeable") or "").upper() == "CONFLICTING":
                raise Stop(f"#{number} has merge conflicts after the branch update", 0)
            checks = _shiplib.latest_checks(pr.raw.get("statusCheckRollup") or [])
            failing = [c for c in checks if c.state == _shiplib.FAIL]
            if failing:
                raise Stop(f"red checks on #{number} (head {pr.sha[:7]}): "
                           + ", ".join(f"{c.label} ({c.raw})" for c in failing), 0)
            pending = [c.label for c in checks if c.state == _shiplib.PENDING]
            names = {c.name for c in checks}
            missing = [name for name in required if name not in names]
            if checks and not pending and not missing:
                say(f"#{number} head {pr.sha[:7]}: {len(checks)} checks green")
                return pr
            parts = []
            if not checks:
                parts.append("no checks yet")
            if pending:
                parts.append("pending: " + ", ".join(pending))
            if missing:
                parts.append("not reported yet: " + ", ".join(missing))
            status = f"#{number} head {pr.sha[:7]}: " + "; ".join(parts)
        left = deadline - clock()
        if left <= 0:
            raise Stop(f"timed out after {timeout:g} s ({status})", 0)
        if status != last:
            say(status)
            last = status
        sleep(min(poll, left))


def stack_merge(
    numbers: Sequence[int],
    repo: str | None = None,
    base: str = DEFAULT_BASE,
    required: Sequence[str] = _shiplib.DEFAULT_REQUIRED,
    wait_seconds: float = _shiplib.DEFAULT_WAIT_SECONDS,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    check_timeout: float = DEFAULT_CHECK_TIMEOUT,
    dry_run: bool = False,
    runner: Runner = _shiplib.run_gh,
    merge_runner: MergeRunner = run_merge_tool,
    sleep: Sleeper = time.sleep,
    clock: Clock = time.monotonic,
    out: TextIO | None = None,
) -> int:
    """Merge the stack bottom-up. Return an exit code."""
    stream = out or sys.stdout
    numbers = list(numbers)
    retargeted: set[int] = set()

    def say(line: str) -> None:
        print(f"stack-merge: {line}", file=stream)

    def verdict(word: str, detail: str) -> None:
        print(f"VERDICT: {word} {repo or '?'} stack {' '.join('#%d' % n for n in numbers)}: {detail}",
              file=stream)

    def report_left(start: int) -> None:
        if start >= len(numbers):
            return
        parts = []
        for n in numbers[start:]:
            parts.append(f"#{n} (retargeted to {base})" if n in retargeted else f"#{n}")
        say("left: " + ", ".join(parts))
        say("fix the cause, then rerun: tools/ship/stack-merge --repo "
            f"{repo} " + " ".join(str(n) for n in numbers[start:]))

    if not numbers:
        verdict("ERROR", "give at least one PR number")
        return EXIT_ERROR
    if len(set(numbers)) != len(numbers) or any(n <= 0 for n in numbers):
        verdict("ERROR", "PR numbers must be positive and distinct")
        return EXIT_ERROR

    try:
        if repo is None:
            repo = _shiplib.resolve_repo(runner)
        elif not _shiplib.REPO_RE.match(repo):
            verdict("ERROR", f"--repo must look like owner/name, got {repo!r}")
            return EXIT_ERROR
        prs = [view(runner, n, repo) for n in numbers]
    except _shiplib.GhError as exc:
        verdict("ERROR", str(exc))
        return EXIT_ERROR

    reasons = check_chain(prs, base)
    if reasons:
        verdict("REFUSED", "not a stack to merge in this order: " + "; ".join(reasons))
        return EXIT_STOPPED
    say(" -> ".join(f"#{p.number} ({p.head} into {p.base})" for p in prs))

    if dry_run:
        for i, n in enumerate(numbers):
            nxt = numbers[i + 1] if i + 1 < len(numbers) else None
            if nxt is not None and prs[i + 1].base != base:
                say(f"would retarget #{nxt} to {base}")
            say(f"would run tools/ship/merge {n} --repo {repo}")
            if nxt is not None:
                say(f"would update the branch of #{nxt} and wait for its checks")
        say(f"checking #{numbers[0]} with tools/ship/merge --dry-run")
        code = merge_runner(numbers[0], repo, required, wait_seconds, True, stream)
        verdict("DRY-RUN" if code == EXIT_OK else "REFUSED",
                "plan printed" if code == EXIT_OK else f"tools/ship/merge --dry-run exited {code}")
        return code

    done = 0  # PRs merged so far
    try:
        for i, n in enumerate(numbers):
            nxt = numbers[i + 1] if i + 1 < len(numbers) else None
            cur = view(runner, n, repo)
            if cur.state != "OPEN" or cur.base != base:
                raise Stop(f"#{n} is {cur.state} and based on {cur.base!r}; expected OPEN on {base!r}", i)
            moved = False
            if nxt is not None:
                nxt_pr = view(runner, nxt, repo)
                if nxt_pr.state != "OPEN":
                    raise Stop(f"#{nxt} is {nxt_pr.state}, not OPEN", i)
                if nxt_pr.base != base:
                    if nxt_pr.base != cur.head:
                        raise Stop(f"#{nxt} is based on {nxt_pr.base!r}, not on #{n} ({cur.head})", i)
                    retarget(runner, nxt, repo, base)
                    retargeted.add(nxt)
                    moved = True
                    say(f"retargeted #{nxt} from {cur.head} to {base}")

            say(f"running tools/ship/merge {n} --repo {repo}")
            code = merge_runner(n, repo, required, wait_seconds, False, stream)
            if code != EXIT_OK:
                note = ""
                if moved and code in (EXIT_STOPPED, EXIT_ERROR):
                    # #n was not merged, so its branch still exists: put the stack back.
                    try:
                        retarget(runner, nxt, repo, cur.head)
                        retargeted.discard(nxt)
                        note = f"#{nxt} is based on {cur.head} again"
                    except _shiplib.GhError as exc:
                        note = f"could not put #{nxt} back on {cur.head}: {exc}"
                raise Stop(f"tools/ship/merge did not merge #{n} (exit {code})", i, code, note)
            done = i + 1
            if nxt is None:
                break

            nxt_pr = view(runner, nxt, repo)
            try:
                update_branch(runner, nxt, repo, nxt_pr.sha)
            except _shiplib.GhError as exc:
                raise Stop(f"update-branch of #{nxt} failed (a conflict is resolved by hand): {exc}", i + 1)
            say(f"updated the branch of #{nxt} from {base} on GitHub; waiting for its checks")
            try:
                wait_for_green(runner, sleep, clock, nxt, repo, required, nxt_pr.sha,
                               check_timeout, poll_seconds, say)
            except Stop as stop:
                stop.left = i + 1
                raise
    except Stop as stop:
        if stop.note:
            say(stop.note)
        merged = numbers[: stop.left]
        detail = stop.reason
        if merged:
            detail += "; merged: " + " ".join(f"#{n}" for n in merged)
        word = "FAILED" if stop.code == EXIT_MERGE_FAILED else "STOPPED"
        verdict(word, detail)
        report_left(stop.left)
        return stop.code
    except _shiplib.GhError as exc:
        merged = numbers[:done]
        detail = str(exc) + ("; merged: " + " ".join(f"#{n}" for n in merged) if merged else "")
        verdict("ERROR", detail)
        report_left(done)
        return EXIT_ERROR

    verdict("MERGED", f"{len(numbers)} PRs merged in order")
    return EXIT_OK
