"""Tests for tools/cv with synthetic profile data only (Example Co, Acme)."""

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _cvlib  # noqa: E402

CLI = HERE.parent / "cv"

BASE = {
    "version": 1,
    "basics": {"id": "basics", "name": "Alex Example", "email": "alex@example.com",
               "links": [{"label": "GitHub", "url": "https://example.com/alex"}]},
    "headlines": [{"id": "head-main", "text": "Data Engineer"}],
    "availability": [{"id": "avail-remote", "text": "Remote (UTC+7)"}],
    "summaries": [{"id": "sum-main", "text": "Builds pipelines that ran 120+ jobs."}],
    "skills": [{"id": "skill-py", "area": "Code", "items": "Python, SQL"}],
    "work": [{"id": "work-acme", "org": "Acme", "role": "Engineer", "start": "Jan 2024", "end": "present",
              "highlights": [{"id": "ach-acme-speed", "text": "Cut run time by 40%."},
                             {"id": "ach-acme-old", "text": "Old fact.", "retired": True}]}],
    "projects": [{"id": "proj-demo", "name": "Demo", "text": "A demo on 3 datasets", "url": "https://example.com/d"}],
    "education": [{"id": "edu-bsc", "text": "BSc, Example University (2015–2019)"}],
    "variants": {"main": {"headline": "head-main", "availability": "avail-remote", "summary": ["sum-main"],
                          "skills": ["skill-py"], "work": [{"id": "work-acme", "highlights": ["ach-acme-speed"]}],
                          "projects": ["proj-demo"], "education": ["edu-bsc"]}},
}


def prof():
    return copy.deepcopy(BASE)


class CheckTest(unittest.TestCase):
    def test_valid_profile_has_no_errors(self):
        self.assertEqual(_cvlib.check(prof()), [])

    def test_number_outside_a_fact_fails(self):
        p = prof()
        p["skills"][0]["area"] = "Code"
        p["notes"] = {"text": "Saved 50 hours"}
        errs = _cvlib.check(p)
        self.assertTrue(any("number 50" in e for e in errs), errs)

    def test_duplicate_id_fails(self):
        p = prof()
        p["projects"].append({"id": "proj-demo", "name": "Again", "text": "x"})
        self.assertTrue(any("duplicate id" in e for e in _cvlib.check(p)))

    def test_wrong_prefix_fails(self):
        p = prof()
        p["skills"][0]["id"] = "proj-py"
        self.assertTrue(any("must start with 'skill-'" in e for e in _cvlib.check(p)))

    def test_variant_unknown_and_retired_ids_fail(self):
        p = prof()
        p["variants"]["main"]["skills"] = ["skill-missing"]
        p["variants"]["main"]["work"][0]["highlights"].append("ach-acme-old")
        errs = _cvlib.check(p)
        self.assertTrue(any("unknown id 'skill-missing'" in e for e in errs), errs)
        self.assertTrue(any("ach-acme-old is retired" in e for e in errs), errs)

    def test_highlight_of_other_job_fails(self):
        p = prof()
        p["work"].append({"id": "work-example", "org": "Example Co", "role": "Analyst", "start": "2020", "end": "2023",
                          "highlights": [{"id": "ach-ex-report", "text": "Wrote reports."}]})
        p["variants"]["main"]["work"][0]["highlights"].append("ach-ex-report")
        self.assertTrue(any("not a highlight of work-acme" in e for e in _cvlib.check(p)))


class NumbersTest(unittest.TestCase):
    def test_numbers_are_tied_to_the_nearest_fact(self):
        rows = {(o, n) for o, n, _ in _cvlib.numbers(prof())}
        self.assertIn(("ach-acme-speed", "40"), rows)
        self.assertIn(("sum-main", "120+"), rows)
        self.assertIn(("work-acme", "2024"), rows)

    def test_letters_glued_to_digits_are_not_numbers(self):
        p = prof()
        p["skills"][0]["items"] = "B2B, S3, Python 3"
        nums = [n for o, n, _ in _cvlib.numbers(p) if o == "skill-py"]
        self.assertEqual(nums, ["3"])

    def test_variant_ids(self):
        ids = _cvlib.variant_ids(prof(), "main")
        self.assertIn("ach-acme-speed", ids)
        self.assertNotIn("ach-acme-old", ids)


class ResolveTest(unittest.TestCase):
    def test_resolve_keeps_order_and_skips_retired(self):
        d = _cvlib.resolve(prof(), "main")
        self.assertEqual(d["headline"], "Data Engineer")
        self.assertEqual(d["work"][0]["highlights"], ["Cut run time by 40%."])
        self.assertEqual(d["work"][0]["dates"], "Jan 2024 – present")
        self.assertIn("Remote (UTC+7)", d["contact"])
        self.assertEqual(d["research"], [])

    def test_unknown_variant_raises(self):
        with self.assertRaises(_cvlib.ProfileError):
            _cvlib.resolve(prof(), "nope")


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], capture_output=True, text=True)

    def test_check_ok_and_fail_without_printing_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "p.yaml"
            good.write_text(yaml.safe_dump(prof()), encoding="utf-8")
            r = self.run_cli("check", "--profile", str(good))
            self.assertEqual(r.returncode, 0, r.stderr)
            bad = prof()
            bad["notes"] = {"text": "Saved 50 hours at Acme"}
            badp = Path(tmp) / "b.yaml"
            badp.write_text(yaml.safe_dump(bad), encoding="utf-8")
            r = self.run_cli("check", "--profile", str(badp))
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("Saved", r.stderr)

    def test_unreadable_profile_exits_2(self):
        r = self.run_cli("check", "--profile", "/nonexistent/profile.yaml")
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
