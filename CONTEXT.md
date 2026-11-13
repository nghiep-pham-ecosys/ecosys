# CONTEXT: whole-system map

One page that says what exists and where each fact lives. The contract is `docs/spec.md`.
If this page and a repo disagree, the repo wins (precedence: repo > canonical doc > memory > skill).

## Areas

| Area | What | Source of truth | Phase |
|---|---|---|---|
| `jobs` | search, applications, follow-ups, interview prep | `private/ops/jobs/applications.yaml` | P0 |
| `learn` | courses, exams, study tracks | `private/ops/learn/deadlines.yaml`, `private/ops/learn/tracks/*.md` | P0 deadlines, P1 tracks |
| `content` | posts and blog | `projects/lab-to-prod` | running |
| `lab` | experiments and side projects | each project repo under `projects/` | running |
| `ecosys` | this workspace: rules, tools, CI | root repo `ecosys` | P0 |
| `profile` | facts about Nghiep, CV source | `private/vault/profile/profile.yaml` | P1 |
| `work` | day job | not here: one weekly `work-block` item on the board | — |

Weekly hours and WIP limits per area: `private/ops/plan/capacity.yaml`.

## Repos

Org `nghiep-pham-ecosys`. Every repo uses default branch `main`. The machine-readable list is `repos.yaml`. Private
repos whose names must stay out of public files are listed only in `private/ops/repos.private.yaml`; the `ws` tools
merge it, and `just ws-workspace` writes a gitignored local VS Code workspace that includes them.

| Repo | Visibility | Local path | Area | Purpose |
|---|---|---|---|---|
| `ecosys` | public | `.` | ecosys | root repo: rules, steering, skills, hooks, tools, ADRs |
| `.github` | public | `meta/.github` | ecosys | org profile, issue and PR templates, reusable workflows |
| `ops` | private | `private/ops` | ecosys | job pipeline, plans, capacity, deadlines, session logs, memory, private lessons |
| `vault` | private | `private/vault` | profile | profile facts, stories, drafts, research notes |
| `lab-to-prod` | public | `projects/lab-to-prod` | content | content lab: calendar, posts, blog, render and publish workflows |
| `claude-for-everyone-vi` | private | `projects/claude-for-everyone-vi` | learn | learning material project |
| `physic-ai-for-everyone` | private | `projects/physic-ai-for-everyone` | lab | Physical AI side project |
| `nghiep-motion-studio` | public | `projects/nghiep-motion-studio` | lab | motion studio side project |
| `process-sim-lab` | public | `projects/process-sim-lab` | lab | chemical process and equipment simulation with an agent interface |

Not part of this workspace: other folders under `~/projects`, forks of third-party repos, and anything owned by an employer or client.

## Runners

| Runner | Runs | Limits |
|---|---|---|
| Claude Code sessions | building and changing repos; drafts that need judgement | Claude plan limits |
| Claude scheduled tasks | mail checks, draft work, digest text, Sunday review draft `[P1]` | plan limits; each task is listed in `private/ops/automations.md` |
| GitHub Actions in `ops` (private) | deterministic jobs: `tools/jobs/check`, deadline scan, capacity check `[P1]` | private-repo minutes *(verify)*; at most daily |
| GitHub Actions in public repos | CI, lab-to-prod validate, render, publish | logs are public: no private data |
| `just` + `tools/` locally | `ws-sync`, `ws-status`, `ci`, `jobs-check` | no LLM |

Notifications go to one channel: the Telegram bot `[P1]`. LLM work runs inside Claude subscriptions only (no paid API).

## Data homes

| Data class | Lives in | Never in |
|---|---|---|
| `public` | public repos (`ecosys`, `.github`, `lab-to-prod`, public projects) | — |
| `private` (applications, salaries, plans, notes) | `private/ops`, `private/vault` | public repos, public CI logs |
| `pii:contact` (other people's details) | `private/ops`, `private/vault` (sops-encrypted `[P1]`) | public repos |
| `secret` (credentials, ID, financial, health documents) | password manager only | any repo or agent workspace |

Rules: `agents/steering/data-rules.md`. Writing guide: `docs/standards/public-safe-writing.md`.

## Where each fact lives

| Fact | Home |
|---|---|
| Agent rules | `CLAUDE.md` + `agents/steering/*.md` |
| Flows (session, ship, lessons, jobs, review) | `skills/<name>/SKILL.md` |
| Decisions | `docs/adr/` |
| Repo list | `repos.yaml` |
| Toolchain versions | `.mise.toml` |
| Org settings and how they were set | `docs/runbooks/org-setup.md` |
| Applications and their stages | `private/ops/jobs/applications.yaml` |
| Learning deadlines | `private/ops/learn/deadlines.yaml` |
| Weekly budget and WIP limits | `private/ops/plan/capacity.yaml` |
| Scheduled tasks | `private/ops/automations.md` |
| Session history and memory | `private/ops/sessions/`, `private/ops/memory.md` |
| Lessons (public-safe) | `skills/lessons/lessons.md` |
| Lessons (personal) | `private/ops/lessons.md` |
| Names that must never appear in public | `private/ops/boundaries.md` + local denylist |
| Board items and their status | org GitHub Project "Ecosys board" (private) |
| Post calendar and drafts | `projects/lab-to-prod` |
| Profile facts `[P1]` | `private/vault/profile/profile.yaml` |
| Research and reading notes, content ideas, messages between Claude Code and Claude Chat | Notion workspace (private; ids in `private/ops/notion.yaml`) |
| Dashboard and project overview in Notion | a mirror of the rows above, written at session end (skill `session`); edit the source, not the mirror |
| Calendar time blocks | Google Calendar; area mapping in `private/ops/plan/routine.yaml` |
