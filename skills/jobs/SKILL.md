---
name: jobs
description: The job search pipeline of the nghiep-pham-ecosys workspace. Covers where application data lives (private ops only), the stages and legal transitions, the 30-day rule, the per-application flow from lead to follow-up, the form-filling rules (Claude fills, Nghiep uploads, ticks, solves CAPTCHAs and submits), the skip rules, tools/jobs/check, and the scan sources. Use it for a job search scan, a new lead, an application form, a recruiter reply, a follow-up, an interview, or when Nghiep asks which applications to close. It does not cover CV content or tailoring (cv, P1), profile facts (vault, P1), the Sunday funnel numbers (weekly-review), or e-mail and post approval in general (core rule 7).
---

# jobs

Everything about applications, employers, recruiters and pay stays in the private `ops` repo (spec §5.2, §10.2).
This skill and its references are public: they hold the method only, never a name or a number from a real application.

## 1. Data homes

| What | Where |
|---|---|
| Applications (source of truth) | `private/ops/jobs/applications.yaml` |
| Seen and skipped postings (not to be reviewed again) | `private/ops/jobs/skipped.yaml` |
| Full rules, including pay expectations and named exceptions | `private/ops/jobs/rules.md` |
| Data for filling forms (contact details, links, standard answers) | `private/ops/jobs/form-data.md` |
| Names that must never reach a public file | `private/ops/boundaries.md` + the local denylist |
| Public-safe rules (paraphrase) | [`references/rules.md`](references/rules.md) |
| Scan sources and methods | [`references/sources.md`](references/sources.md) |
| Board items for applications | issues in private `ops`, never in a public repo |

Record shape (synthetic example):

```yaml
- id: 101
  company: Example Co
  role: Data Analyst (contract)
  stage: applied
  applied_on: 2026-11-12
  last_contact_on: 2026-11-12
  channel: job board → company ATS
  pay: "as posted"
  cv: cv-general
  next: wait
  notes: ""
```

Ids are integers, unique, never reused.

Optional fields include `hold_close`: a short reason (text) that keeps the record out of the 30-day closure
proposals, for example when the wait is on Nghiep's side. `tools/jobs/check` lists such a record as `held` with its
reason instead of proposing it. Remove the field when the reason no longer applies. The old name `hold_14d` is still
read as a deprecated alias, with a warning; rename it to `hold_close`.

## 2. Stages and transitions

| From | Allowed to |
|---|---|
| `lead` | `applied`, `skipped` |
| `applied` | `screen`, `interview`, `rejected`, `withdrawn`, `ghosted` |
| `screen` | `interview`, `rejected`, `withdrawn`, `ghosted` |
| `interview` | `offer`, `rejected`, `withdrawn`, `ghosted` |
| `offer` | `accepted`, `declined` |
| `ghosted` | `screen`, `interview` (revival: the employer replies after the close) |

Terminal: `accepted`, `declined`, `rejected`, `withdrawn`, `ghosted`, `skipped`. `ghosted` is terminal except for the
revival above. Any other change is illegal and fails `tools/jobs/check`.

On every change, update `last_contact_on` when there was contact, and `next` with the next action and its date.

## 3. The 30-day rule

Changed from 14 to 30 days on 2026-11-12: foreign employers reply slowly.

- An application in `applied` or `screen` with no contact for 30 days (counted from `last_contact_on`, or
  `applied_on` when there was no contact) is **proposed** for `ghosted`. `tools/jobs/check --close-after-days N`
  overrides the threshold for one run.
- The tool only proposes. Nghiep confirms each closure; then the stage changes in a commit to `ops`.
- `next` shows the date the 30 days run out, so the follow-up or close date is visible without counting, in the
  form `wait — hết hạn 30 ngày <YYYY-MM-DD>` (the later of `applied_on` and `last_contact_on`, plus 30 days).
- A record with `hold_close` set is not proposed; the check shows it as `held` with the reason (see §1).

## 4. `tools/jobs/check`

Deterministic, no LLM. Run it with `just jobs-check` (or `tools/jobs/check --help` for options).

- Validates the file: schema, known stages, legal transitions, duplicate ids. Any error → non-zero exit; CI in `ops`
  fails.
- Prints: today's 30-day closure proposals (`--close-after-days N` to change); follow-ups due this week; interview prep due within 48 h; the next
  actions.
- Its output is the input for the digest and the weekly review funnel.

## 5. Per-application flow

1. **Lead.** Describe the job for Nghiep in Vietnamese: what the work is, how and where it is done, the posted pay
   (pay detail is written only in `ops`). Check the skip rules first (`references/rules.md` §3).
2. **Draft.** Draft every form field and any cover text. Say whether the CV needs a different variant.
3. **Approve.** Nghiep approves the draft. A batch approval ("apply to all the proposed ones") counts only for the
   items listed in that message.
4. **Fill.** Claude fills the form in the browser. Nghiep uploads the CV, ticks terms and consent boxes, solves
   CAPTCHAs and clicks Submit.
5. **Record.** Set `stage: applied`, `applied_on`, `channel`, `cv`, `next`. Keep the confirmation mail as the evidence.
6. **Follow up.** Recruiter replies update the stage and `last_contact_on`. Replies to recruiters: Claude drafts,
   Nghiep approves, then it is sent.

## 6. Form-filling rules (MUST, spec §5.2)

- Claude fills forms. **Nghiep** uploads CVs, ticks terms, solves CAPTCHAs and clicks Submit.
- Agents create no accounts, sign in nowhere, and type no passwords.
- Skip platforms that use AI interviews (AI screening calls, voice AI interviewers).
- No claude.ai links in any application.
- No employer or client code or data in any take-home task (names in `private/ops/boundaries.md`).
- Screening answers that decide the filter (years of experience, work authorization, tool proficiency, hours) are
  chosen by Nghiep, not guessed.

Guard: ritual (Nghiep holds the Submit step). Everything else in `references/rules.md`.

## 7. Scan sessions

Follow [`references/sources.md`](references/sources.md): the order of sources, how each is read, and the terms of
service rule. Drop postings already in `skipped.yaml` before reading them. New skips go to `skipped.yaml` with a
one-line reason, so they are never reviewed again.

## Maintenance

Follow `skills/README.md`. A new rule that names an employer or a number goes to `private/ops/jobs/rules.md`; only
its general form comes here.
