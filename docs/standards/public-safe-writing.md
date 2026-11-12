# Standard: public-safe writing

Applies to every public repo (`ecosys`, `.github`, `lab-to-prod`, public projects): files, commits, branch names, PR titles and bodies, issues, CI logs and release notes. The rule is in `agents/steering/data-rules.md`; this page says how to write so you follow it.

## Never in public

- Employer names from the job search, recruiter names, salaries, offers, application outcomes.
- Names, e-mails, phones or handles of other people (unless they are public authors you cite).
- Internal names of a current or past employer or client: company, product, app, repo, org, domain, server, team.
- Day-job account ids, issue keys, schemas, prompts, code, screenshots or logs.
- claude.ai links. Private repo paths that reveal private content.
- Secrets of any kind. A secret that was pushed is revoked first, then removed.

## Write it this way instead

| Instead of | Write |
|---|---|
| the employer's name | "the day job", "a client" |
| the employer's product name | a generic role: "an internal web app", "a data pipeline" |
| an application with a company name | nothing public; the item lives in `ops` |
| a real number from an employer | a public-safe range, or the fact id in `vault` `[P1]` |
| a real person in an example | `Example Co`, `Acme`, `Alex Doe`, `alex@example.com` |
| a day-job issue key | the public repo ref `<repo>#<n>`, or nothing |

Examples in tests and docs use synthetic data only (`example.com`, `Example Co`, `Acme`).

## Do not list what you hide

A public file must not list the names it is meant to block. Lesson from lab-to-prod PR #1: a banned-terms file in plaintext published every term it was meant to hide.

- Keep the terms in the local denylist `~/.config/nghiep-pham-ecosys/denylist.txt` and in `private/ops/boundaries.md`.
- Public CI checks only hashes of the terms and generic patterns (e-mail, phone, salary-like amounts).
- Tests of the checker use synthetic terms.

## Checks before a push

1. `gitleaks` on the staged change (pre-push hook and CI).
2. Denylist scan of the change (local pre-push hook; `public-safe-guard` `[P1]`).
3. Read the diff once with the question "would this be fine on a stranger's screen?".
4. A PR that touches `profile` text, posts or project READMEs gets a reviewer-privacy pass.

## When something slips

1. Stop. Do not push more.
2. If it is a secret: revoke it now.
3. Tell Nghiep. History rewrites and force-pushes need his yes (ADR 0003).
4. Write a lesson with a Guard, so the same slip is blocked next time.

## Private to public

A repo goes public only after a full-history gitleaks scan, a denylist scan of every commit, an ADR note and Nghiep's yes.
