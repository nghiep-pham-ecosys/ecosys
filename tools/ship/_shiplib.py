"""Logic for tools/ship/merge (spec §9.1, §9.7).

The merge tool is the only allowed way to merge a PR. It reads the PR twice,
some seconds apart, and merges only when both reads agree that the PR is open,
ready, free of conflicts and fully green. The merge pins the head commit with
--match-head-commit, so a push between the check and the merge fails the merge.

Stdlib only. The gh runner and the sleep function are parameters so tests can
replace them.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Callable, Sequence, TextIO

PR_FIELDS = (
    "number,title,url,isDraft,state,mergeable,mergeStateStatus,"
    "headRefOid,baseRefName,statusCheckRollup"
)
DEFAULT_REQUIRED = ("ci-result", "pr-title")
DEFAULT_WAIT_SECONDS = 20.0
MERGEABLE_RETRY_SECONDS = 5.0
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Exit codes.
EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_ERROR = 2
EXIT_MERGE_FAILED = 3

PASS = "pass"
FAIL = "fail"
PENDING = "pending"

# CheckRun (GitHub Actions jobs and other apps).
RUN_DONE = "COMPLETED"
RUN_OK = {"SUCCESS", "NEUTRAL", "SKIPPED"}
# Everything else that is COMPLETED counts as failing, for example FAILURE,
# CANCELLED, TIMED_OUT, ACTION_REQUIRED, STARTUP_FAILURE and STALE.

# StatusContext (commit statuses).
STATUS_OK = {"SUCCESS"}
STATUS_PENDING = {"PENDING", "EXPECTED"}
# FAILURE, ERROR and anything unknown count as failing.

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]
Sleeper = Callable[[float], None]


class GhError(Exception):
    """A gh read command failed or returned something we cannot parse."""


def run_gh(args: Sequence[str]) -> subprocess.CompletedProcess:
    """Run the real gh CLI and capture its output."""
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
    )


@dataclass(frozen=True)
class Check:
    kind: str  # "run" or "status"
    workflow: str
    name: str
    state: str  # PASS, FAIL or PENDING
    raw: str  # the GitHub status or conclusion, upper case
    stamp: str  # ISO time used to pick the newest of duplicate runs

    @property
    def label(self) -> str:
        return f"{self.workflow} / {self.name}" if self.workflow else self.name


@dataclass
class Assessment:
    sha: str
    checks: list[Check] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def fingerprint(self) -> tuple:
        return tuple(
            sorted((c.kind, c.workflow, c.name, c.state, c.raw) for c in self.checks)
        )


def classify(entry: dict) -> Check:
    """Turn one statusCheckRollup entry into a Check."""
    typename = entry.get("__typename") or ""
    if typename == "StatusContext" or (
        "context" in entry and "conclusion" not in entry
    ):
        raw = str(entry.get("state") or "").upper() or "NONE"
        if raw in STATUS_OK:
            state = PASS
        elif raw in STATUS_PENDING:
            state = PENDING
        else:
            state = FAIL
        return Check(
            kind="status",
            workflow="",
            name=str(entry.get("context") or "?"),
            state=state,
            raw=raw,
            stamp=str(entry.get("startedAt") or ""),
        )

    status = str(entry.get("status") or "").upper()
    conclusion = str(entry.get("conclusion") or "").upper()
    if status != RUN_DONE:
        state, raw = PENDING, status or "UNKNOWN"
    elif conclusion in RUN_OK:
        state, raw = PASS, conclusion
    else:
        state, raw = FAIL, conclusion or "NO_CONCLUSION"
    return Check(
        kind="run",
        workflow=str(entry.get("workflowName") or ""),
        name=str(entry.get("name") or "?"),
        state=state,
        raw=raw,
        stamp=str(entry.get("completedAt") or entry.get("startedAt") or ""),
    )


def latest_checks(entries: Sequence[dict]) -> list[Check]:
    """Keep one check per (kind, workflow, name).

    The rollup can hold several runs of the same job on one commit, for example
    a pr-title run that failed and a newer one after the title was fixed. A
    pending run always wins, so a rerun in flight blocks the merge. Otherwise
    the run that finished last wins.
    """
    groups: dict[tuple[str, str, str], list[Check]] = {}
    for entry in entries or []:
        check = classify(entry)
        groups.setdefault((check.kind, check.workflow, check.name), []).append(check)
    result = []
    for group in groups.values():
        pending = [c for c in group if c.state == PENDING]
        result.append(pending[0] if pending else max(group, key=lambda c: c.stamp))
    return sorted(result, key=lambda c: (c.name, c.workflow, c.kind))


def assess(pr: dict, required: Sequence[str]) -> Assessment:
    """Return every reason that blocks a merge of this PR (empty means ready)."""
    sha = str(pr.get("headRefOid") or "")
    checks = latest_checks(pr.get("statusCheckRollup") or [])
    out = Assessment(sha=sha, checks=checks)
    reasons = out.reasons

    state = str(pr.get("state") or "").upper()
    if state != "OPEN":
        reasons.append(f"PR is {state or 'in an unknown state'}, not OPEN")
    if pr.get("isDraft"):
        reasons.append("PR is a draft")
    mergeable = str(pr.get("mergeable") or "").upper()
    if mergeable == "CONFLICTING":
        reasons.append("PR has merge conflicts")
    elif mergeable != "MERGEABLE":
        reasons.append(f"GitHub has not computed mergeability (mergeable={mergeable or 'UNKNOWN'})")
    merge_state = str(pr.get("mergeStateStatus") or "").upper()
    if merge_state == "DIRTY" and mergeable != "CONFLICTING":
        reasons.append("merge state is DIRTY (conflicts)")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        reasons.append("head commit SHA is missing")

    if not checks:
        reasons.append("PR has no checks at all")
    failing = [c for c in checks if c.state == FAIL]
    pending = [c for c in checks if c.state == PENDING]
    if failing:
        reasons.append(
            "failing checks: " + ", ".join(f"{c.label} ({c.raw})" for c in failing)
        )
    if pending:
        reasons.append(
            "pending checks: " + ", ".join(f"{c.label} ({c.raw})" for c in pending)
        )
    by_name: dict[str, list[Check]] = {}
    for c in checks:
        by_name.setdefault(c.name, []).append(c)
    for name in required:
        found = by_name.get(name)
        if not found:
            reasons.append(f"required check '{name}' is missing")
        elif any(c.state == PASS and c.raw != "SUCCESS" for c in found):
            # A skipped or neutral required check proves nothing.
            raws = ", ".join(c.raw for c in found)
            reasons.append(f"required check '{name}' did not succeed ({raws})")
    return out


def _gh_json(runner: Runner, args: Sequence[str]) -> dict:
    proc = runner(list(args))
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        raise GhError(f"gh {' '.join(args[:2])} failed: {msg or 'exit ' + str(proc.returncode)}")
    try:
        data = json.loads(proc.stdout or "")
    except json.JSONDecodeError as exc:
        raise GhError(f"gh {' '.join(args[:2])} returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise GhError(f"gh {' '.join(args[:2])} returned {type(data).__name__}, not an object")
    return data


def resolve_repo(runner: Runner) -> str:
    data = _gh_json(runner, ["repo", "view", "--json", "nameWithOwner"])
    repo = str(data.get("nameWithOwner") or "")
    if not REPO_RE.match(repo):
        raise GhError(f"could not resolve the current repo (got {repo!r})")
    return repo


def view_pr(runner: Runner, number: int, repo: str) -> dict:
    return _gh_json(
        runner, ["pr", "view", str(number), "--repo", repo, "--json", PR_FIELDS]
    )


def read_pr(runner: Runner, sleep: Sleeper, number: int, repo: str,
            retry_seconds: float = MERGEABLE_RETRY_SECONDS) -> dict:
    """View the PR; if GitHub still computes mergeability, look once more."""
    pr = view_pr(runner, number, repo)
    if str(pr.get("mergeable") or "").upper() == "UNKNOWN":
        sleep(retry_seconds)
        pr = view_pr(runner, number, repo)
    return pr


def diff_checks(a: Assessment, b: Assessment) -> str:
    first = {(c.kind, c.workflow, c.name): c for c in a.checks}
    second = {(c.kind, c.workflow, c.name): c for c in b.checks}
    parts = []
    for key in sorted(set(first) | set(second)):
        x, y = first.get(key), second.get(key)
        label = (x or y).label
        if x is None:
            parts.append(f"{label} appeared ({y.raw})")
        elif y is None:
            parts.append(f"{label} disappeared")
        elif (x.state, x.raw) != (y.state, y.raw):
            parts.append(f"{label} {x.raw} -> {y.raw}")
    return ", ".join(parts) or "check list changed"


def merge(
    number: int,
    repo: str | None = None,
    wait_seconds: float = DEFAULT_WAIT_SECONDS,
    required: Sequence[str] = DEFAULT_REQUIRED,
    dry_run: bool = False,
    runner: Runner = run_gh,
    sleep: Sleeper = time.sleep,
    out: TextIO | None = None,
    retry_seconds: float = MERGEABLE_RETRY_SECONDS,
) -> int:
    """Check the PR twice and squash-merge it. Return an exit code."""
    stream = out or sys.stdout

    def say(line: str) -> None:
        print(f"merge: {line}", file=stream)

    def verdict(word: str, target: str, detail: str) -> None:
        print(f"VERDICT: {word} {target}: {detail}", file=stream)

    target = f"{repo or '?'}#{number}"
    try:
        if repo is None:
            repo = resolve_repo(runner)
        elif not REPO_RE.match(repo):
            verdict("ERROR", target, f"--repo must look like owner/name, got {repo!r}")
            return EXIT_ERROR
        target = f"{repo}#{number}"

        first_pr = read_pr(runner, sleep, number, repo, retry_seconds)
        first = assess(first_pr, required)
        if first.reasons:
            verdict("REFUSED", target, "; ".join(first.reasons))
            return EXIT_REFUSED
        say(
            f"read 1: {target} head {first.sha[:7]}, {len(first.checks)} checks green; "
            f"reading again in {wait_seconds:g} s"
        )

        sleep(wait_seconds)
        second_pr = read_pr(runner, sleep, number, repo, retry_seconds)
        second = assess(second_pr, required)
        if second.reasons:
            verdict("REFUSED", target, "read 2: " + "; ".join(second.reasons))
            return EXIT_REFUSED
        if second.sha != first.sha:
            verdict(
                "REFUSED", target,
                f"head moved between reads ({first.sha[:7]} -> {second.sha[:7]})",
            )
            return EXIT_REFUSED
        if second.fingerprint() != first.fingerprint():
            verdict(
                "REFUSED", target,
                "checks changed between reads: " + diff_checks(first, second),
            )
            return EXIT_REFUSED
        say(f"read 2: head {second.sha[:7]} unchanged, {len(second.checks)} checks still green")
    except GhError as exc:
        verdict("ERROR", target, str(exc))
        return EXIT_ERROR

    # --repo makes gh skip local branch deletion, which fails when the branch
    # is checked out in a lane worktree. The remote branch is still deleted.
    cmd = [
        "pr", "merge", str(number), "--repo", repo, "--squash",
        "--match-head-commit", first.sha, "--delete-branch",
    ]
    if dry_run:
        verdict("DRY-RUN", target, "would run: gh " + " ".join(cmd))
        return EXIT_OK

    proc = runner(cmd)
    failure = ""
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        failure = f"gh pr merge exited {proc.returncode}: {msg}"

    # Always re-read the PR: gh can exit non-zero after a successful merge, for
    # example when the repo already deleted the branch (delete_branch_on_merge)
    # and gh's own --delete-branch call then gets a 404.
    try:
        after = _gh_json(
            runner,
            ["pr", "view", str(number), "--repo", repo, "--json", "state,mergeCommit"],
        )
    except GhError as exc:
        if failure:
            verdict("FAILED", target, f"{failure}; the follow-up read failed too: {exc}")
        else:
            verdict("UNCONFIRMED", target, f"merge ran but the follow-up read failed: {exc}")
        return EXIT_MERGE_FAILED
    if str(after.get("state") or "").upper() != "MERGED":
        if failure:
            verdict("FAILED", target, failure)
        else:
            verdict("UNCONFIRMED", target, f"merge ran but PR state is {after.get('state')!r}")
        return EXIT_MERGE_FAILED
    commit = (after.get("mergeCommit") or {}).get("oid") or "?"
    detail = f"squashed head {first.sha[:7]} as {commit[:7]}"
    if failure:
        detail += f" (gh reported an error after the merge, ignored: {failure})"
    verdict("MERGED", target, detail)
    return EXIT_OK
