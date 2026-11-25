---
name: daily-start
description: The daily ritual of the main session (Claude Code in Claude Desktop on the personal account) in the nghiep-pham-ecosys workspace. On "bắt đầu ngày làm việc" (or "start the day", "báo cáo sáng") it builds the morning report (calendar, job e-mails, board, jobs check, day-job progress, industry news), makes sure today's lessons are in the study book, and proposes the day's checklist. On "chốt ngày" it writes the daily score. Use it every working morning in the main session, when Nghiep asks for today's lesson, or at the end of the day. It does not cover the session start and end rituals (session), the Sunday review (weekly-review), or the job pipeline rules (jobs).
---

# daily-start

The main session runs the morning ritual; Claude Chat is the fallback (`docs/runbooks/main-session.md`).
Answer in Vietnamese.
First check the signed-in account (runbook, "Account check"): on the Team seat the personal Gmail is out of reach.
Every line of the report comes from a live call in this turn, or is labelled *unverified*.

## 1. Morning report ("bắt đầu ngày làm việc")

Gather in parallel, then write one short block per section, in this order:

1. **Lịch hôm nay.** `notion-calendar-list-events` (`notion-ecosys`, today 00:00–24:00, Asia/Ho_Chi_Minh), or the
   Google Calendar connector. Fixed blocks with times; the next free window for Claude Code work.
2. **Mail tuyển dụng.** Gmail connector, `newer_than:1d` (Monday: `newer_than:3d`), job-related senders and words.
   Exclude bot senders, follow `pageToken` until no page is left, and rescan at the start of the job-search block.
   Security alerts are filtered by the connector: say so instead of reporting none.
   For each reply: which application (by `#id` from `private/ops/jobs/applications.yaml`), what it asks, the proposed
   stage change. A stage change needs Nghiep's yes (`jobs`). Gmail not connected on this account → say so and skip.
3. **Board.** `gh project item-list` or `just board-export --stdout`: items `In progress` and due this week.
4. **Jobs.** `just jobs-check`: 30-day closure proposals, follow-ups, interview prep within 48 h.
5. **Day job (read-only).** The work block from the calendar, then the trackers through the Linear and Jira
   connectors: items assigned to Nghiep or updated in the last day, grouped as done / in progress / in review /
   blocked, one line each. Report in the session chat only: never write it to a file, commit, issue, Notion or the inbox
   (root `CLAUDE.md`). Never write to the trackers. No connector on this account → say so and skip.
6. **Tin ngành.** Two or three items from newsletters and alerts in Gmail from the last day, one line each with the
   link. No mail access → skip.
7. **Bài học hôm nay.** Check `private/ops/learn/so-hoc.md` has a section for each study block today (§2). Missing →
   write it now.
8. **Bài đăng.** Today's post in `projects/lab-to-prod/content/<week>/<date>-*/post.md` (`channels`), against the
   `<date>` entry of `published.json` on the `publish-state` branch, and the `publish.yml` runs of today. GitHub cron
   runs late or not at all (lab-to-prod#32), so a channel missing after 08:15 is reported with the fix: with Nghiep's
   yes, `gh workflow run publish.yml -R <org>/lab-to-prod -f event=daily`. A dispatch skips every channel already in
   `published.json`, so it never posts twice. Check the days before today in the same week too: a missed day is
   reported the same way.
   X (`x_manual`) is posted by the main session through Claude in Chrome, not by Claude Chat (Nghiep, 2026-11-24).
   The text, image and alt text come from the merged `x-schedule.md`, which Nghiep approved in the weekly content PR.
   Steps, from the lab-to-prod root: `python tools/state_sync.py pull`, `python -m publish.record_manual check --key <date> --channel x` and a search of the live profile; post
   with the image and alt text; reply with the blog link once the note URL returns 200; then `record` the post and
   the reply (key `<date>:reply`) and `python tools/state_sync.py push published.json`.
   Personal Facebook: every day the main session shares the day's Facebook Page post to Nghiep's personal profile
   through Claude in Chrome (Nghiep, 2026-11-25). Open the Page post URL from the `facebook` entry of
   `published.json`, check the share dialog shows his own name, Feed and Public, and press "Share now" with no added
   text. Check the profile timeline first so a day is never shared twice. No API and no record in `published.json`.
   Telegram stays skipped until its token is set: report it as "not configured", not as a missed post.
9. **Trang theo dõi.** Rebuild and republish the two private pages in `private/ops/pages/` (README there): the study
   book by day and the project map. Update the hand-written text of a repo in the project map when it shipped
   something since the last rebuild. Give both links in the report.

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
- After the lessons are written, rebuild the study-book page (`private/ops/pages/sohoc`) so each day has its tab.
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
