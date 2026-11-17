# ADR 0004: AI engineering lab monorepo

- **Status:** Accepted; amended by ADR 0005 (decision 4, Relation to `tmpl-project`, Lessons review date, Publishing, Capacity and routines, Phases, Revisit when, Follow-ups); "Capacity and routines" also amended by ADR 0006 (routine budget and how routine PRs merge)
- **Date:** 2026-11-16

## Context

- Nghiep wants to learn AI engineering in public through 12 projects in one domain: Climate Change AI (CCAI) papers
  plus materials and chemistry. The project list, the order and the model policy were approved on 2026-11-16.
- Earlier local research, not published, studied two things: a project lifecycle kit and a course format for
  engineering lessons. Nghiep wants the lab to combine the 12 projects with that knowledge. Only ways of working carry
  over (spec §10.3). Each practice is rewritten from a cited public source (spec §10.2).
- A coverage review on 2026-11-16 checked every research topic against the lab. Each AI-engineering topic is covered
  by a project, the method or a lesson, or is named below as a season 2 candidate. Topics outside AI engineering are
  out of scope. The topic map stays private.
- Constraints:
  - P5 and ADR 0002: $0, no paid API, only the actions ADR 0002 allows (GitHub-owned plus four listed patterns).
  - Spec §5.4: lab-to-prod is the only publishing site.
  - Spec §5.5 and §2.2: one `project.yaml` per repo, WIP limits, one new project at a time.
  - ADR 0003: approvals, including one yes per new repo.
- Hardware: one laptop GPU with 8 GB VRAM, about 1 h/week of GPU session time. Cloud routines have no GPU.
- Groq free-tier chat models allow 8K tokens per minute (console, read by Nghiep on 2026-11-16; some models differ).
  The LLM layer must limit by tokens, not only by requests.

## Decision

### Repo and scope

- Scope: AI engineering only, meaning building, evaluating, securing, operating and adapting LLM systems.
- One public repo, `ai-engineering-lab`, area `lab`, one root `project.yaml`.
- The 11 build projects are folders under `projects/`, not separate WIP items. Project 12 (teardown posts and CCAI
  community) is a stream that runs alongside them, with no folder and no gates.
- Only one build project is active at a time. Order: 2 → 4 → 3 → 6 → 1 → 7 → 8 → 5 → 9 → 10 → 11, about 2 weeks each.

| # | Project | Gate metric (G3) | Main risk lens (OWASP LLM Top 10 2025 *(verify)*) |
|---|---|---|---|
| 2 | Hybrid search (BM25 + pgvector + reranker) | recall@k, nDCG against a BM25-only baseline | LLM08 vector and embedding weaknesses |
| 4 | Self-correcting RAG that refuses without evidence | correct-refusal rate, faithfulness | LLM09 misinformation |
| 3 | GraphRAG on material → process → property | multi-hop accuracy against project 2 | LLM05 improper output handling |
| 6 | Hand-written MCP server and client, read-only | tool-call contract tests | LLM06 excessive agency |
| 1 | Context assembler with a token budget | quality at a fixed budget, tokens per task | LLM10 unbounded consumption |
| 7 | 3-tier memory with TTL | fact recall, expiry tests | LLM02 sensitive information disclosure |
| 8 | Typed agent team with unit and constraint checks | pass^k, violations caught | LLM06 excessive agency |
| 5 | Durable workflow with an approval step | resume-after-crash tests, pass^k | LLM06 excessive agency (approval before side effects) |
| 9 | Trajectory eval as a local GitHub Action | match against a golden DAG | LLM03 supply chain |
| 10 | PII and prompt-injection proxy, synthetic data only | mask recall, block rate, false-positive rate | LLM01 prompt injection |
| 11 | Routing and semantic cache with gCO2 metering | tokens, requests and gCO2 per task, quality delta | LLM10 unbounded consumption |

### Layout

```
ai-engineering-lab/
├── README.md, CLAUDE.md (stub that points to the ecosys rules), project.yaml
├── LICENSE (MIT, code), LICENSE-content (CC BY 4.0, text), NOTICE (attributions)
├── docs/adr/            repo ADRs and per-project ADRs (MADR, minimal)
├── docs/method.md       the five lab gates, with a "Based on" line per public source
├── sources.yaml         register of public sources: url, licence, tier, permissions, date checked
├── limits.yaml          free-tier provider register: limits, data-use terms, date checked, fallback
├── data/manifest.yaml   source, licence, url, committed; plus fetch scripts
├── core/                OpenAI-compatible client, cassette replay, token limiter, token and gCO2 metering, eval runner
├── infra/               docker-compose: Postgres + pgvector, Neo4j Community
├── checks/              manifest, sources, gates and quiz checks (stdlib + PyYAML, unittest)
├── projects/_template/  README front matter, spec.md, eval/, card.md, runbook.md, lesson.md, quiz.json
└── projects/02-hybrid-search/ … 11-routing-cache/
```

