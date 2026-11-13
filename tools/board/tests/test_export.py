import datetime as dt
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _boardlib as bl  # noqa: E402

EXPORT = HERE.parent / "export"
NOW = dt.datetime(2026, 11, 13, 10, 30, tzinfo=dt.timezone(dt.timedelta(hours=7)))

ITEMS = [
    {"title": "Ship the Example Co widget", "status": "Next", "area": "lab", "due": "2026-11-20",
     "estimate (h)": 2, "week": {"title": "2026-W47", "startDate": "2026-11-16", "duration": 7},
     "content": {"type": "Issue", "number": 3, "repository": "acme/widgets",
                 "url": "https://github.com/acme/widgets/issues/3"}},
    {"title": "Fix | pipe\nand newline", "status": "In progress", "area": "ecosys",
     "content": {"type": "Issue", "number": 7, "repository": "acme/tools",
                 "url": "https://github.com/acme/tools/issues/7"}},
    {"title": "Draft idea", "status": None, "content": {"type": "DraftIssue", "title": "Draft idea"}},
    {"title": "Earlier due", "status": "Next", "due": "2026-11-15", "estimate (h)": 0.5,
     "content": {"type": "Issue", "number": 1, "repository": "acme/widgets",
                 "url": "https://github.com/acme/widgets/issues/1"}},
]


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.text = bl.render(ITEMS, NOW, project_url="https://github.com/orgs/acme/projects/1")
        self.lines = self.text.splitlines()

    def test_first_line_is_snapshot_with_offset(self):
        self.assertEqual(self.lines[0], "snapshot: 2026-11-13T10:30+07:00")

    def test_groups_in_board_order_with_counts(self):
        headings = [line for line in self.lines if line.startswith("## ")]
        self.assertEqual(headings, ["## In progress (1)", "## Next (2)", "## (no status) (1)"])
        self.assertIn("4 items: In progress 1, Next 2, (no status) 1.", self.text)

    def test_row_fields_and_sort_by_due(self):
        rows = [line for line in self.lines if line.startswith("| ") and "acme/widgets" in line]
        self.assertEqual(rows[0], "| Earlier due |  | 2026-11-15 |  | 0.5 h | "
                                  "[widgets#1](https://github.com/acme/widgets/issues/1) |")
        self.assertEqual(rows[1], "| Ship the Example Co widget | lab | 2026-11-20 | 2026-W47 | 2 h | "
                                  "[widgets#3](https://github.com/acme/widgets/issues/3) |")

    def test_cells_escape_pipes_and_newlines(self):
        self.assertIn("| Fix \\| pipe and newline | ecosys |", self.text)

    def test_draft_has_no_link(self):
        self.assertIn("| Draft idea |  |  |  |  | draft |", self.text)

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            bl.render([], dt.datetime(2026, 11, 13))

    def test_empty_board(self):
        text = bl.render([], NOW)
        self.assertIn("0 items.", text)
        self.assertNotIn("## ", text)


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(EXPORT), *args], capture_output=True, text=True, check=False)

    def test_writes_file_from_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "items.json"
            src.write_text(json.dumps({"items": ITEMS, "totalCount": 4}), encoding="utf-8")
            out = Path(tmp) / "board.md"
            proc = self.run_cli("--input", str(src), "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(out.read_text(encoding="utf-8").startswith("snapshot: "))

    def test_truncated_listing_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "items.json"
            src.write_text(json.dumps({"items": ITEMS, "totalCount": 9}), encoding="utf-8")
            proc = self.run_cli("--input", str(src), "--stdout")
            self.assertEqual(proc.returncode, 1)
            self.assertIn("only 4 of 9", proc.stderr)

    def test_missing_out_folder_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "items.json"
            src.write_text(json.dumps({"items": []}), encoding="utf-8")
            proc = self.run_cli("--input", str(src), "--out", str(Path(tmp) / "nope" / "board.md"))
            self.assertEqual(proc.returncode, 1)


if __name__ == "__main__":
    unittest.main()
