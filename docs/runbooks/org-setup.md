# Runbook: org setup

One-time settings for the org `nghiep-pham-ecosys` (spec §4.6). `[UI]` items are done by Nghiep in the GitHub web UI. Agents do not create orgs, change billing or create tokens.

## Prerequisites

- `gh` signed in as the org owner with scopes `admin:org`, `repo`, `workflow`, `project`.
  If a scope is missing, Nghiep runs: `gh auth refresh -s admin:org,project`
- Check: `gh auth status`

## Checklist

| # | Item | Status |
|---|---|---|
| 1 | `[UI]` Create the org on the Free plan | done 2026-11-12 |
| 2 | `[UI]` Require 2FA for members | done 2026-11-12 |
| 3 | `[UI]` Base member permission: none | done 2026-11-12 |
| 4 | `[UI]` Budgets $0 for Actions, Packages, Codespaces and Git LFS | done 2026-11-12 |
| 5 | Actions: allow GitHub-owned and listed actions only | done 2026-11-12 (API) |
| 6 | Actions: default token read-only; Actions cannot approve PRs | done 2026-11-12 (API) |
| 7 | Public repos: secret scanning, push protection, Dependabot alerts on | pending |
| 8 | Ruleset on `main` for public repos: PR required, squash only, required checks `ci-result` + `pr-title`, no force push, no deletion | pending (after CI exists) |
| 9 | Private repos: local pre-push hook + merge tool (no rulesets on Free *(verify)*) | pending |
| 10 | `[UI]` Org Project "Ecosys board" (private) with fields from spec §6 | pending |

## Items 5 and 6: Actions settings (API)

These calls set the state verified on 2026-11-12. Each is one line.

```sh
gh api -X PUT orgs/nghiep-pham-ecosys/actions/permissions -f enabled_repositories=all -f allowed_actions=selected
gh api -X PUT orgs/nghiep-pham-ecosys/actions/permissions/selected-actions -F github_owned_allowed=true -F verified_allowed=false -f 'patterns_allowed[]=astral-sh/setup-uv@*' -f 'patterns_allowed[]=docker/build-push-action@*' -f 'patterns_allowed[]=docker/setup-buildx-action@*' -f 'patterns_allowed[]=jdx/mise-action@*'
gh api -X PUT orgs/nghiep-pham-ecosys/actions/permissions/workflow -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false
```

Notes:

- `allowed_actions=selected` must be set before the `selected-actions` call is accepted.
- `-F` sends booleans as JSON booleans. `-f` sends strings.
- The `selected-actions` PUT replaces the whole list. To add a pattern, send the full list again.

### Verify

```sh
gh api orgs/nghiep-pham-ecosys/actions/permissions
gh api orgs/nghiep-pham-ecosys/actions/permissions/selected-actions
gh api orgs/nghiep-pham-ecosys/actions/permissions/workflow
gh api orgs/nghiep-pham-ecosys --jq '{plan:.plan.name,two_factor_requirement_enabled,default_repository_permission}'
```

Result on 2026-11-12:

```json
{"enabled_repositories":"all","allowed_actions":"selected","sha_pinning_required":false}
{"github_owned_allowed":true,"verified_allowed":false,"patterns_allowed":["astral-sh/setup-uv@*","docker/build-push-action@*","docker/setup-buildx-action@*","jdx/mise-action@*"]}
{"default_workflow_permissions":"read","can_approve_pull_request_reviews":false}
{"plan":"free","two_factor_requirement_enabled":true,"default_repository_permission":"none"}
```

## Adding a third-party action later

1. Check the action's repo: maintained, pinned releases, no broad token needs.
2. Add its pattern with the full-list PUT above. Org settings changes need Nghiep's yes (ADR 0003).
3. Pin it by full commit SHA in the workflow.
4. Update the allowed list in ADR 0002 with the date.

## Items still to do

- **7:** per public repo, after it exists in the org. Use the repo Settings → Code security page, or `gh api -X PATCH repos/nghiep-pham-ecosys/<repo>` with `security_and_analysis`. Record the calls here when done.
- **8:** after `ci-result` and `pr-title` have run once on the repo (a required check must exist by name). Apply through the API, then show the GET.
- **10:** create with `gh project create --owner nghiep-pham-ecosys`; anything the CLI cannot do is a `[UI]` step. Record the click path here.