### Method: five gates (based on GOV.UK service phases, Spec Kit and AI-DLC)

| Gate | Evidence | Check |
|---|---|---|
| G0 Scope | problem, why AI is needed, 2-week appetite, autonomy level, 3–5 learning objectives written before any code | manual, at the Sunday review |
| G1 Spec | `spec.md` with acceptance criteria, a C4 container view (Mermaid) and no-gos, eval plan with 20–50 tasks including "should not" cases, thresholds, risk notes, one ADR for the main choice | `check_gates` |
| G2 Skeleton | folder from `_template`, cassette replay green in CI with no model call, `runbook.md` | CI |
| G3 Ship | final eval against thresholds with a bootstrap confidence interval (pass^k for agent projects), judge from a different model family than the generator, model and prompt card, lesson and quiz drafted from the eval outputs | CI + reviewer agents |
| G4 Retro | lesson-log entry, shared code moved to `core/`, a template fix if a gate missed something | manual, at the next G0 |

- Stopping is a valid outcome (GOV.UK Service Manual, discovery). The lab's own names for gate outcomes: Go, Kill,
  Hold and Recycle.
  A killed project's retro becomes its lesson.
- `method.md` is based on the GOV.UK Service Manual phases (OGL v3), GitHub Spec Kit (MIT) and AWS AI-DLC (MIT-0).
  It links, without copying, to Anthropic's agent and eval guidance, the NIST AI RMF and the OWASP LLM Top 10.

### Coverage (reviewed 2026-11-16)

| Topic | Where | Status |
|---|---|---|
| Retrieval and RAG | projects 2, 3, 4, 1 | built |
| Agents, tools, MCP, workflows | projects 6, 8, 5 | built |
| Cost, routing, gCO2 | projects 1, 11 | built |
| LLM security (OWASP LLM Top 10) | one lens per project; poisoned-document cases (LLM04) in 2 and 4; prompt-leak test (LLM07) in 10 | built |
| Eval rigour | `core/` eval runner reports a confidence interval; judge calibration against a small human gold set in 4 | folded |
| Data for AI | dataset and embedding hashes in `data/manifest.yaml`; ingest checks in 2 and 3 | folded |
| Agent governance | `inventory.yaml` (owner, autonomy level, tools, data, eval suite, retire date); hard limits and a kill switch in 5 | folded |
| Performance | latency indicator in 11 | folded |
| LLM observability | GenAI tracing wrapper in `core/`, first used by 9 | folded |
| AI-assisted delivery | lesson angle in 8 and 9, with the lab's own routine PRs as the case | lesson |
| Operating and retiring a live LLM system | season 2 candidate 13 | open |
| Model adaptation (fine-tuning, tracking, registry, promotion) | season 2 candidate 14 | open |

- Season 2 candidates:
  - **13 Operate and retire:** run project 4 (or 11) as a local service with traces, a latency and quality objective,
    a drift check, versioned prompts with gated promotion and rollback, and a written retirement.
  - **14 Adapt a small model:** fine-tune the reranker or embedder (LoRA on the local GPU *(verify)*) on materials and
    chemistry query pairs, with local experiment tracking, a registry and promotion against the project 2 baseline.
- Heavier items (code sandbox, application security standard, load test, SBOM and signing) go to candidate 13 or the
  lab CI backlog, not into season 1 projects.

### Lessons

- One lesson and one quiz per project. Each lesson covers three angles: build, evaluate, govern.
- Lesson structure follows Diátaxis (explanation plus how-to; CC BY-SA, so linked and not adapted).
- Own choices, reviewed at W52: `lesson.md` is 800–1,500 words and links to the project code; `quiz.json` holds
  10 items with an 80% pass mark; the item bank is at least 3× the quiz length (2× in v0).
- Every item names its learning objective and its source. Only our own items, never vendor exam content.
- Drafting is capped at 2 h per lesson. Quizzes are self-checks: answers sit in the page source.

### Clean room for unpublished research

- The research originals move to the private `vault` repo before `method.md` or any lesson text is written. They are
  never quoted, linked or summarised in a public file.
- Lane and routine briefs exclude the local research folder and the vault.
- Every practice in `method.md` cites a registered public source, or it is dropped.
- No example, number, tool name, incident or comparison from unpublished or employer material appears in the repo.
- reviewer-privacy reviews every PR that touches `docs/`, a README, `card.md`, `lesson.md` or `quiz.json`.

### Licences and data

