# Personal Ecosystem Spec ("me-as-code")

> **Status:** Draft v0.3 (2026-11-12) · **Owner:** Nghiep (solo) · **Audience:** Nghiep and every coding agent working in the org
> **Changes from v0.2:** adds capacity and WIP limits (§2), uses the multi-repo workspace pattern already used at the day job instead of a new monorepo (§4), removes the assumption of paid LLM APIs (§7), adds Claude scheduled tasks as an automation runner (§8), makes `lab-to-prod` the publishing domain instead of building a second site (§5.4), and cuts Phase 0 to 2–3 evenings (§12). The DB, owner app, twin and AI gateway sections are kept, but only as triggers (§13).
> **Non-goals:** a product for other users, multi-tenant SaaS, enterprise process.

---

## 0. How to read this spec

- **MUST / SHOULD / MAY** have their usual meaning. Every MUST names what enforces it: a hook, a CI check, a test or a ritual step. A rule that nothing enforces is a SHOULD.
- Tags: `[P0]` Phase 0, `[P1]` Phase 1, `[TRIGGER: <condition>]` not built until the condition is true. Each trigger is recorded on the board (§6).
- `<org>` = the GitHub org (proposed `nghiep-pham-ecosys`; check that the name is free). `<you>` = `pqnghiep1354`. `<you-id>` = the numeric GitHub user id.
- Workspace root on disk: `~/projects/nghiep-pham-ecosys/` (WSL Ubuntu). Every other path in this spec is relative to it.
- Free-tier limits change. A number marked *(verify)* is checked on the vendor page before anyone relies on it. The checked value and the date go into ADR 0002.

---

## 1. Purpose and principles

### 1.1 Problem

Too many parallel threads are tracked in too many places: job applications, daily posting, courses, side projects, day-job work and research. Today they live in a Claude Project doc, Notion, Google Docs, scheduled tasks, Gmail and several repos. The calendar is dense and nothing shows the whole picture.

### 1.2 Purpose

One workspace, kept as code, that:

1. Shows **all active work on one board**, within a weekly time budget (§2, §6).
2. Holds **the facts about Nghiep** (experience, skills, projects, learning) as versioned data that CVs and profile text are generated from (§5.1).
3. **Runs the personal pipelines** (job search, publishing, learning, lab) with the same rituals as the day job (§9).
4. **Automates the routine**: one daily digest, one weekly review, deadline reminders (§8).
5. Is **built and run mostly by coding agents** under rules that keep them safe, cheap and honest.

### 1.3 Success after 4 weeks

- Every active item in every area is on the board. Nothing important lives only in chat or memory.
- The Sunday review takes 30 minutes or less and sets next week's items within the budget.
- No deadline is missed (course, application follow-up, post slot).
- Job applications follow the 30-day rule without manual counting (changed from 14 to 30 on 2026-11-12: foreign employers reply slowly).

### 1.4 Principles

| # | Principle | In practice |
|---|---|---|
| P1 | **Capacity first** | Work is limited by a weekly time budget and WIP limits per area (§2). The board shows what will **not** be done this week. |
| P2 | **As-code** | Rules, skills, decisions, facts, the job pipeline and plans live in git. Personal data lives in private repos. |
| P3 | **Evidence over claims** | "Done" means verified (§9.5). No status is stated from memory: check it live or label it *unverified*. |
| P4 | **One source of truth per fact** | Each fact has one home. Precedence: **repo > canonical doc > memory > skill**. Drift is reported, never resolved silently. |
| P5 | **Free and subscription only** | No paid API (X API, Anthropic API, others). LLM work runs inside Claude subscriptions (Claude Code, Claude app, scheduled tasks). A new paid service needs an explicit yes, with the monthly cost stated first. |
| P6 | **Privacy by design** | Job search, contacts, salaries and personal notes stay in private repos. Public repos follow the public-safe rule (§10.2). |
| P7 | **Guards over good intentions** | A lesson that repeats becomes a hook, a CI check or a test. |
| P8 | **Agents code, the orchestrator ships** | Subagents never push, merge or write to external systems. Publishing to any channel and submitting any application need Nghiep. |
| P9 | **Same way of working as the day job** | Same rituals, folder pattern, lesson format and ship rules, so habits carry over in both directions. **Nothing else from the day job comes in** (§10.3). |

---

## 2. Capacity and WIP `[P0]`

This section is the main fix for "too many threads". The board (§6) enforces it and the weekly review (§9.4) uses it.

### 2.1 Weekly time budget

Defaults below. Nghiep sets the real numbers in `ops/plan/capacity.yaml` at the first weekly review.

