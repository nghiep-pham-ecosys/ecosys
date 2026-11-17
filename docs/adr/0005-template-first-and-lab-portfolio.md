# ADR 0005: Template first, and the lab portfolio

- **Status:** Proposed (set to Accepted, with the date, after Nghiep's yes on this text)
- **Date:** 2026-11-17
- **Amends ADR 0004:**
  - decision 4;
  - "Relation to `tmpl-project`";
  - "Lessons" (review date);
  - "Publishing";
  - "Capacity and routines";
  - "Phases";
  - "Revisit when";
  - "Follow-ups".

  Every date elsewhere in ADR 0004 follows the Phases table of this ADR.

## Context

- ADR 0004 (2026-11-16) planned to build `ai-engineering-lab` by hand in 2026-W48. Its generic base would then move
  back into `tmpl-project` (ecosys#7) after project 2, about 2026-W52. That plan was a stated exception to spec §5.5
  ("new projects start from `tmpl-project`").
- Later on 2026-11-16, Nghiep approved a private plan for engineering practice outside AI. It adds two public lab
  repos, `eng-analytics-lab` and `platform-lab`. That makes three new repos. A template built first therefore has
  three real users and one `copier update` loop, instead of one hand-built repo and a back-port.
- The private plan comes from the same unpublished local research as ADR 0004. Only ways of working carry over
  (spec §10.3), through the clean room in ADR 0004. So this ADR names repos and rules, and keeps the project list
  private.
- On 2026-11-17 Nghiep approved a master plan with a session schedule and two budgets: agent hours for Claude Code
  sessions, and Nghiep's own hours per area. It moves three dates:
  - the AI lab starts in 2026-W52, not W48;
  - the template is finished in W49–W51;
  - the first lessons move into 2027-Q1.
- A local draft of the template (Copier, v0.1) exists since 2026-11-17. It generates a public and a private variant.
  `just ci`, actionlint and gitleaks pass in both.
- Constraints:
  - ADR 0003: one yes per new repo, and a yes before anything is published.
  - P5 and ADR 0002: $0.
  - Spec §2.2: WIP limits.
  - Spec §5.4: lab-to-prod is the only publishing site.

## Decision

### 1. Template first (replaces ADR 0004 decision 4 and "Relation to `tmpl-project`")

- `tmpl-project` v0.1 is finished before any new repo is created. Every new repo is generated from it, including
  `ai-engineering-lab`.
- The template holds the generic base only:
  - README, `project.yaml`, and a `CLAUDE.md` stub that points to the root rules;
  - licence files (MIT for code, optional CC BY 4.0 for text) and `NOTICE`;
  - `justfile` and `.mise.toml`;
  - CI with gitleaks, `ci-result` and `pr-title`;
  - a pre-push hook for private repos.
- The AI-specific layer stays in `ai-engineering-lab`, as in ADR 0004: gates, eval plan, card, risk notes and
  registers.
- ADR 0004 made a stated exception to spec §5.5. That exception is withdrawn. ecosys#7's "Done when" is met by the
  first repo generated from the template.
- `tmpl-project` sits in the `ecosys` area. Creating it needs Nghiep's yes (ADR 0003).

### 2. Lab portfolio

| Repo | Visibility | Area | Status | Starts |
|---|---|---|---|---|
| `process-sim-lab` | public | lab | active | running |
| `physic-ai-for-everyone` | private | lab | active, light cadence | running |
| `ai-engineering-lab` | public | lab | planned (no repo yet) | 2026-W52, after a yes |
| `eng-analytics-lab` | public | lab | planned (no repo yet) | about 2027-W06, after a yes |
| `platform-lab` | public | lab | planned (no repo yet) | when another lab is paused or done |
| `nghiep-motion-studio` | public | lab | paused (spec only) | — |

- Spec §2.2 lets a new side project into `lab` only when another one is paused.
  - ADR 0004's stated exception to §2.2 is extended: `lab` WIP grows without a pause, one repo at a time. It is 2 now,
    3 from 2026-W52, and 4 in 2027-Q1. The WIP limit of 4 was set on 2026-11-16.
  - `platform-lab` follows §2.2 as written.
  - Inside each lab repo, one build project is active at a time. A project's retro comes before the next one starts.
- The non-AI work is ordered by dependency, not by date.
  - Its estimated end is 2027-Q4 to 2028-Q1, assuming one non-AI session a week or less.
  - Each quarterly review re-checks that estimate and records the pace, plus Go, Hold or Kill.
  - Hold and Kill are valid outcomes, as in ADR 0004.
- Heavy local stacks never run at the same time. That includes the AI lab's model and graph stack. Each stack has a
  peak-RAM check.

### 3. Lessons and publishing (amends ADR 0004 "Publishing" and the "Lessons" review date)

- Two sections on lab-to-prod, both on the one site (spec §5.4):
  - "Lab lessons" for `ai-engineering-lab`;
  - "Practice lessons" for the other labs.
- A section is added only when its first lesson exists, built from merged lab work.
  - Adding a section is a publish step, so it needs Nghiep's yes.
  - The fixed W51 date in ADR 0004 is dropped.
- At most one lesson a week across all labs. Other lessons queue.
  - Drafting takes at most 2 agent hours per lesson.
  - Nghiep's read counts as `content`.
- Posts and lessons come only from merged project work (master plan, 2026-11-17).
- The lesson format choices in ADR 0004 are reviewed at the pace check after AI project 2's retro, not at W52.

### 4. Season 2 by dependency (amends ADR 0004 "Revisit when")

- Candidate 13 (operate and retire) starts only when two projects have passed G3:
  - AI project 4;
  - a platform-lab project with the monitoring and service-level objectives that candidate 13 reuses.
- Candidate 14 (adapt a small model) starts after AI project 2 passes G3, when GPU time is free.
- Pace checks replace the W52 and 2027-W19 calendar checkpoints:
  - one at the 2026-W53 review, together with the 2027-Q1 plan;
  - one after AI project 2's retro;
  - one after project 11.
- The other "Revisit when" items of ADR 0004 stay: free-tier terms, a paid API call, a reader site, and a privacy
  blocker traced to method text.

### 5. Capacity and routines (amends ADR 0004 "Capacity and routines")

- `lab` hours go from 3 to 4 h/week, with 1 h taken from `learn` (2026-11-16). Nghiep's split:
  - from 2026-W52, 0.5 h of review and 1 h of GPU time for the AI lab;
  - the rest across the other active labs.
- Build work counts against agent hours (Claude Code sessions), not against Nghiep's hours.
- This ADR adds no cloud routine for `ai-engineering-lab` or `eng-analytics-lab`.
  - ADR 0006 (Claude Code drives the work, Claude Chat reports) sets the routine budget.
  - Each new routine needs Nghiep's yes.
  - The Tuesday and Friday 07:00 routine in ADR 0004 is withdrawn until then.
- `platform-lab` runs in local sessions only.

### 6. Phases (replaces ADR 0004 "Phases")

| Phase | Weeks | Work | Done when |
|---|---|---|---|
| T template | 2026-W49–W51 | finish and verify `tmpl-project` v0.1; create the repo after a yes | template CI green; a generated repo passes `just ci` |
| P0 frame | 2026-W52–W53 | AI lab generated from the template after a yes; ADR 0004 P0 work minus what the template supplies (skeleton, licences, `NOTICE`, CI); `method.md` and `_template` may run into 2027-W01 | CI green; one local model call recorded and replayed in CI |
| Pace check | 2026-W53 review | Q1 plan; pace of the template and P0 | dates below confirmed or moved |
| P1 | 2027-W01–W06 | AI projects 2 and 4 | eval numbers against thresholds; 2 lessons and quizzes live after Nghiep's yes |
| Pace check | after project 2 retro | pace and hours | on pace → continue; behind → a lesson for every second project, or Hold |
| P2 | about 2027-W07–W11 | projects 3 and 6 | as P1 |
| P3 | about 2027-W12–W19 | projects 1, 7, 8 and 5 | as P1 |
| P4 | about 2027-W20–W25 | projects 9, 10 and 11; CCAI workshop draft | as P1, and a draft ready for Nghiep |
| Season 2 decision | after project 11 | candidates 13 and 14 by the gates in section 4 | Go, Hold or archive, recorded in an ADR note |
| Non-AI | from 2027-Q1 | `eng-analytics-lab` first, then the rest by dependency | per-project gates; reviewed each quarter |

Dates after P1 are estimates. The pace checks move them.

## Options considered

- **Keep ADR 0004 decision 4 (hand-build the AI lab, back-port later):** rejected. With three new repos, the
  template has three users, and copying the base by hand into two more repos would drift.
- **Build `tmpl-project` first, in W48 (the 2026-11-16 plan):** rejected for the date. The W48 sessions go to the new
  working model (ADR 0006) and to the content rule, so the template moves to W49–W51.
- **One lesson section for all labs:** rejected. Readers looking for AI engineering would have to filter practice
  lessons out.
- **Fixed end dates for each non-AI project:** rejected. At the approved session budget they would slip every month.
  An estimated end range, checked each quarter, is used instead.
- **Cut the non-AI work to the template and its first wave:** not chosen now. It stays the fallback when a quarterly
  review records Hold.
- **Create all three repos now, while the template is a draft:** rejected. Generated repos would start from an
  unverified base.

## Consequences

- One template is the base of every new repo. Fixes reach existing repos through `copier update`.
- The AI lab starts four weeks later than ADR 0004 planned. The first lessons move into 2027-Q1.
- The non-AI portfolio has an order and an estimated end range, not fixed dates. Pace data decides how much of it
  gets built.
- `lab` reaches WIP 4 only in 2027-Q1, through the extended §2.2 exception. `platform-lab` waits for a free slot.
- Spec §5.5 holds with no exception.

## Revisit when

- The template needs a breaking change after two repos use it.
- A pace check shows the AI lab more than one project behind.
- A quarterly review records Hold or Kill for a non-AI lab.
- A lesson takes more than 2 agent hours twice, or the weekly lesson cap holds a finished lesson back for more than
  4 weeks.

## Decisions by Nghiep

- **2026-11-16** (private plan):
  - three new public repos;
  - `lab` WIP 2 → 4, and 3 → 4 h/week taken from `learn`;
  - template first;
  - season 2 by dependency;
  - a separate "Practice lessons" section;
  - one light routine for `eng-analytics-lab`, deferred by this ADR to ADR 0006 and a yes;
  - `platform-lab` in local sessions only.
- **2026-11-17** (master plan):
  - the moved dates: AI lab 2026-W52, template W49–W51, first lessons in 2027-Q1;
  - the repo statuses;
  - lessons only from merged work;
  - two budgets (agent hours and Nghiep's hours);
  - routines decided in ADR 0006.

## Follow-ups

This table replaces ADR 0004's Follow-ups.

| Item | Repo | When |
|---|---|---|
| Update ecosys#7 scope to "template first" and link this ADR | ecosys | with this ADR |
| Mark ADR 0004 as amended by this ADR | ecosys | with this ADR |
| ADR 0006: roles of Claude Code and Claude Chat, routine budget | ecosys | 2026-W47 review (2026-11-22) |
| Routine budgets in `automations.md` | ops | 2026-W48 |
| Vault CI, then move the research originals to the vault, before any lesson or method text | vault | 2026-W48–W49 |
| Finish and verify `tmpl-project` v0.1 from the local draft | ecosys | 2026-W49 |
| Create `tmpl-project` after a yes; add it to `repos.yaml` | ecosys | 2026-W49–W51 |
| Confirm the free-tier API keys (created by Nghiep, outside repos) | none | 2026-W49 review |
| Recheck lab data sources whose licence is unverified | ai-engineering-lab | 2026-W51, before data is committed |
| Generate `ai-engineering-lab` after a yes; add it to `repos.yaml` | ecosys | 2026-W52 |
| Pace check and 2027-Q1 plan | ops | 2026-W53 review |
| Create `eng-analytics-lab` after a yes | ecosys | about 2027-W06 |
| Add "Lab lessons" or "Practice lessons" when the first lesson exists, after a yes | lab-to-prod | when ready |
