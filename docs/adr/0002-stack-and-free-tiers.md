# ADR 0002: Stack and free tiers

- **Status:** Accepted
- **Date:** 2026-11-12

## Context

The workspace must cost nothing beyond existing subscriptions (P5). Free-tier limits change, so every number is either checked on a stated date or marked *(verify)*.

## Decision

| Need | Choice |
|---|---|
| Code, CI, tracker | GitHub Free org, Actions, Projects |
| LLM work | Claude subscription only (Claude Code, Claude app, scheduled tasks). No paid API. |
| Blog | lab-to-prod's own choice (GitHub Pages or Cloudflare Pages) |
| Notifications | Telegram bot, one channel `[P1]` |
| CV | Typst, local only `[P1]` |
| Secrets in files | sops + age `[P1]` |
| Secret scan | gitleaks (CI + pre-push) and GitHub push protection on public repos |
| Toolchain | mise, versions pinned in `.mise.toml` |
| Editors and agents | VS Code + Claude Code, Claude Desktop, Kiro optional |

### Verified on 2026-11-12

Checked with `gh api` GET calls or confirmed by Nghiep in the GitHub UI.

| Fact | Value | How checked |
|---|---|---|
| Org plan | Free | `GET orgs/nghiep-pham-ecosys` → `plan.name = free` |
| 2FA required | yes | `GET orgs/...` → `two_factor_requirement_enabled = true` |
| Base member permission | none | `GET orgs/...` → `default_repository_permission = none` |
| Budgets | $0 for Actions, Packages, Codespaces and Git LFS | set by Nghiep in the billing UI |
| Actions enabled for | all repos | `GET orgs/.../actions/permissions` |
| Allowed actions | selected: GitHub-owned + `astral-sh/setup-uv@*`, `docker/build-push-action@*`, `docker/setup-buildx-action@*`, `jdx/mise-action@*`; verified creators not allowed | `GET .../actions/permissions/selected-actions` |
| Default workflow token | read-only | `GET .../actions/permissions/workflow` |
| Actions can approve PRs | no | same call |
| SHA pinning required (org setting) | off | `GET .../actions/permissions`; CI pins by full SHA anyway |

### Not yet verified

| Item | Assumed value |
|---|---|
| Actions minutes on private repos (Free) | about 2,000 min/month *(verify)* |
| Packages storage (Free) | about 500 MB *(verify)* |
| Rulesets / branch protection on private repos (Free) | not available *(verify)* |
| GitHub Pages from private repos (Free) | not available *(verify)* |
| Telegram bot API | free *(verify)* |
| Cloudflare Workers cron (trigger only) | free tier *(verify)* |

When a value is checked, move its row to the verified table with the date.

## Consequences

- Monthly cost is $0. A $0 budget makes a paid overage fail closed instead of billing.
- Workflows can use only GitHub-owned actions and the four listed patterns. A new third-party action needs an org settings change (runbook `org-setup.md`).
- Private repos may lack server-side merge rules. They rely on a local pre-push hook and `tools/ship/merge`.
- Plan limits on Claude are the real constraint; heavy work is batched into planned sessions.

## Revisit when

- The first paid API call is proposed (then ADR 0004: AI gateway with ledger and caps).
- A free-tier limit is hit, or a *(verify)* value turns out wrong.
- Something must run more often than hourly (Cloudflare Workers cron).
