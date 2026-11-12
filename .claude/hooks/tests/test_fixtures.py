import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _harness import FIXTURES, FIXTURES_DIR, load_fixture  # noqa: E402

MAIN_KEYS = ["session_id", "transcript_path", "cwd", "scratchpad_dir", "prompt_id", "permission_mode",
             "effort", "hook_event_name", "tool_name", "tool_input", "tool_use_id"]
SUB_KEYS = MAIN_KEYS[:6] + ["agent_id", "agent_type"] + MAIN_KEYS[6:]


class CapturedFixtureTest(unittest.TestCase):
    """The fixtures keep the captured key set and order (fixtures/README.md)."""

    def test_every_fixture_file_is_used(self):
        used = {name for name, _ in FIXTURES.values()}
        on_disk = {f for f in os.listdir(FIXTURES_DIR) if f.endswith(".json")}
        self.assertEqual(on_disk, used)
        self.assertTrue(all(f.endswith(".captured.json") for f in on_disk))

    def test_key_order(self):
        for key in FIXTURES:
            with self.subTest(key=key):
                payload = load_fixture(key)
                expected = SUB_KEYS if key.startswith("sub-") else MAIN_KEYS
                self.assertEqual(list(payload), expected)
                self.assertEqual(payload["hook_event_name"], "PreToolUse")

    def test_subagent_markers(self):
        self.assertNotIn("agent_id", load_fixture("main-bash"))
        sub = load_fixture("sub-bash")
        self.assertTrue(sub["agent_id"])
        self.assertEqual(sub["agent_type"], "workflow-subagent")

    def test_ids_are_fake(self):
        for name in sorted({name for name, _ in FIXTURES.values()}):
            with open(os.path.join(FIXTURES_DIR, name), encoding="utf-8") as fh:
                payload = json.load(fh)
            with self.subTest(name=name):
                self.assertTrue(payload["session_id"].startswith("00000000-"))
                self.assertTrue(payload["tool_use_id"].startswith("toolu_FakeFixture"))
                self.assertTrue(payload["transcript_path"].startswith("/tmp/claude-fixture/"))


if __name__ == "__main__":
    unittest.main()
