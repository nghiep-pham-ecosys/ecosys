# ADR 0005: Template first, and the lab portfolio

- **Status:** Proposed (Accepted after Nghiep's yes on this text)
- **Date:** 2026-11-17
- **Amends:** ADR 0004 (decision 4, Publishing, Capacity and routines, Phases, Follow-ups)

## Context

- ADR 0004 (2026-11-16) planned to build `ai-engineering-lab` by hand in 2026-W48. Its generic base would move back
  into `tmpl-project` (ecosys#7) after project 2, about 2026-W52. That plan was a stated exception to spec §5.5
  ("new projects start from `tmpl-project`").
- Later on 2026-11-16, Nghiep approved a private plan for engineering practice outside AI. It adds two more public
  lab repos, `eng-analytics-lab` and `platform-lab`. With three new repos to create, a template built first has
  three real users and one `copier update` loop, instead of one hand-built repo and a back-port.
- The private plan was drawn from the same unpublished local research as ADR 0004. Only ways of working carry over
  (spec §10.3), through the clean room in ADR 0004. This ADR therefore names repos and rules, not the project list.
  The project list stays private.
- On 2026-11-17 Nghiep approved a master plan with sessions and budgets. It moves the dates:
  - the AI lab starts in 2026-W52, not W48;
  - the template is finished in W49–W51;
  - the first lesson moves into 2027-Q1.
- A local draft of the template (Copier, v0.1) exists since 2026-11-17. It generates a public and a private
  variant, and `just ci`, actionlint and gitleaks pass in both.
- Constraints:
  - ADR 0003: one yes per new repo, and a yes before anything is published.
  - P5 and ADR 0002: $0.
  - Spec §2.2: WIP limits.
  - Spec §5.4: lab-to-prod is the only publishing site.

## Decision

### 1. Template first (replaces ADR 0004 decision 4)

- `tmpl-project` v0.1 is finished before any new repo is created. Every new repo is generated from it, including
  `ai-engineering-lab`.
- The template holds the generic base only:
  - README, `project.yaml`, a `CLAUDE.md` stub that points to the root rules;
  - licence files (MIT code; CC BY 4.0 text, optional) and `NOTICE`;
  - `justfile` and `.mise.toml`;
  - CI with gitleaks, `ci-result` and `pr-title`;
  - a pre-push hook for private repos.
- The AI-specific layer stays in `ai-engineering-lab`, as in ADR 0004: gates, eval plan, card, risk notes and
  registers.
- The spec §5.5 exception in ADR 0004 ("Relation to `tmpl-project`") is withdrawn. ecosys#7's "Done when" is met by
  the first repo generated from the template.
- `tmpl-project` sits in the `ecosys` area. Creating it needs Nghiep's yes (ADR 0003).

### 2. Lab portfolio

| Repo | Area | Status | Starts |
|---|---|---|---|
| `process-sim-lab` | lab | active | running |
| `physic-ai-for-everyone` | lab | active-light | running |
| `ai-engineering-lab` | lab | planned | 2026-W52, after a yes |
| `eng-analytics-lab` | lab | planned | about 2027-W06, after a yes |
| `platform-lab` | lab | planned | when another lab is paused or done |
| `nghiep-motion-studio` | lab | paused (spec only) | — |

- `lab` WIP grows one repo at a time:
  - 2 now;
  - 3 from 2026-W52;
  - 4 in 2027-Q1, the limit set on 2026-11-16 (capacity 4 h/week).
- Spec §2.2 still applies inside each repo: one active build project at a time. A project's retro comes before the
  next project starts.
- The non-AI work is ordered by dependency, not by date. It needs about 70 sessions. At the session budget approved
  on 2026-11-17, that is well past the 17–18 weeks estimated on 2026-11-16, so it has no fixed end date. Each quarterly
  review records its pace, and Go, Hold or Kill. Hold and Kill are valid outcomes, as in ADR 0004.
- Heavy local stacks (Kubernetes, streaming and the AI lab's model and graph stack) never run at the same time.

### 3. Lessons and publishing (amends ADR 0004 "Publishing")

- Two sections on lab-to-prod, both on the one site (spec §5.4):
  - "Lab lessons" for `ai-engineering-lab`;
  - "Practice lessons" for the other labs.
- A section is added only when its first lesson exists, built from merged lab work. Adding it is a publish step, so
  it needs Nghiep's yes. The fixed W51 date in ADR 0004 is dropped.
- At most one lesson a week across all labs (about 2 h, `content` budget). Other lessons queue.
- Posts and lessons come only from merged project work (master plan, 2026-11-17).

### 4. Season 2 by dependency (amends ADR 0004 "Revisit when")

- Candidate 13 (operate and retire) starts only when two projects have passed G3: AI project 4, and the platform-lab
  project that runs a service with objectives.
- Candidate 14 (adapt a small model) starts after AI project 2 passes G3, when GPU time is free.
- The calendar checkpoint is replaced by a pace check after AI project 2's retro.

### 5. Routines (amends ADR 0004 "Capacity and routines")

- No new cloud routine is added for `ai-engineering-lab` or `eng-analytics-lab` by this ADR. Two things change that:
  - ADR 0006 (Claude Code drives the work, Claude Chat reports) sets the routine budget;
  - each new routine needs Nghiep's yes.
- The Tuesday and Friday 07:00 routine in ADR 0004 is withdrawn until then.

### 6. Phases (replaces ADR 0004 "Phases")

| Phase | Weeks | Work | Done when |
|---|---|---|---|
| T template | 2026-W49–W51 | finish and verify `tmpl-project` v0.1; create the repo after a yes | template CI green; a generated repo passes `just ci` |
| P0 frame | 2026-W52–W53 | AI lab generated from the template after a yes; ADR 0004 P0 work, unchanged | CI green; one local model call recorded and replayed in CI |
| P1 | 2027-W01–W06 | AI projects 2 and 4 | eval numbers against thresholds; first lesson ready |
| Pace check | after project 2 retro | pace and hours | on pace → continue; behind → a lesson for every second project, or Hold |
| P2 | about 2027-W07–W11 | projects 3 and 6 | as P1 |
| P3 | about 2027-W12–W19 | projects 1, 7, 8 and 5 | as P1 |
| P4 | about 2027-W20–W25 | projects 9, 10 and 11; CCAI workshop draft | as P1, and a draft ready for Nghiep |
| Non-AI | from 2027-Q1 | `eng-analytics-lab` first, then the rest by dependency | per project gates; reviewed each quarter |

Dates after P1 are estimates. The pace check moves them.

## Options considered

- **Keep ADR 0004 decision 4 (hand-build the AI lab, back-port later):** rejected. With three new repos, the template
  has three users, and copying the base by hand into two more repos would drift.
- **Build `tmpl-project` first, in W48 (the 2026-11-16 plan):** rejected for the date. The W48 sessions go to the
  new working model (ADR 0006) and the content rule, so the template moves to W49–W51.
- **One lesson section for all labs:** rejected. Readers looking for AI engineering would have to filter practice
  lessons out.
- **Fixed end dates for the non-AI work:** rejected. At the approved session budget they would slip every month.
  A quarterly Go, Hold or Kill is used instead.
- **Create all three repos now, while the template is a draft:** rejected. Generated repos would start from an
  unverified base.

## Consequences

- One template is the base of every new repo. Fixes reach existing repos through `copier update`.
- The AI lab starts four weeks later than ADR 0004 planned. The first lesson moves into 2027-Q1.
- The non-AI portfolio has an order, not a date. Pace data, not the plan, decides how much of it gets built.
- `lab` reaches WIP 4 only in 2027-Q1. `platform-lab` waits for a free slot.
- Spec §5.5 holds with no exception.

## Revisit when

- The template needs a breaking change after two repos use it.
- The pace check after AI project 2 shows the lab more than one project behind.
- A quarterly review records Hold or Kill for a non-AI lab.
- A lesson takes more than 2 h twice, or the weekly lesson cap blocks a finished lesson for more than 4 weeks.

## Decisions by Nghiep

- 2026-11-16 (private plan): three new public repos; `lab` WIP 2 → 4 and 3 → 4 h/week; template first; season 2 by
  dependency; a separate "Practice lessons" section.
- 2026-11-17 (master plan): the moved dates (AI lab 2026-W52, template W49–W51, first lesson in 2027-Q1); repo
  statuses; lessons only from merged work; routines decided in ADR 0006.

## Follow-ups

| Item | Repo | When |
|---|---|---|
| Update ecosys#7 scope to "template first" and link this ADR | ecosys | with this ADR |
| Mark ADR 0004 as amended by this ADR | ecosys | with this ADR |
| Finish and verify `tmpl-project` v0.1 from the local draft | ecosys | 2026-W49 |
| Create `tmpl-project` after a yes; add it to `repos.yaml` | ecosys | 2026-W49–W51 |
| Vault CI, then move the research originals to the vault, before any lesson or method text | vault | 2026-W48–W49 |
| Generate `ai-engineering-lab` after a yes | ecosys | 2026-W52 |
| Routine budget and roles | ecosys (ADR 0006) | 2026-W48 |
