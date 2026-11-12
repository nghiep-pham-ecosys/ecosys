---
name: weekly-review
description: The Sunday weekly review of the nghiep-pham-ecosys workspace. Gathers hours planned versus done per area, items done with evidence, items moved out, the jobs funnel, deadlines in the next 14 days, content published versus planned, red automations and plan-limit hits; checks next week's plan against the budgets and WIP limits in private/ops/plan/capacity.yaml; writes private/ops/reviews/YYYY-Www.md and sets next week's board items. Use it on Sundays, when Nghiep asks to plan the week, when there are "too many threads", when a new project or item wants to start, or when a WIP or budget question comes up. It does not cover the daily session rituals (session), single application decisions (jobs), or merging work (ship).
---

# weekly-review

Capacity first (P1): the plan shows what will **not** be done this week. Nghiep finishes the review in 30 minutes or
less. The draft does the counting so he only decides.

## 1. When and who

- Sunday, for the ISO week that starts on Monday.
- The draft is produced by a Claude scheduled task from `ops` files and the board **[P1]**. Until that task exists,
  the draft is made in a session with this skill.
- Nghiep finishes it: confirms moves, closures and the plan. The agent never sets a plan Nghiep has not seen.

## 2. Inputs

| Input | Source |
|---|---|
| Budgets, WIP limits, buffer | `private/ops/plan/capacity.yaml` |
| Planned, done, in progress, moved | the board: items with `Week` = this week, `Status`, `Estimate (h)`, `Evidence` |
| Jobs funnel, 30-day closures | `just jobs-check` on `private/ops/jobs/applications.yaml` |
| Deadlines in the next 14 days | `private/ops/learn/deadlines.yaml` + `Due` on board items |
| Content published vs planned | the lab-to-prod calendar and its published posts |
| Automations | `private/ops/automations.md`; red runs: `gh run list --status failure` on repos with scheduled workflows |
| Plan-limit hits, hours actually spent | the week's session logs `private/ops/sessions/*.md` |
| Hours the calendar already commits per area | next week's events via the Notion Calendar connector, mapped to areas in `private/ops/plan/routine.yaml` (refresh the file when blocks changed) |
| Last week's decisions | the previous `private/ops/reviews/YYYY-Www.md` |

Every number in the draft names its source. A number that could not be checked is marked *unverified*.

## 3. Capacity and WIP rules (spec §2)

- **Area budget:** the sum of `Estimate (h)` of an area's items set to `This week` must not exceed that area's
  `hours` in `capacity.yaml`.
- **Buffer:** `buffer_pct` of the total budget stays unplanned (interviews, surprises). Do not assign items to it.
- **WIP limit** (MUST): an area has at most `wip` items in `In progress`. A new item waits in `Next` until one
  finishes or is dropped. The review and the digest list every area over its limit.
- **Every item has an estimate.** An item with no `Estimate (h)` cannot be planned; estimate it or leave it in `Next`.
- **Deadlines first:** items with a hard deadline (course, exam, application follow-up) are planned before the rest.
- **One new project at a time:** a new side project enters `lab` only when another is set to `Paused` with a reason.
- **Day job:** one `work-block` item per week with the hours, so the week adds up. No day-job tasks on the board.
- **Over budget → the plan is refused.** The draft lists what moves out (back to `Next`, or `Dropped` with a reason)
  until every area fits. Nghiep chooses among the proposals.

Guard: the capacity check in the review (by hand until `tools/board` has a plan check; then this section shrinks to
the tool's name). Recurring work (daily posts, daily study) is one weekly item with its total hours.

## 4. Steps

1. **Gather** the inputs of §2. Run `just jobs-check` and `just ws-status`. Sum next week's calendar hours per area
   and put them next to the `capacity.yaml` budgets: an area whose calendar hours exceed its budget is a decision for
   Nghiep (raise the budget or cut blocks), never silently accepted.
2. **Close the week.** For each item planned this week: done with evidence, still in progress (what is left), moved
   out (why). Hours planned vs done per area, from estimates and session logs.
3. **Funnel and deadlines.** Applications sent, replies, interviews, closures proposed by the 30-day rule (Nghiep
   confirms each). Deadlines in the next 14 days, those within 48 h at the top.
4. **Automations.** Red or missed runs. A scheduled task not listed in `automations.md` is proposed for disabling;
   Nghiep disables it.
5. **Plan-limit hits.** Days when Claude plan limits were hit, and what moved because of it (spec §7).
6. **Draft next week** within the rules of §3: deadlines first, then unfinished `In progress` items, then `Next` by
   priority. Show the sum per area against the budget, and the list of what does not fit.
7. **Nghiep decides.** Apply his choices only: set items to `This week` and their `Week`, move the rest.
8. **Write** `private/ops/reviews/YYYY-Www.md` with the template in
   [`references/template.md`](references/template.md). Commit it to `ops` through the normal flow (`ship`).
9. **Monthly:** the first review of each month also reviews the skill set (`skills/README.md` Maintenance) and the
   real numbers in `capacity.yaml`.

## 5. First review

The first review sets the real numbers in `capacity.yaml` (the defaults come from spec §2.1) and settles open
decisions that the spec defers to it, for example whether LinkedIn guest endpoints stay in the job sources
(`jobs/references/sources.md`).

## Maintenance

Follow `skills/README.md`. When the scheduled draft task or `tools/board` plan check exists, replace the manual
steps here with their names.