- Code MIT. Method, lessons and quizzes CC BY 4.0, the same as the lab-to-prod content licence.
- Source tiers in `sources.yaml`:
  - Green (OGL v3, MIT, MIT-0, CC BY, Apache 2.0): adapt, with a `NOTICE` line or a "Based on" credit.
  - Amber (CC BY-SA, for example OWASP and Diátaxis): link and summarise in our own words only.
  - Red or unchecked (vendor docs, PRINCE2, ISO, books): link and summarise only. Never used as quiz content.
- `check_sources` fails when an amber, red or unchecked source is marked as adapted.
- Data: commit only CC0, CC BY or CC BY-SA files with a manifest row. Everything else is fetched at run time.
  `check_manifest` enforces this.
- Project 10 uses synthetic data only (Example Co, Acme).

### Models (a scoped extension of ADR 0002)

- Project code may call local models (Ollama) and the Groq and Gemini free tiers, on public or synthetic data only.
  On unpaid quota, Google may use inputs to improve its products (Gemini API terms, read on 2026-11-16).
- Tiers (policy of 2026-11-16; exact model ids live in `limits.yaml` and change there without a new ADR):
  - small: Qwen3 8B on the local GPU, fallback a small Groq model;
  - large: a large Groq model, fallback Gemini Flash Lite, then Gemma;
  - judge: a Groq model from a different family than the generator;
  - embeddings and reranker: local (bge-m3, bge-reranker-v2-m3).
- CI and cloud routines only replay recorded responses (cassettes). `core/` raises an error when a replay misses.
  No model key is stored in CI.
- Free-tier keys are created by Nghiep after a yes (ADR 0003) and live outside the repo.
- Claude has no runtime role in the lab. It writes code and drafts text in sessions and routines.
- A paid API call is out of scope. Proposing one triggers the AI gateway ADR (ADR 0002, "Revisit when").

### Publishing (spec §5.4, P8)

- The lab repo has no site. The blog page on lab-to-prod is the canonical URL for each lesson.
- Until the lab-to-prod trial ends on 2026-12-13, a lesson goes out as a normal post.
- In W51 a lab-to-prod PR adds a "Lab lessons" section with static self-check quizzes.
- Everything public goes through the lab-to-prod weekly PR. Submitting a CCAI paper needs Nghiep's yes.

### Capacity and routines

- `lab` WIP goes from 1 to 2 (process-sim-lab and this repo), as a stated exception to spec §2.2.
  `lab` hours stay at 3 h/week. The change is a separate ops PR.
