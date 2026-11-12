"""Test helpers: run a hook as Claude Code would, with a fixture payload on stdin.

Paths are found relative to this file, so the tests work wherever the
.claude folder lives (staging or the final place).
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
HOOKS_DIR = os.path.dirname(TESTS_DIR)
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")

# The fixtures were captured with the project at FIXTURE_PROJECT. Tests run against the
# real checkout (a CI runner clones elsewhere), so fixture paths are rewritten to PROJECT;
# the hooks get it through the environment. Locally the two are the same path.
FIXTURE_PROJECT = "/home/nghiep/projects/nghiep-pham-ecosys"
PROJECT = os.path.realpath(os.path.join(HOOKS_DIR, "..", ".."))
HOME = "/home/nghiep"
WT = PROJECT + "/.tmp-session/wt"
LANE = WT + "/s1-lane-a"

# key -> (fixture file, field overrides). The files derive from real captured
# payloads with every value scrubbed (see fixtures/README.md).
FIXTURES = {
    "main-bash": ("main-bash.captured.json", {}),
    "main-read": ("main-read.captured.json", {}),
    "sub-bash": ("subagent-bash.captured.json", {}),
    # A subagent whose cwd is inside its worktree (the capture showed the root,
    # but ship-guard must treat both as a lane).
    "sub-wt-bash": ("subagent-bash.captured.json", {"cwd": LANE}),
    "sub-write": ("subagent-write.captured.json", {}),
}

if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)


def load_fixture(key: str) -> dict:
    name, overrides = FIXTURES[key]
    with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as fh:
        payload = _rebase_paths(json.load(fh))
    payload.update(overrides)
    return payload


def _rebase_paths(value):
    """Point fixture paths captured under FIXTURE_PROJECT at the real checkout."""
    if isinstance(value, str):
        if value == FIXTURE_PROJECT or value.startswith(FIXTURE_PROJECT + "/"):
            return PROJECT + value[len(FIXTURE_PROJECT):]
        return value
    if isinstance(value, dict):
        return {k: _rebase_paths(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_rebase_paths(v) for v in value]
    return value


def build_payload(key: str, command: str | None = None, tool_input: dict | None = None,
                  cwd: str | None = None, tool_name: str | None = None) -> dict:
    payload = copy.deepcopy(load_fixture(key))
    if tool_name is not None:
        payload["tool_name"] = tool_name
    if command is not None:
        payload["tool_input"] = {"command": command, "description": "test"}
    if tool_input is not None:
        payload["tool_input"] = tool_input
    if cwd is not None:
        payload["cwd"] = cwd
    return payload


def run_raw(hook: str, stdin_text: str, env_extra: dict | None = None, project_env: bool = True):
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
    env["HOME"] = HOME
    if project_env:
        env["CLAUDE_PROJECT_DIR"] = PROJECT
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, os.path.join(HOOKS_DIR, hook)],
        input=stdin_text, capture_output=True, text=True, env=env, timeout=20,
    )
    return proc.returncode, proc.stderr


def run_hook(hook: str, key: str, project_env: bool = True, **kw):
    return run_raw(hook, json.dumps(build_payload(key, **kw)), project_env=project_env)


class HookCase(unittest.TestCase):
    HOOK = ""

    def assertBlocked(self, key, contains=None, **kw):
        code, err = run_hook(self.HOOK, key, **kw)
        self.assertEqual(code, 2, f"expected block for {kw}; stderr={err!r}")
        self.assertTrue(err.strip(), "a block must explain itself on stderr")
        if contains:
            self.assertIn(contains, err)
        return err

    def assertAllowed(self, key, **kw):
        code, err = run_hook(self.HOOK, key, **kw)
        self.assertEqual(code, 0, f"expected pass for {kw}; stderr={err!r}")