| Area | Hours/week (default) | Notes |
|---|---|---|
| `work` (day job) | fixed by the employer | Shown only as blocked time. Day-job items stay in the employer's own tools (§10.3). |
| `jobs` | 5 | Search, applications, follow-ups, interview prep |
| `learn` | 10–14 | ~2 h/day study plan; courses with deadlines come first |
| `content` | 4 | lab-to-prod posts and blog; drafting is mostly done by agents |
| `lab` | 3 | experiments, side projects (Physical AI, climate, motion studio) |
| `ecosys` | 2 | building this workspace; drops to ~1 after Phase 0 |
| buffer | 10% of the total | interviews, surprises |

`ops/plan/capacity.yaml`:

```yaml
week_starts: monday
areas:
  jobs:    { hours: 5,  wip: 3 }
  learn:   { hours: 12, wip: 2 }
  content: { hours: 4,  wip: 2 }
  lab:     { hours: 3,  wip: 1 }
  ecosys:  { hours: 2,  wip: 2 }
buffer_pct: 10
```

### 2.2 Rules

- **WIP limit per area** (MUST, enforced by the weekly review script and the digest): an area may have at most `wip` items in `In progress`. A new item waits in `Next` until one finishes or is dropped.
- Every item on the board has an `Estimate (h)`. The weekly review refuses a plan whose sum is over budget and lists what moves out.
- **One new project at a time:** a new side project enters `lab` only when another one is paused, recorded as `Status: Paused` with a reason.
- Items with a hard deadline (course, exam, application follow-up) are planned first, then the rest.

---

## 3. Areas (domains)

| Area | Source of truth | Where it lives | Phase |
|---|---|---|---|
| `jobs` | `ops/jobs/applications.yaml` | private `ops` repo | P0 (migrated from the Project tracker) |
| `profile` (CV, facts) | `vault/profile/profile.yaml` | private `vault` repo | P1 |
| `learn` | `ops/learn/deadlines.yaml` + `ops/learn/tracks/*.md` | private `ops` | P0 deadlines, P1 tracks |
| `content` | `lab-to-prod` repo (calendar, posts, blog) | public project repo | already running |
| `projects` | each project repo + its `project.yaml` | `projects/*` | P1 registry |
| `lab` | experiment folders in `lab-to-prod` or a project repo | public code, private data | `[TRIGGER: first experiment that is not a post]` |
| `research` | `vault/research/` | private | `[TRIGGER]` |
| `twin` | — | — | `[TRIGGER: §13]` |

Each area has one skill (§9.6) that explains its flow. Areas talk to each other through files and the digest, not through a database, until a trigger in §13 fires.

---

## 4. GitHub org and local workspace

### 4.1 Decision (ADR 0001): multi-repo workspace, like the day job

v0.2 proposed one public monorepo. v0.3 uses the **day-job pattern** instead: one root repo for rules and docs, and every other repo cloned under it with its own `.git`. Reasons:

- Several repos already exist (`lab-to-prod` and others), each with its own history and CI. Merging histories into a monorepo costs time and gains little.
- Nghiep already works this way every day in the day-job workspace (a root repo with child repos under `apps/` and `infra/`), so the habits and tools carry over.
- Visibility differs per repo (public projects, private `ops`/`vault`). Separate repos make that split simple and safe.

**Revisit when:** two repos need to share code and copying it becomes a chore. Then add a `packages` repo or merge just those two.

### 4.2 Repos in `<org>`

| Repo | Visibility | Purpose | Local path |
|---|---|---|---|
| `ecosys` | public | **root repo**: `CLAUDE.md`, steering, skills, hooks, tools, ADRs, public-safe docs, `repos.yaml`, VS Code workspace file | `./` |
| `.github` | public | org profile README, default issue and PR templates, reusable workflows | `meta/.github` |
| `ops` | private | board-side data: job pipeline, plans, capacity, learning deadlines, session logs, memory, lessons about private matters, private scheduled workflows | `private/ops` |
| `vault` | private | facts: `profile.yaml`, stories, drafts, research notes; sensitive files encrypted with sops+age `[P1]` | `private/vault` |
| `lab-to-prod` | public | content lab: calendar, posts, blog, render and publish workflows | `projects/lab-to-prod` |
| other existing repos | as today | personal projects transferred from `<you>` (§4.4) | `projects/<repo>` |
| `tmpl-project` | public, template | starter for new projects | `meta/tmpl-project` `[P1]` |

**Not moved into the org:** anything owned by or related to the employer or clients (their orgs are listed in `private/ops/boundaries.md`). Forks of third-party repos stay on `<you>` unless Nghiep asks.

