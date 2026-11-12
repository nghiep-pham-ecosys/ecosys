"""Logic for tools/jobs/check: validate the job pipeline and list what is due.

Deterministic, stdlib + PyYAML only, no LLM. The tool reads the data file and
never writes it. Spec: docs/spec.md section 5.2.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

STAGES = (
    "lead", "applied", "screen", "interview", "offer", "accepted",
    "declined", "rejected", "withdrawn", "ghosted", "skipped",
)
# Stages that end the pipeline. ghosted can be revived, but is closed until then.
TERMINAL = frozenset({"accepted", "declined", "rejected", "withdrawn", "ghosted", "skipped"})
# Stages a history may start with.
START_STAGES = frozenset({"lead", "applied"})
TRANSITIONS = {
    "lead": {"applied", "skipped"},
    "applied": {"screen", "interview", "rejected", "withdrawn", "ghosted"},
    "screen": {"interview", "rejected", "withdrawn", "ghosted"},
    "interview": {"offer", "rejected", "withdrawn", "ghosted"},
    "offer": {"accepted", "declined"},
    "ghosted": {"screen", "interview"},
}
REQUIRED = (
    "id", "company", "role", "stage", "applied_on", "last_contact_on",
    "channel", "pay", "cv", "next", "notes",
)
OPTIONAL = (
    "history", "source", "link", "follow_up_on", "interview_on",
    "closed_reason", "hold_close", "hold_14d",
)
DATE_FIELDS = ("applied_on", "last_contact_on", "follow_up_on")
TEXT_FIELDS = ("company", "role", "channel", "pay", "cv", "next", "notes",
               "source", "link", "closed_reason", "hold_close", "hold_14d")
# Days without contact before an applied/screen row is proposed as ghosted.
# Changed from 14 to 30 on 2026-11-12: foreign employers reply slowly.
CLOSURE_DAYS = 30
HOLD_FIELD = "hold_close"
# Deprecated name of HOLD_FIELD, still read (with a warning) until the data is renamed.
DEPRECATED_HOLD_FIELD = "hold_14d"
PREP_DAYS = 2  # 48 h, counted in calendar days from today
_WAIT_RE = re.compile(r"^\s*wait\b", re.IGNORECASE)


class DataError(Exception):
    """The data file cannot be read as a list of records."""


# ---------- loading and parsing ----------

def load_list(path: str | Path, what: str) -> list[Any]:
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise DataError(f"cannot read {what} file {p}: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise DataError(f"{what} file {p} is not valid YAML: {exc}") from exc
    if data is None:
        return []
    if not isinstance(data, list):
        raise DataError(f"{what} file {p} must be a YAML list at the top level")
    return data


def parse_date(value: Any) -> dt.date | None:
    """Return a date, None for empty, or raise ValueError."""
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        s = value.strip()
        try:
            return dt.date.fromisoformat(s)
        except ValueError:
            return dt.datetime.fromisoformat(s).date()
    raise ValueError(f"not a date: {value!r}")


def step_on(step: dict) -> Any:
    """History date. YAML 1.1 reads an unquoted `on:` key as boolean True."""
    return step.get("on", step.get(True))


def is_wait(next_text: Any) -> bool:
    return not str(next_text or "").strip() or bool(_WAIT_RE.match(str(next_text)))


def label(rec: dict, width: int = 70) -> str:
    text = f"#{rec.get('id')} {rec.get('company', '')} — {rec.get('role', '')}"
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


# ---------- validation ----------

def validate(records: list[Any], today: dt.date,
             skipped: list[Any] | None = None) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors make the tool exit 1."""
    errors: list[str] = []
    warnings: list[str] = []
    seen: dict[int, int] = {}

    for idx, rec in enumerate(records):
        where = f"record[{idx}]"
        if not isinstance(rec, dict):
            errors.append(f"{where}: not a mapping")
            continue
        rid = rec.get("id")
        if isinstance(rid, bool) or not isinstance(rid, int):
            errors.append(f"{where}: id must be an integer, got {rid!r}")
        else:
            where = f"#{rid}"
            if rid in seen:
                errors.append(f"{where}: duplicate id (also record[{seen[rid]}])")
            else:
                seen[rid] = idx

        for key in REQUIRED:
            if key not in rec:
                errors.append(f"{where}: missing field '{key}'")
        for key in rec:
            if key not in REQUIRED and key not in OPTIONAL:
                warnings.append(f"{where}: unknown field '{key}'")
        if DEPRECATED_HOLD_FIELD in rec:
            if HOLD_FIELD in rec:
                warnings.append(f"{where}: both '{HOLD_FIELD}' and deprecated '{DEPRECATED_HOLD_FIELD}' are set; "
                                f"'{HOLD_FIELD}' is used, remove '{DEPRECATED_HOLD_FIELD}'")
            else:
                warnings.append(f"{where}: field '{DEPRECATED_HOLD_FIELD}' is deprecated, rename it to '{HOLD_FIELD}'")
        for key in TEXT_FIELDS:
            if key in rec and rec[key] is not None and not isinstance(rec[key], str):
                errors.append(f"{where}: '{key}' must be a string")
        if isinstance(rec.get("company"), str) and not rec["company"].strip():
            errors.append(f"{where}: company is empty")

        stage = rec.get("stage")
        if stage not in STAGES:
            errors.append(f"{where}: unknown stage {stage!r}")

        dates: dict[str, dt.date | None] = {}
        for key in DATE_FIELDS:
            if key in rec:
                try:
                    dates[key] = parse_date(rec[key])
                except ValueError:
                    errors.append(f"{where}: '{key}' is not an ISO date: {rec[key]!r}")
        if "interview_on" in rec:
            try:
                parse_date(rec["interview_on"])
            except ValueError:
                errors.append(f"{where}: 'interview_on' is not an ISO date/datetime: {rec['interview_on']!r}")

        applied = dates.get("applied_on")
        last = dates.get("last_contact_on")
        if stage in STAGES and stage not in ("lead", "skipped") and applied is None:
            warnings.append(f"{where}: stage {stage} but applied_on is empty")
        if applied and last and last < applied:
            warnings.append(f"{where}: last_contact_on {last} is before applied_on {applied}")
        for key in ("applied_on", "last_contact_on"):
            value = dates.get(key)
            if value and value > today:
                warnings.append(f"{where}: '{key}' {value} is after today {today}")
        if stage in TERMINAL and stage != "skipped" and not str(rec.get("closed_reason") or "").strip():
            warnings.append(f"{where}: closed stage {stage} without closed_reason")

        if "history" in rec:
            errors.extend(_check_history(where, rec.get("history"), stage))

    if skipped is not None:
        errors.extend(_check_skipped(skipped, seen))
    return errors, warnings


