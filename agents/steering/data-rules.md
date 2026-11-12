# Data rules

## Data classes (spec §10.1)

| Class | Examples | Lives in |
|---|---|---|
| `public` | code, docs, posts, public-safe lessons | any repo |
| `private` | applications, salaries, plans, notes, reviews | `private/ops`, `private/vault` |
| `pii:contact` | other people's names, e-mails, phones | `private/ops`, `private/vault` (sops-encrypted `[P1]`) |
| `secret` | credentials, ID, financial and health documents | password manager only; never a repo or agent workspace |

## Public-safe rule (MUST, spec §10.2)

Public repos (`ecosys`, `.github`, `lab-to-prod`, public projects) never contain:

- employer names from the job search, recruiter names, salaries or application outcomes;
- contact details of anyone;
- internal names of current or past employers or clients;
- account ids, issue keys or code from the day job;
- claude.ai links.

How to write around this: `docs/standards/public-safe-writing.md`.

**Enforcement.** A local denylist at `~/.config/nghiep-pham-ecosys/denylist.txt` (never committed, chmod 600) feeds the pre-push hook and `public-safe-guard` `[P1]`. Public CI checks only hashes and generic patterns. Agents never read or print the denylist (hook `secret-path-guard`).

Never list the names you want to hide in a public file. A public file that lists them defeats its purpose.

## Day-job boundary (MUST, spec §10.3)

- Copied: ways of working only (rituals, lesson format, ship rules, folder pattern, ADR template).
- Never copied: employer or client code, data, prompts, schemas, account ids, issue keys, internal names, screenshots. The same applies to teaching or other client work.
- The day job shows up only as the weekly `work-block` item and as public-safe achievement text in `vault`.

## Where data goes

| You have | Put it in |
|---|---|
| a new application or a stage change | `private/ops/jobs/applications.yaml` |
| a course deadline or voucher expiry | `private/ops/learn/deadlines.yaml` |
| a personal task (application, money, health) | an issue in `ops` |
| a public-safe task | an issue in the repo it belongs to |
| a personal lesson | `private/ops/lessons.md` |
| a public-safe lesson | `skills/lessons/lessons.md` |
| a credential | the password manager, nothing else |

## LLM use

- LLM work runs inside Claude subscriptions. No paid API (P5).
- A free LLM tier MAY be used only on public or synthetic data. Free tiers may train on inputs.
- Test fixtures are synthetic. Never paste real application data into a test.

## Private to public

Before a repo goes from private to public: a full-history gitleaks scan, a denylist scan of every commit, and an ADR note. The visibility change needs Nghiep's yes (ADR 0003).
