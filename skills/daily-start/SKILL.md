---
name: daily-start
description: The daily ritual of the hub (the long-running Claude Code Remote Control session) in the nghiep-pham-ecosys workspace. On "bắt đầu ngày làm việc" (or "start the day", "báo cáo sáng") it builds the morning report (calendar, job e-mails, board, jobs check, day-job reminder, industry news), makes sure today's lessons are in the study book, and proposes the day's checklist. On "chốt ngày" it writes the daily score. Use it every working morning in the hub, when Nghiep asks for today's lesson, or at the end of the day. It does not cover the session start and end rituals (session), the Sunday review (weekly-review), or the job pipeline rules (jobs).
---

# daily-start

The hub replaces Claude Chat's morning ritual from W48 (`docs/runbooks/hub.md`). Answer in Vietnamese.
Every line of the report comes from a live call in this turn, or is labelled *unverified*.

## 1. Morning report ("bắt đầu ngày làm việc")

Gather in parallel, then write one short block per section, in this order:

1. **Lịch hôm nay.** `notion-calendar-list-events` (`notion-ecosys`, today 00:00–24:00, Asia/Ho_Chi_Minh), or the
   Google Calendar connector. Fixed blocks with times; the next free window for Claude Code work.
2. **Mail tuyển dụng.** Gmail connector, `newer_than:1d` (Monday: `newer_than:3d`), job-related senders and words.
   For each reply: which application (by `#id` from `private/ops/jobs/applications.yaml`), what it asks, the proposed
   stage change. A stage change needs Nghiep's yes (`jobs`). Gmail not connected on this account → say so and skip.
3. **Board.** `gh project item-list` or `just board-export --stdout`: items `In progress` and due this week.
4. **Jobs.** `just jobs-check`: 30-day closure proposals, follow-ups, interview prep within 48 h.
5. **Day job (reminder only).** The work block from the calendar, one line. Never read day-job trackers, mail or
   repos from this workspace (root `CLAUDE.md`, spec §10.3).
6. **Tin ngành.** Two or three items from newsletters and alerts in Gmail from the last day, one line each with the
   link. No mail access → skip.
7. **Bài học hôm nay.** Check `private/ops/learn/so-hoc.md` has a section for each study block today (§2). Missing →
   write it now.

Then propose the day's checklist (3–6 items, each with "xong khi") from the master plan, `sessions.yaml`, the board
and the inbox. Nghiep's answer goes under "Nghiep's decisions" in `.tmp-session/checklist.md` (`session`).

## 2. Lessons in the study book

- File: `private/ops/learn/so-hoc.md`, newest section on top, right under the speaking-method section.
- Heading: `## DD/MM (Thứ) — <block> HH:MM: <topic>`. The blocks and their day topics come from
  `private/ops/plan/routine.yaml` (`blocks`) and the calendar event descriptions.
- Follow the shape of the newest section of the same block (for example English morning: timetable, Anki words,
  script, model answer to learn by heart; course blocks: the week's module, worked example, edge cases, a short quiz).
- Material comes from real work where the block says so (the day's lab-to-prod post, a merged PR). Never post graded
  course code anywhere public.
- Write the next working day's lessons at the evening close, so the morning only checks them.
- Commit `ops` changes through the normal flow (`ship`).

## 3. Close of day ("chốt ngày")

- Score: items done / items planned, by group (posts, job search, projects, study), with a percent.
- Append the line to `private/ops/learn/daily-score.md` and what was learned or missed to
  `private/ops/learn/lesson-log.md`.
- Then the session end ritual (`session`, End), which writes the inbox end line.

## 4. Limits

- Approval rules do not change: no e-mail, post, application or merge without Nghiep's own message (ADR 0003,
  ADR 0006 §1).
- On Saturday and Sunday: lessons and the Sunday review only; no code.
- Nothing from this ritual goes into a public repo except public-safe text (`core` §2 rule 8).
