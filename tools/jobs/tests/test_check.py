"""Tests for tools/jobs/check. Synthetic data only (Example Co, Acme, ...)."""

from __future__ import annotations

import datetime as dt
import hashlib
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent
CHECK = TOOL_DIR / "check"
sys.path.insert(0, str(TOOL_DIR))
import _jobslib as jl  # noqa: E402

TODAY = dt.date(2026, 3, 12)  # Thursday; ISO week runs 2026-03-09 .. 2026-03-15


def rec(id_, stage="applied", applied="2026-03-10", last=None, **extra):
    r = {
        "id": id_, "company": f"Example Co {id_}", "role": "Data Analyst",
        "stage": stage, "applied_on": applied, "last_contact_on": last if last is not None else applied,
        "channel": "job board", "pay": "as posted", "cv": "cv-general", "next": "wait", "notes": "",
    }
    r.update(extra)
    return r


class ValidateTests(unittest.TestCase):
    def test_valid_records_pass(self):
        errors, warnings = jl.validate([rec(1), rec(2, stage="lead", applied="", last="")], TODAY)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_duplicate_id(self):
        errors, _ = jl.validate([rec(1), rec(1)], TODAY)
        self.assertTrue(any("duplicate id" in e for e in errors), errors)

    def test_non_integer_id(self):
        errors, _ = jl.validate([rec("7")], TODAY)
        self.assertTrue(any("id must be an integer" in e for e in errors), errors)

    def test_unknown_stage(self):
        errors, _ = jl.validate([rec(1, stage="hired")], TODAY)
        self.assertTrue(any("unknown stage" in e for e in errors), errors)

    def test_missing_required_field(self):
        r = rec(1)
        del r["cv"]
        errors, _ = jl.validate([r], TODAY)
        self.assertIn("#1: missing field 'cv'", errors)

    def test_bad_date(self):
        errors, _ = jl.validate([rec(1, applied="12/03/2026")], TODAY)
        self.assertTrue(any("not an ISO date" in e for e in errors), errors)

    def test_legal_history(self):
        hist = [{"on": "2026-03-01", "stage": "applied"}, {"on": "2026-03-05", "stage": "screen"},
                {"on": "2026-03-09", "stage": "interview"}]
        errors, _ = jl.validate([rec(1, stage="interview", applied="2026-03-01", history=hist)], TODAY)
        self.assertEqual(errors, [])

    def test_illegal_transition(self):
        hist = [{"on": "2026-03-01", "stage": "applied"}, {"on": "2026-03-05", "stage": "offer"}]
        errors, _ = jl.validate([rec(1, stage="offer", applied="2026-03-01", history=hist)], TODAY)
        self.assertTrue(any("illegal transition applied → offer" in e for e in errors), errors)

    def test_ghosted_revival_is_legal(self):
        hist = [{"on": "2026-02-01", "stage": "applied"}, {"on": "2026-02-20", "stage": "ghosted"},
                {"on": "2026-03-02", "stage": "screen"}]
        errors, _ = jl.validate([rec(1, stage="screen", applied="2026-02-01", history=hist)], TODAY)
        self.assertEqual(errors, [])

    def test_history_must_end_at_stage(self):
        hist = [{"on": "2026-03-01", "stage": "applied"}]
        errors, _ = jl.validate([rec(1, stage="screen", applied="2026-03-01", history=hist)], TODAY)
        self.assertTrue(any("does not match stage" in e for e in errors), errors)

    def test_history_dates_must_not_go_back(self):
        hist = [{"on": "2026-03-05", "stage": "applied"}, {"on": "2026-03-01", "stage": "rejected"}]
        errors, _ = jl.validate([rec(1, stage="rejected", applied="2026-03-05", history=hist,
                                     closed_reason="no")], TODAY)
        self.assertTrue(any("before the previous step" in e for e in errors), errors)

    def test_closed_without_reason_warns(self):
        errors, warnings = jl.validate([rec(1, stage="rejected")], TODAY)
        self.assertEqual(errors, [])
        self.assertTrue(any("without closed_reason" in w for w in warnings), warnings)

    def test_unknown_field_warns(self):
        errors, warnings = jl.validate([rec(1, salary_band="x")], TODAY)
        self.assertEqual(errors, [])
        self.assertTrue(any("unknown field 'salary_band'" in w for w in warnings), warnings)

    def test_hold_close_is_known_field(self):
        errors, warnings = jl.validate([rec(1, hold_close="exam pending on my side")], TODAY)
        self.assertEqual((errors, warnings), ([], []))

    def test_hold_14d_is_deprecated_alias(self):
        errors, warnings = jl.validate([rec(1, hold_14d="exam pending on my side")], TODAY)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, ["#1: field 'hold_14d' is deprecated, rename it to 'hold_close'"])

    def test_both_hold_fields_warn(self):
        errors, warnings = jl.validate([rec(1, hold_close="a", hold_14d="b")], TODAY)
        self.assertEqual(errors, [])
        self.assertTrue(any("both 'hold_close' and deprecated 'hold_14d'" in w for w in warnings), warnings)

    def test_skipped_list(self):
        skipped = [{"position": "Acme — Engineer", "reason": "on-site only"},
                   {"position": "Globex — Analyst", "reason": "", "tracker_id": 1}]
        errors, _ = jl.validate([rec(1)], TODAY, skipped)
        self.assertTrue(any("skipped[1]: 'reason'" in e for e in errors), errors)
        self.assertTrue(any("tracker_id 1 is also an application id" in e for e in errors), errors)


