# Job search rules (public-safe)

A public-safe paraphrase of the rules Nghiep set for the job search. The full original, with pay expectations,
named exceptions and personal details, is in `private/ops/jobs/rules.md`. When the two differ, the private file wins
(repo precedence) and this file is fixed.

Read this before a scan, before drafting an application, and when a posting looks borderline.

## 1. Division of work

- Before each application: describe the job (what, how, where, posted pay), draft the fields, and say whether the CV
  needs a different variant. Nghiep approves, then Claude fills.
- A batch approval ("apply to all the proposed ones") covers only the postings listed when it was given. Nghiep still
  reviews each filled form and submits it.
- Claude fills forms. Nghiep uploads the CV, ticks terms and consent, solves CAPTCHAs and clicks Submit.
- Claude does not create accounts, sign in, type passwords, sign legal commitments or enter a date of birth.
- Answers that decide whether the filter passes (years of experience, work authorization for another country, tool
  proficiency level, working hours) are chosen by Nghiep.
- E-mails to recruiters: Claude drafts, Nghiep approves, then Claude sends.
- Standard answers (start date, notice period, references, links) come from `private/ops/jobs/form-data.md`.
  Never offer the current employer's managers as references.

## 2. Platforms to avoid or flag

- Platforms that ask for a lot of personal data at the apply step (date of birth, ID documents, identity
  verification, IP checks): tell Nghiep **before** any account is created.
- Platforms that charge a fee or a subscription to see or apply to jobs: do not sign up.
- "Remote" postings tied to one country: check the form for a "legally authorized to work in <country>" question
  before drafting.

## 3. Skip rules

Skip, and record the posting in `skipped.yaml` with a one-line reason:

- the process includes an AI interview (AI screening call, voice AI interviewer);
- an essay that must be written without AI;
- a PhD is required;
- candidates from Nghiep's country are not accepted.

Still allowed: a take-home done by Nghiep himself, a short questionnaire, a written expert test. A take-home never
contains employer or client code or data.

## 4. Links

- No claude.ai links in any application (they show the text was AI-made).
- Portfolio and sample links come from `private/ops/jobs/form-data.md`.

## 5. The 30-day rule

An application with no reply for 30 days after it was sent, or after the last contact, is proposed for closing as
`ghosted` (changed from 14 to 30 on 2026-11-12: foreign employers reply slowly). `next` shows the date the 30 days run
out. Nghiep confirms each closure (`jobs` §3).

## 6. Scope of roles

- AI and ML engineering roles at mid and senior level, not only senior or lead.
- Remote roles outside AI that fit the background: data and automation, Vietnamese-language evaluation or
  translation, chemistry and environmental engineering.
- AI trainer, annotation and AI evaluation work, preferring tasks that fit the background (technical chemistry,
  Python and coding agents, Vietnamese).
- Applied science roles in environment, climate and energy.
- Remote first, ideally companies based in Nghiep's country. Hybrid or on-site roles near home may still be proposed.
- Pay floor and bands: private file only.

## 7. Browser notes

- Some sites open only in one browser (Claude in Chrome vs the browser inside the Claude app). Which site works where
  changes; the current list is in the private rules file. A site that shows an error page in one browser → try the
  other before giving up.
- Sites behind a bot check: open the page and wait about 10 seconds before reading.
- Do not use "Generate … with AI" buttons on job boards.
- Do not use "Autofill from resume" on ATS forms that overwrite fields already filled.
- Long dropdowns: scroll inside the list with the mouse wheel. Scrolling the page can click outside the form and
  trigger a "discard application" dialog.
- ATS profile pages (for example a candidate profile on an ATS vendor's site) may overwrite employment, education
  and name when a new CV is uploaded. Re-check those fields after each upload.

## 8. Mail checks

When checking mail for recruiter replies, also flag non-recruiting mail that needs Nghiep to act (course deadlines,
calendar changes, alerts from his own repos). Add dated items to `private/ops/learn/deadlines.yaml` or the board.

## 9. Language

Talk with Nghiep in Vietnamese. Application text follows the posting's language.