### 4.3 Local layout

```
~/projects/nghiep-pham-ecosys/          ← root repo <org>/ecosys (branch main)
├── CLAUDE.md                           ← root agent rules (imports steering)
├── AGENTS.md                           ← pointer for other agent tools (Kiro, Codex)
├── CONTEXT.md                          ← whole-system map: areas, repos, runners, data homes
├── repos.yaml                          ← workspace manifest: every repo, path, visibility, area
├── nghiep-pham-ecosys.code-workspace   ← VS Code multi-root workspace
├── justfile                            ← ws-sync, ws-status, digest, review, ci
├── agents/steering/                    ← workflow.md, language-and-style.md, data-rules.md, machine-notes.md
├── skills/<name>/SKILL.md              ← core, session, ship, lessons, jobs, learn, content, weekly-review
├── .claude/
│   ├── settings.json                   ← permissions + hooks (§9.7)
│   ├── hooks/ hooks/tests/
│   ├── agents/                         ← reviewer-privacy.md, reviewer-correctness.md
│   └── skills -> ../skills
├── .kiro/steering -> ../agents/steering
├── docs/
│   ├── spec.md                         ← this file
│   ├── adr/                            ← 0001-workspace-topology, 0002-stack-and-free-tiers, 0003-approvals
│   ├── runbooks/                       ← org-setup.md, new-project.md, lost-laptop.md
│   └── standards/                      ← public-safe-writing.md, secrets-register.md (names only)
├── tools/
│   ├── ws/                             ← sync (clone/pull all from repos.yaml + private overlay), status (branch, dirty, ahead/behind, open PRs), workspace (local VS Code file)
│   ├── board/                          ← sync labels/fields, weekly plan check against capacity.yaml
│   ├── jobs/                           ← 30-day rule, follow-up list, digest section
│   └── ship/                           ← merge tool (checks green twice, squash, --match-head-commit)
├── .tmp-session/                       ← gitignored: wt/<session>-<lane>/ worktrees, checklist, lessons-pending
│
├── meta/                               ← gitignored, cloned: .github, tmpl-project
├── private/                            ← gitignored, cloned: ops, vault
└── projects/                           ← gitignored, cloned: lab-to-prod, <other project repos>
```

Root `.gitignore` MUST list `meta/`, `private/`, `projects/`, `.tmp-session/`, `.env*`. A CI check in `ecosys` fails if any path under those folders is tracked.

### 4.4 Bringing existing repos in