def _check_history(where: str, history: Any, stage: Any) -> list[str]:
    errs: list[str] = []
    if not isinstance(history, list) or not history:
        return [f"{where}: history must be a non-empty list"]
    prev_stage = None
    prev_on = None
    for i, step in enumerate(history):
        w = f"{where}: history[{i}]"
        if not isinstance(step, dict):
            errs.append(f"{w}: not a mapping")
            return errs
        s = step.get("stage")
        if s not in STAGES:
            errs.append(f"{w}: unknown stage {s!r}")
            return errs
        raw_on = step_on(step)
        try:
            on = parse_date(raw_on)
        except ValueError:
            errs.append(f"{w}: 'on' is not an ISO date: {raw_on!r}")
            on = None
        if on is None and raw_on in (None, ""):
            errs.append(f"{w}: 'on' is missing")
        if prev_stage is None:
            if s not in START_STAGES:
                errs.append(f"{w}: history must start at lead or applied, not {s}")
        elif s not in TRANSITIONS.get(prev_stage, set()):
            errs.append(f"{w}: illegal transition {prev_stage} → {s}")
        if prev_on and on and on < prev_on:
            errs.append(f"{w}: date {on} is before the previous step {prev_on}")
        prev_stage, prev_on = s, on or prev_on
    if prev_stage != stage:
        errs.append(f"{where}: last history stage {prev_stage} does not match stage {stage}")
    return errs


