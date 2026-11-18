"""Profile facts to CV: load, check, audit and resolve a variant (spec §5.1).

The profile is private data (vault/profile/profile.yaml). This module only reads it.
Rules checked:
- every fact id is unique, lower-case kebab, and starts with its section prefix;
- every id a variant names exists and is not retired;
- every number in the profile sits inside a fact that has an id (the nearest dict with `id`).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

# Section name -> required id prefix. Lists of facts unless noted.
SECTIONS = {
    "headlines": "head-",
    "availability": "avail-",
    "summaries": "sum-",
    "skills": "skill-",
    "work": "work-",
    "projects": "proj-",
    "research": "res-",
    "education": "edu-",
    "certs": "cert-",
    "languages": "lang-",
}
HIGHLIGHT_PREFIX = "ach-"
ID_RX = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
NUMBER_RX = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)*\+?(?![A-Za-z])")
# Variant keys that hold a list of fact ids from one section.
VARIANT_LISTS = {
    "summary": "summaries",
    "skills": "skills",
    "projects": "projects",
    "research": "research",
    "education": "education",
    "certs": "certs",
    "languages": "languages",
}
VARIANT_SINGLES = {"headline": "headlines", "availability": "availability"}


class ProfileError(Exception):
    pass


def load(path: str | Path) -> dict:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ProfileError(f"cannot read profile: {exc.__class__.__name__}") from None
    if not isinstance(data, dict):
        raise ProfileError("profile must be a mapping")
    return data


def _facts(profile: dict):
    """Yield (section, fact) for every fact, highlights included."""
    basics = profile.get("basics")
    if isinstance(basics, dict):
        yield "basics", basics
    for section in SECTIONS:
        for fact in profile.get(section) or []:
            if isinstance(fact, dict):
                yield section, fact
                if section == "work":
                    for h in fact.get("highlights") or []:
                        if isinstance(h, dict):
                            yield "highlights", h


def index(profile: dict) -> dict[str, dict]:
    return {f["id"]: f for _, f in _facts(profile) if isinstance(f.get("id"), str)}


def _numbers(node, owner, out, path):
    if isinstance(node, dict):
        owner = node.get("id", owner) if isinstance(node.get("id"), str) else owner
        for k, v in node.items():
            if k == "id":
                continue
            _numbers(v, owner, out, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _numbers(v, owner, out, f"{path}[{i}]")
    elif isinstance(node, (str, int, float)) and not isinstance(node, bool):
        for m in NUMBER_RX.finditer(str(node)):
            out.append((owner, m.group(0), path))


def numbers(profile: dict) -> list[tuple[str | None, str, str]]:
    """Every number outside `variants` and `version`: (fact id or None, number, path)."""
    out: list[tuple[str | None, str, str]] = []
    for key, value in profile.items():
        if key in ("variants", "version"):
            continue
        _numbers(value, None, out, key)
    return out


def check(profile: dict) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    basics = profile.get("basics")
    if not isinstance(basics, dict) or basics.get("id") != "basics" or not basics.get("name"):
        errors.append("basics: needs id 'basics' and a name")
    for section, fact in _facts(profile):
        if section == "basics":
            continue
        fid = fact.get("id")
        prefix = HIGHLIGHT_PREFIX if section == "highlights" else SECTIONS[section]
        if not isinstance(fid, str) or not ID_RX.match(fid):
            errors.append(f"{section}: bad or missing id {fid!r}")
            continue
        if not fid.startswith(prefix):
            errors.append(f"{fid}: id in {section} must start with '{prefix}'")
        if fid in seen:
            errors.append(f"{fid}: duplicate id (also in {seen[fid]})")
        seen[fid] = section
    for owner, num, path in numbers(profile):
        if owner is None:
            errors.append(f"{path}: number {num} is not inside a fact with an id")
    facts = index(profile)
    variants = profile.get("variants") or {}
    if not isinstance(variants, dict) or not variants:
        errors.append("variants: at least one variant is needed")
        variants = {}
    for name, v in variants.items():
        errors.extend(_check_variant(name, v, facts))
    return errors


def _ref(name, fid, section, facts, prefix):
    f = facts.get(fid)
    if f is None:
        return f"variant {name}: unknown id {fid!r}"
    if f.get("retired"):
        return f"variant {name}: {fid} is retired"
    if not str(fid).startswith(prefix):
        return f"variant {name}: {fid} is not a {section} fact"
    return None


def _check_variant(name, v, facts):
    errs = []
    if not isinstance(v, dict):
        return [f"variant {name}: must be a mapping"]
    for key, section in VARIANT_SINGLES.items():
        if key in v:
            e = _ref(name, v[key], section, facts, SECTIONS[section])
            if e:
                errs.append(e)
    if "headline" not in v:
        errs.append(f"variant {name}: needs a headline")
    for key, section in VARIANT_LISTS.items():
        for fid in v.get(key) or []:
            e = _ref(name, fid, section, facts, SECTIONS[section])
            if e:
                errs.append(e)
    for item in v.get("work") or []:
        if not isinstance(item, dict):
            errs.append(f"variant {name}: work entries need id and highlights")
            continue
        e = _ref(name, item.get("id"), "work", facts, "work-")
        if e:
            errs.append(e)
            continue
        own = {h.get("id") for h in facts[item["id"]].get("highlights") or []}
        for hid in item.get("highlights") or []:
            if hid not in own:
                errs.append(f"variant {name}: {hid} is not a highlight of {item['id']}")
            elif facts[hid].get("retired"):
                errs.append(f"variant {name}: {hid} is retired")
    return errs


def resolve(profile: dict, variant: str) -> dict:
    """Flatten one variant into the data the template prints, in order."""
    variants = profile.get("variants") or {}
    if variant not in variants:
        raise ProfileError(f"unknown variant {variant!r}; known: {', '.join(sorted(variants)) or 'none'}")
    v = variants[variant]
    facts = index(profile)

    def texts(key):
        return [facts[f]["text"] for f in v.get(key) or []]

    b = profile["basics"]
    out = {
        "name": b["name"],
        "headline": facts[v["headline"]]["text"],
        "contact": [x for x in (b.get("location"), facts[v["availability"]]["text"] if v.get("availability") else None,
                                b.get("email"), b.get("phone")) if x],
        "links": [{"label": l["label"], "url": l["url"]} for l in b.get("links") or []],
        "summary": texts("summary"),
        "skills": [{"area": facts[f]["area"], "items": facts[f]["items"]} for f in v.get("skills") or []],
        "work": [],
        "projects": [{"name": facts[f]["name"], "text": facts[f]["text"], "url": facts[f].get("url", "")}
                     for f in v.get("projects") or []],
        "research": texts("research"),
        "education": texts("education"),
        "certs": texts("certs"),
        "languages": texts("languages"),
    }
    for item in v.get("work") or []:
        w = facts[item["id"]]
        out["work"].append({
            "org": w["org"], "role": w["role"], "dates": f"{w['start']} – {w['end']}", "place": w.get("place", ""),
            "highlights": [facts[h]["text"] for h in item.get("highlights") or []],
        })
    return out


def variant_ids(profile: dict, variant: str) -> set[str]:
    """Every fact id one variant prints (basics included)."""
    v = profile["variants"][variant]
    ids = {"basics"}
    for key in VARIANT_SINGLES:
        if v.get(key):
            ids.add(v[key])
    for key in VARIANT_LISTS:
        ids.update(v.get(key) or [])
    for item in v.get("work") or []:
        ids.add(item["id"])
        ids.update(item.get("highlights") or [])
    return ids