class ReportTests(unittest.TestCase):
    def test_default_closure_is_30_days(self):
        self.assertEqual(jl.CLOSURE_DAYS, 30)

    def test_closure_boundary_29_vs_30_days(self):
        rows = [rec(1, applied="2026-02-10"), rec(2, applied="2026-02-11")]  # 30 and 29 days
        proposed, held = jl.closures(rows, TODAY)
        self.assertEqual([r["id"] for r, _, _ in proposed], [1])
        self.assertEqual(proposed[0][1], 30)
        self.assertEqual(held, [])

    def test_closure_custom_days(self):
        rows = [rec(1, applied="2026-02-26"), rec(2, applied="2026-02-27")]  # 14 and 13 days
        proposed, _ = jl.closures(rows, TODAY, 14)
        self.assertEqual([r["id"] for r, _, _ in proposed], [1])

    def test_closure_uses_latest_contact(self):
        rows = [rec(1, applied="2026-02-01", last="2026-03-01")]
        self.assertEqual(jl.closures(rows, TODAY)[0], [])

    def test_closure_only_applied_and_screen(self):
        rows = [rec(1, stage="screen", applied="2026-01-01"),
                rec(2, stage="interview", applied="2026-01-01"),
                rec(3, stage="lead", applied="", last="")]
        self.assertEqual([r["id"] for r, _, _ in jl.closures(rows, TODAY)[0]], [1])

    def test_closure_hold(self):
        rows = [rec(1, applied="2026-01-01", hold_close="exam pending on my side")]
        proposed, held = jl.closures(rows, TODAY)
        self.assertEqual(proposed, [])
        self.assertEqual([r["id"] for r in held], [1])

    def test_closure_hold_deprecated_alias(self):
        rows = [rec(1, applied="2026-01-01", hold_14d="exam pending on my side"),
                rec(2, applied="2026-01-01", hold_close="", hold_14d="ignored: hold_close wins")]
        proposed, held = jl.closures(rows, TODAY)
        self.assertEqual([r["id"] for r, _, _ in proposed], [2])
        self.assertEqual([r["id"] for r in held], [1])
        self.assertEqual(jl.hold_reason(rows[0]), "exam pending on my side")

    def test_followups_this_week_and_overdue(self):
        rows = [rec(1, follow_up_on="2026-03-15"),            # Sunday this week
                rec(2, follow_up_on="2026-03-16"),            # next Monday: out
                rec(3, follow_up_on="2026-03-02"),            # overdue
                rec(4, stage="rejected", follow_up_on="2026-03-12", closed_reason="no")]
        got = [(r["id"], overdue) for r, _, overdue in jl.followups(rows, TODAY)]
        self.assertEqual(got, [(3, True), (1, False)])

    def test_interview_prep_48h(self):
        rows = [rec(1, stage="interview", interview_on="2026-03-14T09:00+07:00"),
                rec(2, stage="interview", interview_on="2026-03-15"),
                rec(3, stage="interview", interview_on="2026-03-12")]
        self.assertEqual([r["id"] for r, _ in jl.interview_prep(rows, TODAY)], [3, 1])

    def test_next_actions_skip_wait_and_closed(self):
        rows = [rec(1, next="wait"), rec(2, next="Wait — reply expected"),
                rec(3, next="Send the take-home"), rec(4, stage="withdrawn", next="x", closed_reason="r"),
                rec(5, next=""), rec(6, stage="interview", next="Prepare system design")]
        self.assertEqual([r["id"] for r in jl.next_actions(rows)], [6, 3])

    def test_week_bounds(self):
        self.assertEqual(jl.week_bounds(TODAY), (dt.date(2026, 3, 9), dt.date(2026, 3, 15)))
        self.assertEqual(jl.week_bounds(dt.date(2026, 3, 15)), (dt.date(2026, 3, 9), dt.date(2026, 3, 15)))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        p = self.dir / name
        p.write_text(textwrap.dedent(text), encoding="utf-8")
        return p

    def run_check(self, *args):
        return subprocess.run([sys.executable, str(CHECK), *args], capture_output=True, text=True, check=False)

    GOOD = """\
        - id: 1
          company: Example Co
          role: Data Analyst (contract)
          stage: applied
          applied_on: 2026-02-20
          last_contact_on: 2026-02-20
          channel: job board
          pay: as posted
          cv: cv-general
          next: wait
          notes: ""
        - id: 2
          company: Acme
          role: Backend Engineer
          stage: screen
          applied_on: 2026-03-02
          last_contact_on: 2026-03-05
          channel: referral
          pay: ""
          cv: cv-general
          next: Finish the take-home
          notes: ""
          follow_up_on: 2026-03-13
          history:
            - {on: 2026-03-02, stage: applied}
            - {on: 2026-03-05, stage: screen, note: recruiter call}
        """

    def test_report_and_file_untouched(self):
        data = self.write("applications.yaml", self.GOOD)
        before = hashlib.sha256(data.read_bytes()).hexdigest()
        res = self.run_check("--data", str(data), "--today", "2026-03-12")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        for section in ("VALIDATION", "30-DAY CLOSURES (proposed ghosted, Nghiep confirms)",
                        "FOLLOW-UPS DUE THIS WEEK", "INTERVIEW PREP", "NEXT ACTIONS", "STAGES"):
            self.assertIn(section, res.stdout)
        # #1 applied 2026-02-20: 20 days, under the 30-day default
        self.assertNotIn("#1 Example Co", res.stdout.split("30-DAY CLOSURES")[1].split("FOLLOW-UPS")[0])
        self.assertIn("Finish the take-home", res.stdout)
        self.assertEqual(hashlib.sha256(data.read_bytes()).hexdigest(), before)

    def test_close_after_days_flag(self):
        data = self.write("applications.yaml", self.GOOD)
        res = self.run_check("--data", str(data), "--today", "2026-03-12", "--close-after-days", "14")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertNotIn("30-DAY CLOSURES", res.stdout)
        section = res.stdout.split("14-DAY CLOSURES (proposed ghosted, Nghiep confirms)")[1].split("FOLLOW-UPS")[0]
        self.assertIn("#1 Example Co", section)
        self.assertIn("20 days", section)

    def test_close_after_days_must_be_positive(self):
        data = self.write("applications.yaml", self.GOOD)
        for bad in ("0", "-3", "x"):
            res = self.run_check("--data", str(data), "--close-after-days", bad)
            self.assertEqual(res.returncode, 2, bad)

    def test_held_row_shows_hold_close(self):
        data = self.write("applications.yaml", self.GOOD.replace(
            '          notes: ""\n        - id: 2', '          notes: ""\n          hold_14d: waiting for my exam\n        - id: 2'))
        res = self.run_check("--data", str(data), "--today", "2026-04-30")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("field 'hold_14d' is deprecated", res.stdout)
        self.assertIn("held  #1 Example Co", res.stdout)
        self.assertIn("hold_close: waiting for my exam", res.stdout)

    def test_validate_only(self):
        data = self.write("applications.yaml", self.GOOD)
        res = self.run_check("--data", str(data), "--today", "2026-03-12", "--validate-only")
        self.assertEqual(res.returncode, 0)
        self.assertIn("VALIDATION", res.stdout)
        self.assertNotIn("NEXT ACTIONS", res.stdout)

    def test_errors_exit_1(self):
        data = self.write("applications.yaml", self.GOOD.replace("stage: screen", "stage: hired"))
        res = self.run_check("--data", str(data), "--today", "2026-03-12")
        self.assertEqual(res.returncode, 1)
        self.assertIn("ERROR", res.stdout)
        self.assertNotIn("NEXT ACTIONS", res.stdout)

    def test_skipped_file(self):
        data = self.write("applications.yaml", self.GOOD)
        skipped = self.write("skipped.yaml", '- {position: "Globex — Analyst", reason: "US only"}\n')
        res = self.run_check("--data", str(data), "--skipped", str(skipped), "--today", "2026-03-12")
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("skipped list 1", res.stdout)

    def test_missing_file_exit_2(self):
        res = self.run_check("--data", str(self.dir / "nope.yaml"))
        self.assertEqual(res.returncode, 2)

    def test_top_level_must_be_list(self):
        data = self.write("applications.yaml", "applications: []\n")
        self.assertEqual(self.run_check("--data", str(data)).returncode, 2)

    def test_bad_today_arg(self):
        data = self.write("applications.yaml", self.GOOD)
        self.assertEqual(self.run_check("--data", str(data), "--today", "12/03/2026").returncode, 2)


if __name__ == "__main__":
    unittest.main()