- Who pays the hours: build work runs in routines and sessions (Claude plan limits, not Nghiep's hours). Nghiep's
  30 min/week of review and 1 h/week GPU session come from `lab`, leaving 1.5 h/week for process-sim-lab. Reading a
  lesson before it is published counts as `content`. Nothing comes from `learn`.
- A cloud routine runs on Tuesday and Friday at 07:00. It does one small item, opens one PR, uses cassettes only and
  never merges. Its PRs wait for the Sunday review. (Withdrawn by ADR 0005 §5; routine PRs merge as in ADR 0006 §3.)

### Relation to `tmpl-project` (ecosys#7)

- The lab is built by hand in W48 with the file set planned for `tmpl-project`. This is a stated exception to spec
  §5.5 (new projects start from `tmpl-project`), because the template does not exist yet.
- Only the generic repo base goes back to `tmpl-project`, after the project 2 retro. The AI-specific layer (gates,
  eval plan, card, risk notes, registers) stays in the lab, where it is used.
- This narrows the 2026-11-16 decision that folded the whole kit into `tmpl-project`.

### Phases (ISO weeks; 2026-W48 starts Monday 2026-11-23; 2026 has 53 weeks)

| Phase | Weeks | Work | Done when |
|---|---|---|---|
| P0 frame | 2026-W48 | this ADR Accepted; ops capacity PR; research moved to the vault; repo created after a yes; skeleton, licences, `NOTICE`, CI; `core/` client, cassettes, token limiter; `check_manifest`; `_template`; `method.md`; `sources.yaml`; `limits.yaml` | CI green; one Ollama call recorded and replayed in CI |
| P1 | 2026-W48–W51 | projects 2 and 4; `check_gates` and quiz lint with project 2; "Lab lessons" blog PR in W51 | eval numbers against thresholds; 2 lessons and quizzes live |
| Checkpoint | 2026-W52 review | pace and hours; back-port the repo base to `tmpl-project` | on pace → continue; behind → a lesson for every second project, or Hold |
| P2 | 2026-W52–2027-W05 | projects 3 and 6; about 3 weeks of holiday slack | as P1 |
| P3 | 2027-W06–W13 | projects 1, 7, 8 and 5 | as P1 |
| P4 | 2027-W14–W19 | projects 9, 10 and 11; the best write-up becomes a CCAI workshop draft | as P1, and a draft ready for Nghiep |
| Season 2 decision | 2027-W19 review (or 2026-W52 if on pace) | candidates 13 and 14, about 2 weeks each; both would end about 2027-W23 | Go, Hold or archive, recorded in an ADR note |

### Cost

$0: GitHub public repo and Actions; lab-to-prod's existing Pages site; Ollama with local models; Docker with
Postgres + pgvector and Neo4j Community; Groq and Gemini free tiers *(verify)*; the existing Claude subscription for authoring and routines.
No Neo4j Aura, Vercel, domain, cloud account or paid API.

## Options considered

- **12 repos, one per project:** rejected. Twelve CIs and rulesets, and it breaks the WIP limits.
- **Curriculum-first repo** with a separate course tree: rejected for v0. It adds a large P0 before any project ships.
  Its learning thread is kept as objectives in each project's front matter.
- **Lab-first, lean method, one lesson per project:** chosen.
- **A full lifecycle kit in `tmpl-project` before any project uses it:** rejected.
- **A separate course repo or course site** (reader site, sign-in, badges): deferred behind its own ADR (spec §5.4, P5).
- **Lesson licence CC BY-SA:** rejected. The blog would need a licence exception.
- **Build `tmpl-project` first:** rejected for W48 because of the dates. A back-port after project 2 is used instead.
- **Add projects until every topic is covered:** rejected. Topics that need a real build beyond season 1 are season 2
  candidates; the rest fold into existing projects, `core/` or the template.
- **Add candidates 13 and 14 to season 1:** rejected. P3 and P4 have no slack, so the plan would slip before the W52
  check. Season 2 is decided on real pace data instead.

## Consequences

- One repo shows code, evals and lessons together. Readers can fork it and run it in replay mode without a key.
- The method is tested on 11 real projects before the generic part moves into `tmpl-project`.
- CC BY 4.0 keeps one licence across the lab text and the blog. Share-alike sources can only be linked.
- Lessons add about 2 h per project, about 22 h over P1–P4. This is the main capacity risk, checked at W52.
- `lab` holds two active repos. ecosys#7 stays open longer.
- Season 1 has no live service, so there is no service-level objective or on-call. Operating a live LLM system is
  season 2 candidate 13. Infrastructure as code stays out of scope.
- ADR 0002 and spec §7 reserved "ADR 0004" for the AI gateway. This change points them to the next free ADR number.

## Revisit when

- At the W52 review the lab is more than one project behind, or a lesson takes more than 2 h twice.
- A free-tier term or limit changes, for example training on inputs, or a tier is dropped.
- A paid API call is proposed: write the AI gateway ADR.
- A reader site, Vietnamese lessons or a second publishing surface is wanted.
- A reviewer-privacy blocker traces back to method text.
- At the W52 review, if the lab is on pace: decide whether season 2 (13 and 14) may start right after project 11.
- After project 11 (2027-W19 review), or by June 2027: run season 2, archive the repo, or plan a v2. Record why each
  open coverage row stays open.

## Decisions by Nghiep (2026-11-16)

1. Name and scope: `ai-engineering-lab`, 11 build projects plus project 12 as a stream; candidates 13 and 14 as
   season 2, decided on pace data.
2. Rule for the method: spec §10.3 "ways of working only", applied through the clean room above.
3. Text licence: CC BY 4.0, with share-alike sources linked only.
4. `tmpl-project`: build the lab by hand in W48 and back-port the generic base after project 2.
5. Capacity: `lab` WIP 1 → 2 with one active build project at a time.
6. Blog: a "Lab lessons" section in W51, normal posts until then.

## Follow-ups

| Item | Repo | When |
|---|---|---|
| Raise `lab` WIP to 2 and record these decisions in the private plan | ops | 2026-W47 |
| Move the research originals to the vault (the vault needs CI first) | vault | 2026-W48, before `method.md` |
| Create the repo (Nghiep's yes, ADR 0003); add it to `repos.yaml` and the workspace file | ecosys | 2026-W48 |
| Skeleton, licences, `NOTICE`, CI; `core/` client with cassettes and token limiter; `check_manifest`; `_template`; `method.md`; `sources.yaml`; `limits.yaml`; `inventory.yaml` | ai-engineering-lab | 2026-W48 |
| Free-tier API keys, created by Nghiep after a yes | none (outside repos) | 2026-W48 |
| Recheck lab data sources (`data/manifest.yaml`) whose licence is unverified | ai-engineering-lab | before their data is committed |
| Tuesday and Friday 07:00 routine, recorded in `automations.md` | ops | after P0 |
| "Lab lessons" section with static quizzes | lab-to-prod | 2026-W51 |
| Narrow ecosys#7 to the generic base and back-port it | ecosys | 2026-W52 |