def _check_skipped(skipped: list[Any], app_ids: dict[int, int]) -> list[str]:
    errs: list[str] = []
    seen: set[int] = set()
    for i, row in enumerate(skipped):
        w = f"skipped[{i}]"
        if not isinstance(row, dict):
            errs.append(f"{w}: not a mapping")
            continue
        for key in ("position", "reason"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                errs.append(f"{w}: '{key}' must be a non-empty string")
        tid = row.get("tracker_id")
        if tid is not None:
            if isinstance(tid, bool) or not isinstance(tid, int):
                errs.append(f"{w}: tracker_id must be an integer")
            elif tid in app_ids:
                errs.append(f"{w}: tracker_id {tid} is also an application id")
            elif tid in seen:
                errs.append(f"{w}: duplicate tracker_id {tid}")
            else:
                seen.add(tid)
    return errs


# ---------- reports ----------

def _contact_basis(rec: dict) -> dt.date | None:
    dates = [d for d in (parse_date(rec.get("last_contact_on")), parse_date(rec.get("applied_on"))) if d]
    return max(dates) if dates else None


def hold_reason(rec: dict) -> str:
    """The closure hold text: hold_close, else the deprecated hold_14d, else ""."""
    for key in (HOLD_FIELD, DEPRECATED_HOLD_FIELD):
        if key in rec:
            return str(rec.get(key) or "").strip()
    return ""


def closures(records: list[dict], today: dt.date, days_limit: int = CLOSURE_DAYS,
             ) -> tuple[list[tuple[dict, int, dt.date]], list[dict]]:
    """Closure rule: applied/screen rows with no contact for days_limit days or more.

    Returns (proposed, held). held = would qualify but a hold reason is set.
    """
    proposed, held = [], []
    for rec in records:
        if rec.get("stage") not in ("applied", "screen"):
            continue
        basis = _contact_basis(rec)
        if basis is None:
            continue
        days = (today - basis).days
        if days < days_limit:
            continue
        if hold_reason(rec):
            held.append(rec)
        else:
            proposed.append((rec, days, basis))
    proposed.sort(key=lambda t: (-t[1], t[0]["id"]))
    return proposed, held


def closure_title(days_limit: int = CLOSURE_DAYS) -> str:
    return f"{days_limit}-DAY CLOSURES (proposed ghosted, Nghiep confirms)"


def week_bounds(today: dt.date) -> tuple[dt.date, dt.date]:
    monday = today - dt.timedelta(days=today.isoweekday() - 1)
    return monday, monday + dt.timedelta(days=6)


def followups(records: list[dict], today: dt.date) -> list[tuple[dict, dt.date, bool]]:
    """Open rows with follow_up_on in this ISO week (Mon–Sun) or overdue."""
    _, sunday = week_bounds(today)
    out = []
    for rec in records:
        if rec.get("stage") in TERMINAL:
            continue
        due = parse_date(rec.get("follow_up_on"))
        if due is None or due > sunday:
            continue
        out.append((rec, due, due < today))
    out.sort(key=lambda t: (t[1], t[0]["id"]))
    return out


def interview_prep(records: list[dict], today: dt.date) -> list[tuple[dict, str]]:
    """Open rows with interview_on from today through today + 2 days."""
    out = []
    for rec in records:
        if rec.get("stage") in TERMINAL:
            continue
        raw = rec.get("interview_on")
        day = parse_date(raw)
        if day is None:
            continue
        if today <= day <= today + dt.timedelta(days=PREP_DAYS):
            out.append((rec, str(raw)))
    out.sort(key=lambda t: (t[1], t[0]["id"]))
    return out


def stale_interviews(records: list[dict], today: dt.date) -> list[dict]:
    """Open rows whose interview_on is in the past: the stage likely needs an update."""
    return [r for r in records
            if r.get("stage") not in TERMINAL
            and (d := parse_date(r.get("interview_on"))) is not None and d < today]


def next_actions(records: list[dict]) -> list[dict]:
    rows = [r for r in records if r.get("stage") not in TERMINAL and not is_wait(r.get("next"))]
    order = {s: i for i, s in enumerate(STAGES)}
    rows.sort(key=lambda r: (-order.get(r.get("stage"), 0), r["id"]))
    return rows


def stage_counts(records: list[dict]) -> Counter:
    return Counter(r.get("stage") for r in records if isinstance(r, dict))


def render(records: list[Any], today: dt.date, errors: list[str], warnings: list[str],
           data_path: str, validate_only: bool = False, skipped_count: int | None = None,
           close_after_days: int = CLOSURE_DAYS) -> str:
    iso = today.isocalendar()
    out = [f"jobs check · data={data_path} · today={today} ({today:%a}, week {iso.year}-W{iso.week:02d})", ""]

    out.append("VALIDATION")
    extra = f", skipped list {skipped_count}" if skipped_count is not None else ""
    out.append(f"  {len(records)} records{extra}: {len(errors)} errors, {len(warnings)} warnings")
    out += [f"  ERROR   {e}" for e in errors]
    out += [f"  warning {w}" for w in warnings]
    if validate_only:
        return "\n".join(out) + "\n"
    if errors:
        out += ["", "Other sections skipped: fix the validation errors first."]
        return "\n".join(out) + "\n"

    proposed, held = closures(records, today, close_after_days)
    out += ["", closure_title(close_after_days)]
    if not proposed:
        out.append("  (none)")
    for rec, days, basis in proposed:
        out.append(f"  {label(rec)} · {rec['stage']} · last contact {basis} · {days} days")
    for rec in held:
        out.append(f"  held  {label(rec)} · {HOLD_FIELD}: {hold_reason(rec)}")

    monday, sunday = week_bounds(today)
    out += ["", f"FOLLOW-UPS DUE THIS WEEK ({monday} to {sunday}, plus overdue)"]
    fu = followups(records, today)
    if not fu:
        out.append("  (none)")
    for rec, due, overdue in fu:
        flag = "OVERDUE " if overdue else ""
        out.append(f"  {flag}{due} {label(rec)} · next: {rec.get('next', '')}")

    out += ["", f"INTERVIEW PREP (within 48h: {today} to {today + dt.timedelta(days=PREP_DAYS)})"]
    prep = interview_prep(records, today)
    if not prep:
        out.append("  (none)")
    for rec, when in prep:
        out.append(f"  {when} {label(rec)} · {rec['stage']}")
    for rec in stale_interviews(records, today):
        out.append(f"  past  {rec.get('interview_on')} {label(rec)} · stage still {rec['stage']}: update it")

    out += ["", "NEXT ACTIONS"]
    na = next_actions(records)
    if not na:
        out.append("  (none)")
    for rec in na:
        out.append(f"  {label(rec)} · {rec['stage']}")
        out.append(f"      → {' '.join(str(rec['next']).split())}")

    counts = stage_counts(records)
    out += ["", "STAGES"]
    out.append("  " + " · ".join(f"{s} {counts[s]}" for s in STAGES if counts[s]))
    return "\n".join(out) + "\n"
