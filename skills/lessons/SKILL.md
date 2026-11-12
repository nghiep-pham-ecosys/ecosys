---
name: lessons
description: The lesson log of the nghiep-pham-ecosys workspace. Write one rule the moment a root cause is found for a mistake caused by a wrong method, a wrong assumption or a skipped check, and read the lessons of an area before changing it. Covers the entry format (Rule, Why, Seen, Guard), where to write (public-safe skills/lessons/lessons.md or personal private/ops/lessons.md), pending lessons during a session, and turning a repeated lesson into a hook, check or test. Use it when Nghiep says "mistake", "wrong way", "again", "note this lesson", when a review finds a pattern bug, when an issue's premise turns out false, and before editing hooks, CI, tools or the job pipeline. It does not cover session logs (session) or the ship flow (ship).
---

# lessons

Log: [`lessons.md`](lessons.md) for public-safe lessons, `private/ops/lessons.md` for personal ones. Each entry is
**one rule**, not an incident diary.

| Section in the log | Read before |
|---|---|
| Working with agents | planning, running lanes, writing briefs, reporting to Nghiep |
| Verify and Done | saying something is done, writing tests, moving an item to Done |
| Shipping and CI | merging, editing workflows, hooks, the merge tool, git operations |
| Public-safe and privacy | writing anything in a public repo, a post, a README, a test fixture |
| Data and tools | editing `tools/`, YAML data files, migrations of `ops` data |

## 1. Read first

- Before changing an area, read its section above, in both logs.
- At session start (`session` step 4): the sections for the agreed items, plus `.tmp-session/lessons-pending.md` if
  the last session left one.
- A lesson that conflicts with the current request → raise it with Nghiep first. Do not skip it quietly.

## 2. When to write: immediately

Write at the moment the root cause is found, not at the end of the session. Write when the mistake came from:

- a wrong method or pattern (it worked, but the design was wrong);
- a wrong assumption: an issue's premise, memory, a file or field name, "probably because…";
- a verify step that was skipped and would have caught it;
- a change that broke an earlier decision nobody checked against.

Do not write: plain typos, mistakes an existing guard already catches, or session history (that goes in the log).

During a session, write to `.tmp-session/lessons-pending.md` with the same format. Move entries into the logs at the
end (`session` End step 3), so parallel lanes never edit the log file. Lanes do not edit the logs: they return
lessons in their result JSON (`lessons` field) and the orchestrator writes them.

## 3. Format

```markdown
### <Rule: a short imperative>
- Why: <symptom> → <root cause>.
- How: <what to do instead; optional, only when the heading is not enough>
- Seen: <repo>#<n> or <repo> PR #<n>, <YYYY-MM-DD>; add a line each time it happens again.
- Guard: <kind> <target>
```

`Guard:` is required. It says what stops the mistake next time (P7, "guards over good intentions"):

| Guard value | When |
|---|---|
| `hook <path>` · `ci <workflow/job>` · `test <path>` · `tool <path>` | a machine already blocks it; the path exists on `main` |
| `pending <repo>#<n>` | the guard is planned; the issue exists and is on the board |
| `none: judgement <why>` · `none: external <why>` · `none: one-off <why>` | nothing mechanical can catch it; reason of 3+ words |

Rules for entries:

- English, short, active voice. Code and command names unchanged.
- No secrets, no account ids, no tokens.
- `Seen` points to something a reader can open. In the public log, point only to public repos.
- The guard target is something that stays in the repo, never a helper in `.tmp-session/` (it gets deleted).

## 4. Public log or private log

Ask: **could this entry be published on the blog as it is?**

- Yes → `skills/lessons/lessons.md` (public `ecosys`). The rule must stand without the names behind it.
- No (it needs an employer, recruiter, person, salary, application or health detail to make sense) →
  `private/ops/lessons.md`. A general rule hidden inside a personal lesson can also go to the public log, rewritten
  with no names.
- Day-job lessons stay in the day-job's own log. Only the way of working may be re-derived here (spec §10.3).

## 5. Repeat → guard

A lesson that can be checked by a machine is the best kind.

1. A test, CI check, hook or lint rule is possible and in scope of the current PR → build it now, and set `Guard:` to it.
2. Out of scope → propose an issue (ask Nghiep, `core` §6) and set `Guard: pending <repo>#<n>`.
3. **A lesson seen again** (a second `Seen` line) whose mistake a machine can detect → the guard is built in this
   session or gets a `pending` issue on next week's board. Adding another `Seen` line alone is not enough. Only
   `none:` entries may simply collect `Seen` lines.
4. When a merged guard blocks the **whole class** of the mistake (not just one case), move the entry to
   `skills/lessons/guards.md` (create the file on first use) in the same PR, with the guard path, and name the guard
   in the commit message. The skill text that described the rule shrinks to one line naming the guard.
5. Before loosening or removing a guard, read its entry in `guards.md`.

## 6. End of session

In `session` End step 3: move `.tmp-session/lessons-pending.md` into the right log and section. Check each entry has
a valid `Guard:`. Scan the session for mistakes that have no entry yet. Note in the memory block: "lessons: X new,
Y became guards".

## Maintenance

Follow `skills/README.md`. Sections of the log can be added when an area grows; update the table at the top.
