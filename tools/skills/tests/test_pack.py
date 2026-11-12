import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent / "pack"
sys.path.insert(0, str(HERE.parent))
from _packlib import SkillError, pack_all, validate  # noqa: E402


def make_skill(root: Path, name: str, desc: str = "Does a synthetic thing for Example Co.", extra: dict | None = None,
               fm_name: str | None = None) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {fm_name or name}\ndescription: {desc}\n---\n\n# {name}\n", encoding="utf-8")
    for rel, text in (extra or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return d


class PackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.skills = self.tmp / "skills"
        self.out = self.tmp / "dist"

    def test_zip_has_one_folder_with_skill_md_and_references(self):
        make_skill(self.skills, "acme-flow", extra={"references/guide.md": "x", "__pycache__/a.pyc": "y"})
        (self.skills / "README.md").parent.mkdir(exist_ok=True)
        (self.skills / "README.md").write_text("index", encoding="utf-8")
        packed = pack_all(self.skills, self.out)
        self.assertEqual([p.name for p in packed], ["acme-flow"])
        names = zipfile.ZipFile(self.out / "acme-flow.zip").namelist()
        self.assertEqual(sorted(names), ["acme-flow/SKILL.md", "acme-flow/references/guide.md"])

    def test_output_is_deterministic(self):
        make_skill(self.skills, "acme-flow", extra={"references/a.md": "a"})
        pack_all(self.skills, self.out)
        first = hashlib.sha256((self.out / "acme-flow.zip").read_bytes()).hexdigest()
        os.utime(self.skills / "acme-flow" / "SKILL.md", (1, 1))
        pack_all(self.skills, self.out)
        self.assertEqual(first, hashlib.sha256((self.out / "acme-flow.zip").read_bytes()).hexdigest())

    def test_name_must_match_folder(self):
        d = make_skill(self.skills, "acme-flow", fm_name="other")
        with self.assertRaises(SkillError):
            validate(d)

    def test_name_format(self):
        d = make_skill(self.skills, "Acme_Flow")
        with self.assertRaises(SkillError):
            validate(d)

    def test_description_limit(self):
        d = make_skill(self.skills, "acme-flow", desc="x" * 1025)
        with self.assertRaises(SkillError):
            validate(d)
        d2 = make_skill(self.skills, "acme-ok", desc="x" * 1024)
        validate(d2)

    def test_description_rejects_angle_brackets(self):
        d = make_skill(self.skills, "acme-flow", desc='Use "Refs <repo>#<n>" in commits.')
        with self.assertRaises(SkillError):
            validate(d)

    def test_nothing_written_when_one_skill_is_invalid(self):
        make_skill(self.skills, "acme-a")
        make_skill(self.skills, "acme-b", desc="")
        with self.assertRaises(SkillError):
            pack_all(self.skills, self.out)
        self.assertFalse((self.out / "acme-a.zip").exists())

    def test_only_selected_and_unknown_name(self):
        make_skill(self.skills, "acme-a")
        make_skill(self.skills, "acme-b")
        self.assertEqual([p.name for p in pack_all(self.skills, self.out, ["acme-b"])], ["acme-b"])
        with self.assertRaises(SkillError):
            pack_all(self.skills, self.out, ["nope"])

    def test_cli_exit_codes(self):
        make_skill(self.skills, "acme-a")
        ok = subprocess.run([sys.executable, str(TOOL), "--skills", str(self.skills), "--out", str(self.out)],
                            capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("1 zip(s)", ok.stdout)
        make_skill(self.skills, "acme-bad", desc="")
        bad = subprocess.run([sys.executable, str(TOOL), "--skills", str(self.skills), "--out", str(self.out)],
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)


if __name__ == "__main__":
    unittest.main()
