"""Pack each skill under skills/<name>/ into dist/skills/<name>.zip for upload to Claude (claude.ai, Desktop).

The zip holds one top-level folder named after the skill, with SKILL.md at its root and any references.
Archives are deterministic: sorted entries and a fixed timestamp, so an unchanged skill gives the same bytes.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import yaml

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_DESCRIPTION = 1024
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
SKIP_PARTS = {"__pycache__", ".DS_Store"}


@dataclass
class Packed:
    name: str
    path: Path
    files: int


class SkillError(ValueError):
    pass


def read_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SkillError(f"{skill_md}: missing YAML frontmatter")
    try:
        _, block, _ = text.split("---\n", 2)
    except ValueError as exc:
        raise SkillError(f"{skill_md}: unterminated frontmatter") from exc
    data = yaml.safe_load(block) or {}
    if not isinstance(data, dict):
        raise SkillError(f"{skill_md}: frontmatter is not a mapping")
    return data


def validate(skill_dir: Path) -> dict:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise SkillError(f"{skill_dir}: no SKILL.md")
    fm = read_frontmatter(skill_md)
    name, desc = fm.get("name"), fm.get("description")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise SkillError(f"{skill_md}: name must be lower-case letters, digits and hyphens (max 64)")
    if name != skill_dir.name:
        raise SkillError(f"{skill_md}: name '{name}' does not match folder '{skill_dir.name}'")
    if not isinstance(desc, str) or not desc.strip():
        raise SkillError(f"{skill_md}: description is missing")
    if "<" in desc or ">" in desc:
        raise SkillError(f"{skill_md}: description cannot contain '<' or '>' (Claude reads them as XML tags)")
    if len(desc) > MAX_DESCRIPTION:
        raise SkillError(f"{skill_md}: description is {len(desc)} characters (max {MAX_DESCRIPTION})")
    return fm


def skill_files(skill_dir: Path) -> list[Path]:
    files = []
    for p in sorted(skill_dir.rglob("*")):
        if p.is_symlink():
            raise SkillError(f"{p}: symlinks are not packed")
        if p.is_file() and not (set(p.relative_to(skill_dir).parts) & SKIP_PARTS) and p.suffix != ".pyc":
            files.append(p)
    return files


def pack_one(skill_dir: Path, out_dir: Path) -> Packed:
    validate(skill_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{skill_dir.name}.zip"
    files = skill_files(skill_dir)
    tmp = target.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            arcname = f"{skill_dir.name}/{f.relative_to(skill_dir).as_posix()}"
            info = zipfile.ZipInfo(arcname, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, f.read_bytes())
    tmp.replace(target)
    return Packed(skill_dir.name, target, len(files))


def find_skills(skills_root: Path, only: list[str] | None = None) -> list[Path]:
    dirs = [d for d in sorted(skills_root.iterdir()) if d.is_dir() and (d / "SKILL.md").is_file()]
    if only:
        wanted = set(only)
        missing = wanted - {d.name for d in dirs}
        if missing:
            raise SkillError(f"unknown skill(s): {', '.join(sorted(missing))}")
        dirs = [d for d in dirs if d.name in wanted]
    return dirs


def pack_all(skills_root: Path, out_dir: Path, only: list[str] | None = None) -> list[Packed]:
    skills = find_skills(skills_root, only)
    for d in skills:  # validate everything before writing anything
        validate(d)
    return [pack_one(d, out_dir) for d in skills]