1. List the repos on `<you>` (`gh repo list <you> --limit 200 --json name,visibility,isFork,isArchived,pushedAt`). Nghiep marks each one: **move**, **keep on personal account**, **archive**.
2. **Move** = transfer the repo to `<org>` (`gh api -X POST repos/<you>/<repo>/transfer -f new_owner=<org>`). GitHub redirects old URLs, keeps issues, PRs, stars and Actions secrets. Things to check after each transfer:
   - local remotes: `git remote set-url origin git@github.com:<org>/<repo>.git` (the redirect works, but don't rely on it);
   - **GitHub Pages URL changes** (`<you>.github.io/<repo>` → `<org>.github.io/<repo>`): update `site`/`base` config and any canonical URLs **before** the first public post;
   - OAuth apps, deploy keys and webhooks that point at the old owner.
3. Move the local clone into `projects/<repo>` (`mv`, which keeps uncommitted work and branches), then point any editor or Claude Desktop session at the new path.
4. Add the repo to `repos.yaml` and the VS Code workspace file, or, when its name must stay out of public files (for example a job-related exercise), to `private/ops/repos.private.yaml` only (§4.5). Give it the topic `project` and a `project.yaml` `[P1]`.

### 4.5 `repos.yaml`

```yaml
org: nghiep-pham-ecosys
repos:
  - { name: ecosys,      path: .,                     visibility: public,  area: ecosys,  default_branch: main }
  - { name: .github,     path: meta/.github,          visibility: public,  area: ecosys,  default_branch: main }
  - { name: ops,         path: private/ops,           visibility: private, area: ecosys,  default_branch: main }
  - { name: vault,       path: private/vault,         visibility: private, area: profile, default_branch: main }
  - { name: lab-to-prod, path: projects/lab-to-prod,  visibility: public,  area: content, default_branch: main }
  # one line per transferred project repo
```

`just ws-sync` clones missing repos and fast-forwards clean ones. It never touches a dirty repo or a repo on another branch, and it reports them instead. `just ws-status` prints one line per repo: branch, dirty count, ahead/behind, open PRs.

**Private overlay (added 2026-11-12).** Private repos whose names must not appear in public files (job-related exercises, for example) are listed only in `private/ops/repos.private.yaml`, with the same schema (`org` must match, every repo `private`). The `ws` tools merge it when it exists; a name or path that collides with `repos.yaml` is an error. Overlay rows are marked `private-manifest` in the output. `just ws-workspace` writes `nghiep-pham-ecosys.local.code-workspace` (gitignored by `*.local.code-workspace`): the public workspace plus the overlay repos.

### 4.6 Org settings (one-time, `docs/runbooks/org-setup.md`)

Items marked `[UI]` are done by Nghiep in the GitHub web UI. Agents do not create orgs, change billing or create tokens.

- [ ] `[UI]` Create the org on the Free plan. Require 2FA. Base member permission: none.
- [ ] `[UI]` Billing: spending limit 0 for Actions, Packages and Codespaces.
- [ ] Actions: default token read-only; Actions cannot approve PRs; allow GitHub-owned and listed actions only.
- [ ] Public repos: secret scanning and push protection on, Dependabot alerts on.
- [ ] Ruleset on `main` for public repos: PR required, squash only, required checks `ci-result` and `pr-title`, no force push, no deletion. Private repos on the Free plan cannot have rulesets *(verify)*, so they use a local pre-push hook plus the merge tool.
- [ ] `[UI]` Org-level GitHub Project "Ecosys board" (§6), private.

---

## 5. Area details

### 5.1 Profile and CV `[P1]`

- `vault/profile/profile.yaml` (JSON Resume base plus stable ids such as `work-…`, `ach-…`, `skill-…`), validated by `vault/schema/profile.schema.json` in vault CI. Ids are never renamed or reused; unwanted facts get `retired: true`.
- Facts are migrated from today's CVs ("AI Platform", "Engineering & Environmental AI Evaluation", the Vietnamese version). Every number in a CV must point to a fact id.
- CV rendering: **Typst**, one ATS-safe template (one column, real text, standard headings), run locally with `just cv <variant>`. The PDF never goes into a public repo or public CI.
- `[TRIGGER: more than 3 tailored CVs a week]`: a `cv-tailor` skill that picks facts per job requirement and checks every number against its fact.

### 5.2 Job search `[P0]`

- **Source of truth:** `ops/jobs/applications.yaml`, migrated from the Project doc `claude/job-applications-tracker.md` (active rows, closed rows, skipped list, rules, form data). After migration the Project doc becomes a short pointer.
- One record per application:

```yaml
- id: 101
  company: Example Co
  role: Data Analyst (contract)
  stage: applied            # lead|applied|screen|interview|offer|accepted|declined|rejected|withdrawn|ghosted|skipped
  applied_on: 2026-11-12
  last_contact_on: 2026-11-12
  channel: job board → company ATS
  pay: "as posted"
  cv: cv-general
  next: wait
  notes: ""
```

- `tools/jobs/check` (deterministic, no LLM):
  - **30-day rule:** `applied`/`screen` with no contact for 30 days → digest proposes `ghosted`, and Nghiep confirms (changed from 14 to 30 on 2026-11-12: foreign employers reply slowly). `--close-after-days N` overrides the threshold; a record with `hold_close` set is shown as held instead.
  - lists follow-ups due this week and interview prep due within 48 h.
  - fails CI on unknown stages, illegal transitions or duplicate ids.
- **Rules carried over (MUST):** Claude fills forms; Nghiep uploads CVs, ticks terms, solves CAPTCHAs and clicks Submit. No account creation and no passwords by agents. Skip platforms with AI interviews (micro1, Turing, Mercor, voice AI). No claude.ai links in applications. No employer or client code or data in any take-home (names in `private/ops/boundaries.md`).
- **Sources:** the scan list in the tracker (§3b there) moves to `skills/jobs/references/sources.md`. Sites whose terms forbid scraping are read only as a normal signed-in user, page by page. Nghiep decides at the first review whether LinkedIn guest endpoints stay in the list.
- Everything about applications, employers, recruiters and salaries stays in `ops` (§10.2).

### 5.3 Learning `[P0 deadlines, P1 tracks]`

- `ops/learn/deadlines.yaml`: every dated obligation (course deadlines, exams, certificate vouchers, discount codes with an expiry). The digest lists items due within 7 days, and anything within 48 h is flagged at the top.

```yaml
- id: course-x-m0
  what: Example course, module 0 graded quiz
  due: 2026-11-14T09:04+07:00
  needs: upgrade to the verified track before the deadline
  status: open
```

- `ops/learn/tracks/<track>.md`: plan, weekly hours and progress for each track (English, DSA, ML, AI engineering, Claude certification, MSc preparation). The existing study plan and the calendar reminders are imported once.
- `lab-to-prod/claude/lesson-log.md` stays the input for "learning in public" posts. `ops` links to it and does not copy it.

### 5.4 Content `[running]`

- `lab-to-prod` **is** the publishing area: calendar, post format, validator, blog, render and publish workflows, approval flow. This spec does not define a second site or blog.
- The ecosystem adds only: content items on the board (one per week, not per post), the content section of the digest (today's slot, drafts awaiting approval), and the content line in the weekly review.
- Lessons from `lab-to-prod` that apply everywhere (for example "a public repo must not list internal names in plaintext") move up to `ecosys/skills/lessons/`.

### 5.5 Projects `[P1]`

- Each project repo has a `project.yaml` (name, area, status: active|paused|done, stack, highlights, links, visibility). `tools/ws/projects` builds the portfolio list from these files. Only `active` projects count against the `lab` WIP limit.
- New projects start from `tmpl-project` (README, `project.yaml`, `CLAUDE.md` stub that points to the root rules, CI with gitleaks, pr-title).

---

## 6. The board (single tracker) `[P0]`

- One **org-level GitHub Project**, "Ecosys board", private, that pulls issues from every repo.
- **Fields:** `Area` (jobs, learn, content, lab, ecosys, work-block), `Status` (Inbox, Next, This week, In progress, Blocked, Done, Paused, Dropped), `Estimate (h)`, `Due`, `Week` (iteration), `Evidence` (link).
- **Where issues live:** public-safe work in the repo it belongs to. **Anything personal (an application, a recruiter, a salary, a health or money matter) goes as an issue in private `ops`**, never in a public repo.
- **Granularity:** one issue is about one PR or one 1–3 h task. Recurring work (daily posts, daily study) is **one weekly item**, not seven.
- Day-job work appears only as one `work-block` item per week with the hours, so the budget adds up. Day-job tasks stay in the employer's own tracker.
- Issue template (all repos, from `.github`): Problem · Scope (in/out) · Done when (checkable) · Estimate · Area · Where (public repo or `ops`).

---

## 7. LLM use without paid APIs `[P0]`

| Work | Runs in | Notes |
|---|---|---|
| Building and changing the repos | Claude Code (Desktop/VS Code) on the workspace | the main way work gets done |
| Drafting posts, CV text, cover letters, digests that need judgement | Claude Code sessions or **Claude scheduled tasks** | subscription, no API key |
| Reading Gmail and calendars, filling forms in a browser | Claude app with connectors and the Chrome extension | the user's own sign-ins |
| Deterministic checks (30-day rule, validators, schema, deadlines) | scripts in `tools/` run by `just` or Actions | no LLM |
| Second opinion review | a reviewer subagent with a different lens; Kiro/Codex optional | not a different paid vendor |

- **Usage budget:** Claude plan limits are the real constraint (limits were hit on 2026-11-12). Rules: heavy multi-file work goes in one planned session; scheduled tasks stay short and do one thing; subagents are used only for independent parallel lanes. The weekly review notes whether limits were hit and moves work if they were.
- Free LLM tiers (for example a free Gemini tier) MAY be used **only on public or synthetic data**, because free tiers may train on inputs.
- `[TRIGGER: the first paid API call]`: the AI gateway with a ledger and caps from v0.2 §4.10 comes back as ADR 0004.

---

## 8. Automation runners `[P0 digest, P1 the rest]`

| Runner | Use for | Limits |
|---|---|---|
| **Claude scheduled tasks** | anything that needs judgement or the user's connectors: the mail check (11:41 and 20:41 today), daily draft work, the morning digest text, the Sunday review draft | plan limits; each task is written as a standalone prompt that reads `ops` files first |
| **GitHub Actions in `ops`** (private) | deterministic jobs: `tools/jobs/check`, deadline scan, capacity check, encrypted backup of `ops`/`vault` | about 2,000 min/month on private repos *(verify)*; no tick more often than daily |
| **GitHub Actions in public repos** | CI, lab-to-prod validate/render/publish, blog deploy | public repo logs are public: never private data |
| `[TRIGGER: something must run more often than hourly]` Cloudflare Workers cron | frequent ticks | — |

- **Digest:** one message per day to **one channel**, the Telegram bot already planned for lab-to-prod (ntfy and e-mail are not used). Sections, in this order: due within 48 h (deadlines, follow-ups, interviews) → today's content slot and drafts awaiting approval → board items `In progress` per area → anything red (failed workflow, missed task).
- Every scheduled job declares its expected run time. A missed or failed run shows up in the next digest under "red".
- Existing scheduled tasks are listed in `ops/automations.md` (name, schedule, runner, what it reads and writes). A task that is not listed there gets disabled at the next weekly review.

---

## 9. Working with agents (day-job rituals, personal edition)

### 9.1 Roles

| Actor | Does | Never does |
|---|---|---|
| **Nghiep** | sets session goals and weekly plans; approves publication, applications, money, deletes, credentials, visibility changes, repo transfers | review every routine PR |
| **Orchestrator** (main Claude Code session) | plans, runs lanes, merges through the merge tool, verifies, writes logs | publish content, submit applications, start paid services, transfer repos without approval |
| **Subagents / lanes** | code and test in their worktree, commit locally, return structured results | push, merge, open PRs, run workflows, write to external tools (hook) |
| **Reviewer agents** | read-only review of a diff (privacy, correctness) | edit code |

### 9.2 Session start (`skills/session`)

1. Read the newest block of `private/ops/memory.md`, the last session log, and the board view "This week".
2. Check reality (read-only): `just ws-status`, red workflows, open PRs, digest "red" items, deadlines within 48 h.
3. Report drift between the records and reality.
4. Read the lessons for the areas about to be touched.
5. Propose 3–5 items **within the area budgets** (§2), each with what, why and how it will be verified.
6. After agreement: create `.tmp-session/checklist.md` and start.

### 9.3 Session end

1. Settle board items (status, evidence link).
2. Move pending lessons into `skills/lessons/lessons.md` (public-safe) or `private/ops/lessons.md` (personal).
3. Batch external drafts (posts, e-mails, application text) once for approval. Nothing goes out without it.
4. Write the session log `private/ops/sessions/YYYY-MM-DD-<slug>.md` and prepend the memory block.
5. Every repo on a clean `main`; worktrees removed; three lines to Nghiep: done / left and why / where the next session starts.

### 9.4 Weekly review (Sunday, `skills/weekly-review`)

- Draft produced by a Claude scheduled task from `ops` files and the board. Nghiep finishes it in ≤ 30 minutes.
- Contents: hours planned vs done per area; items done with evidence; items moved out and why; jobs funnel (applied, replies, interviews, closed by the 30-day rule); deadlines in the next 14 days; content published vs planned; red automations; plan-limit hits.
- Output: `private/ops/reviews/YYYY-Www.md` and next week's board items, set to `This week` within budget.

### 9.5 Definition of Done

- Code: merged → CI green on `main` → deployed and verified where something is deployed (blog URL returns 200, workflow run green) → evidence link on the board item.
- Non-code (an application, a post, a course module): the artifact exists and is linked (confirmation mail, post URL, certificate or progress screenshot in `ops`).

### 9.6 Skills (in `ecosys/skills/`)

| Skill | Purpose | Phase |
|---|---|---|
| `core` | hard rules, roles, sources and precedence, which skill when, brief template | P0 |
| `session` | start/end rituals, checklist | P0 |
| `ship` | PR → checks → merge tool → verify → Done with evidence | P0 |
| `lessons` | lesson format with Guard and Seen fields | P0 |
| `jobs` | stages, 30-day rule, form-filling rules, sources, skip list | P0 |
| `weekly-review` | capacity check, review template | P0 |
| `learn` | deadlines, tracks, study coaching | P1 |
| `content` | pointer to lab-to-prod skills and approval flow | P1 |
| `cv` | facts → Typst variant, number-to-fact check | P1 |

Each skill: `SKILL.md` ≤ ~150 lines, a description that names its triggers and what it does not cover, details in `references/`. Skills are the same files for Claude Code (`.claude/skills` symlink) and Kiro (listed in a steering file).

### 9.7 Guardrails `[P0]`

| Hook | Rule |
|---|---|
| `ship-guard` (PreToolUse Bash) | commands run from inside `.tmp-session/wt/` (lanes): block `git push`, `git reset --hard`, `git clean -f`, `--no-verify`, `gh pr create/merge`, `gh workflow run`, write API calls. For everyone: block raw `gh pr merge` outside `tools/ship/merge`. |
| `secret-path-guard` (PreToolUse Read/Edit/Write/Bash) | block `.env*`, `*.pem`, `*.key`, `*.sops.*` decryption, `~/.config/sops/**`, and the local denylist file |
| `worktree-guard` | `git worktree add` only with an absolute path under `.tmp-session/wt/` |
| `public-safe-guard` `[P1]` | on commits, PR titles/bodies and issue text in **public** repos: block names in the local denylist (§10.2) |

Each hook has tests built from real payload fixtures (one block case, one near-miss pass case), run in `ecosys` CI.

`.claude/settings.json` (root):

```json
{
  "permissions": {
    "allow": ["Bash(just *)", "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)", "Bash(git add *)",
              "Bash(git commit *)", "Bash(gh pr view*)", "Bash(gh pr checks*)", "Bash(gh repo list*)"],
    "ask":   ["Bash(git push*)", "Bash(gh workflow run*)", "Bash(gh api -X POST*)", "Bash(gh repo create*)"],
    "deny":  ["Read(./.env)", "Read(./.env.*)", "Read(**/*.pem)", "Read(**/*.key)", "Read(~/.config/sops/**)",
              "Bash(gh pr merge*)", "Bash(sops -d*)", "Bash(age -d*)", "Bash(gh repo delete*)"]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [
        { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/ship-guard.py" },
        { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/worktree-guard.py" } ] },
      { "matcher": "Read|Edit|Write|Bash", "hooks": [
        { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/secret-path-guard.py" } ] }
    ]
  }
}
```

Child repos get a short `CLAUDE.md` that says what the repo is and imports nothing. The root rules apply because sessions start at the workspace root, the same as in the day-job workspace. A session opened directly inside a child repo reads that repo's `CLAUDE.md`, which points back to `../../CLAUDE.md`.

---

## 10. Privacy and boundaries

### 10.1 Data classes

`public` · `private` (applications, salaries, notes, plans) · `pii:contact` (other people's details) · `secret` (credentials, ID and financial documents, health documents). `secret` never enters any repo or agent workspace: it stays in a password manager.

### 10.2 Public-safe rule (MUST)

- Public repos (`ecosys`, `.github`, `lab-to-prod`, public projects) contain no employer names from the job search, recruiter names, salaries, application outcomes, contact details, internal names from current or past clients, or claude.ai links.
- **Enforcement:** a local denylist `~/.config/nghiep-pham-ecosys/denylist.txt` (never committed) feeds the pre-push hook and `public-safe-guard`. Public CI checks only **hashes** and generic patterns (e-mail, phone, salary-like amounts). Lesson from lab-to-prod PR #1: a public file that lists the names it is meant to hide defeats its purpose.
- Before a repo goes from private to public: a full-history gitleaks scan plus a denylist scan, and an ADR note.

### 10.3 Day-job boundary (MUST)

- **Copied from the day job:** ways of working only (rituals, lesson format, ship rules, folder pattern, ADR template).
- **Never copied:** employer or client code, data, prompts, schemas, account ids, issue keys, internal names, screenshots. The same applies to material from teaching or other client work. The names to watch are in `private/ops/boundaries.md` and the local denylist, never in a public file.
- The day job appears in this ecosystem only as (a) the weekly `work-block` time item and (b) public-safe achievement text in `vault/profile/profile.yaml`.
- Enforced by the denylist (§10.2) and a reviewer-privacy pass on any PR that touches `profile`, posts or project READMEs.

### 10.4 Encryption `[P1]`

sops + age for `vault/profile/private.sops.yaml` (salary history, references, contacts). The age private key lives in the password manager plus one offline copy, never in a repo or workspace. Agents are denied read access to it (§9.7).

---

## 11. Stack (ADR 0002, all free)

| Need | Choice | Notes |
|---|---|---|
| Code, CI, tracker | GitHub Free org, Actions, Projects | private repos have no rulesets *(verify)* |
| Blog | lab-to-prod's own choice (GitHub Pages or Cloudflare Pages) | Pages URL changes when the repo moves to the org |
| Notifications | Telegram bot | one channel for everything |
| CV | Typst (local) | |
| Secrets in files | sops + age `[P1]` | |
| Secret scan | gitleaks (CI + pre-push) + GitHub push protection on public repos | |
| Toolchain | mise (python, uv, node, pnpm, typst, gitleaks, just) | pinned in `.mise.toml` at the root |
| Editors/agents | VS Code + Claude Code extension, Claude Desktop Code tab, Kiro optional | same steering files |

---

## 12. Roadmap

### Phase 0 — 2–3 evenings

1. `[UI]` Create the org; set billing limits and 2FA (§4.6).
2. Create `ecosys`, `ops`, `vault`, `.github` repos. Build the workspace layout (§4.3), `repos.yaml`, `just ws-sync`/`ws-status`, VS Code workspace file.
3. Inventory personal repos; Nghiep marks move/keep/archive; transfer the chosen ones; move local clones under `projects/` (§4.4).
4. Root `CLAUDE.md`, `CONTEXT.md`, steering files, ADRs 0001–0003, skills `core`, `session`, `ship`, `lessons`, `jobs`, `weekly-review`.
5. Hooks `ship-guard`, `secret-path-guard`, `worktree-guard` with tests; `ecosys` CI (pr-title, hook tests, gitleaks, tracked-children check, `ci-result`).
6. Org board with fields; issue template in `.github`.
7. Migrate the job tracker into `ops/jobs/applications.yaml` + `tools/jobs/check`; create `ops/learn/deadlines.yaml`; `ops/plan/capacity.yaml`; `ops/automations.md`.

**Done when:** `just ws-status` lists every repo clean on `main`; a docs PR in `ecosys` goes branch → green → merge tool; `tools/jobs/check` runs on the migrated data and lists today's 30-day closures; the board shows next week's plan within budget; one full session was run with the start and end rituals.

### Phase 1 — rest of November and December

- Daily digest to Telegram (Claude scheduled task reading `ops` + deterministic sections from `ops` Actions).
- Sunday review task; old overlapping scheduled tasks retired per `ops/automations.md`.
- `vault/profile/profile.yaml` + schema + Typst CV; sops + age.
- `tmpl-project`, `project.yaml` registry, `public-safe-guard`, encrypted backup of `ops`/`vault`.
- Skills `learn`, `content`, `cv`.

**Done when:** two weeks of digests with no missed deadline; two weekly reviews done in ≤ 30 minutes; a CV PDF builds locally from the vault.

---

## 13. Triggers (kept from v0.2, not built by default)

| Trigger | Then |
|---|---|
| The YAML job pipeline exceeds ~150 active rows, or queries over it become painful | Postgres (Neon free) with the `jobs` schema from v0.2 §4.12, encrypted nightly export |
| An owner UI is needed to work from a phone | `career` app (Next.js on Vercel Hobby, Auth.js allowlist on `<you-id>`), v0.2 §4.3–4.4 |
| The first paid API call | AI gateway + ledger + caps, v0.2 §4.10 |
| Enough public content to be worth asking | private twin over public and private scope; public endpoint only after every control in v0.2 §9.6 |
| Two repos need to share code | a `packages` repo or a merge of those two (revisit ADR 0001) |
| Settings drift between repos twice | `org-drift` job comparing settings with `tools/setup/expected.json` |

---

## Appendix A. Root `CLAUDE.md` outline

```markdown
# nghiep-pham-ecosys: agent rules (root)
## Identity & scope       ← personal workspace of one person; areas jobs, learn, content, lab, ecosys
## Workspace map          ← root repo + meta/ private/ projects/ (each its own .git); repos.yaml is the list
## Hard rules (MUST)      ← each names its guard
   - start sessions at the workspace root; read CONTEXT.md, then the target repo's CLAUDE.md (ritual)
   - plan within capacity.yaml budgets and WIP limits (skill weekly-review)
   - work in worktrees under .tmp-session/wt/ (hook)
   - subagents never push, merge or run workflows (hook)
   - merge only through tools/ship/merge (hook)
   - no paid API or service without an explicit yes (P5)
   - never submit an application, publish a post or send a message without Nghiep (P8)
   - personal data only in private/ops or private/vault; public-safe writing elsewhere (hook + denylist)
   - nothing from the day job or clients except ways of working (§10.3)
   - never state live status from memory (ritual)
## Sources of truth       ← repo > canonical doc > memory > skill
## Imports
@agents/steering/workflow.md
@agents/steering/language-and-style.md
@agents/steering/data-rules.md
@agents/steering/machine-notes.md
## Which skill when       ← table → skills/<name>/SKILL.md
## Commands               ← just ws-sync | ws-status | ci | jobs-check | digest | review
```

## Appendix B. Language and style

Code, commits, PRs, issues, ADRs and technical docs: English. Chat with Nghiep, session logs, memory and private notes: Vietnamese. Posts: per lab-to-prod rules. Style: short sentences, active voice, numbers with units, no claim without a source.

## Appendix C. Brief template for a lane

```markdown
Task: <repo>#<n>: <title>. Do ONLY this task.
Goal: <1–2 sentences>
Worktree: /home/nghiep/projects/nghiep-pham-ecosys/.tmp-session/wt/<session>-<lane> · Branch: <type>/<n>-<slug> from origin/main
Read first: CONTEXT.md · <repo>/CLAUDE.md · lessons for <areas>
Done when: <copied from the issue, unchanged>
Files in scope: <paths>
Test: just ci (in the target repo)
Ending: commit `<type>: …` with body `Refs <repo>#<n>`; do NOT push, open PRs, merge, run workflows or open secret paths;
return JSON {ready, blocked_reason, branch, commits, summary, followups, lessons}
```
