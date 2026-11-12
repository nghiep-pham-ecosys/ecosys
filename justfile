# Workspace commands (spec section 4.3). Run `just` to list them.
set shell := ["bash", "-cu"]
set positional-arguments := true
# Shebang recipes write their script here instead of the system temp dir.
# just does not create this folder, so every shebang recipe depends on the
# private `_tempdir` recipe below (a plain recipe, which needs no temp file).
set tempdir := ".tmp-session/just"

# The tools need PyYAML. mise's python may not have it, so pick the first
# python3 on PATH that can import yaml, then fall back to the system one.
python := `for p in python3 /usr/bin/python3; do if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import yaml' 2>/dev/null; then command -v "$p"; exit 0; fi; done; echo python3`

test_dirs := ".claude/hooks/tests tools/ws/tests tools/ship/tests tools/jobs/tests"

# List the recipes
default:
    @just --list --unsorted

# Clone missing repos, fast-forward clean ones (args: --dry-run, --only NAME)
ws-sync *args:
    @{{python}} tools/ws/sync "$@"

# One line per repo: branch, dirty, ahead/behind, open PRs (args: --no-gh, --strict)
ws-status *args:
    @{{python}} tools/ws/status "$@"

# Write the gitignored local VS Code workspace: public folders plus the private-manifest repos
ws-workspace *args:
    @{{python}} tools/ws/workspace "$@"

# Job pipeline checks on the private ops data, plus skipped.yaml when present (args: --today YYYY-MM-DD, --close-after-days N)
jobs-check *args:
    @skipped=(); if [ -f private/ops/jobs/skipped.yaml ]; then skipped=(--skipped private/ops/jobs/skipped.yaml); fi; {{python}} tools/jobs/check --data private/ops/jobs/applications.yaml "${skipped[@]}" "$@"

# Daily digest
digest:
    @echo "[P1] not built yet"

# Weekly review draft
review:
    @echo "[P1] not built yet"

# Unit tests of hooks and tools (a missing test folder fails, as in CI)
test: _tempdir
    #!/usr/bin/env bash
    set -uo pipefail
    failed=()
    for d in {{test_dirs}}; do
      if [ ! -d "$d" ]; then echo "test: $d not found" >&2; failed+=("$d (missing)"); continue; fi
      echo "test: $d"
      "{{python}}" -m unittest discover -s "$d" -p 'test_*.py' || failed+=("$d")
    done
    if [ ${#failed[@]} -gt 0 ]; then echo "test: FAILED in ${failed[*]}" >&2; exit 1; fi
    echo "test: ok"

# Fail if anything under the child-repo or scratch folders is tracked
tracked-children: _tempdir
    #!/usr/bin/env bash
    set -euo pipefail
    out="$(git ls-files -- meta private projects .tmp-session import skill docs/BOOTSTRAP-PROMPT.md)"
    if [ -n "$out" ]; then
      echo "tracked-children: these paths must not be tracked in the root repo:" >&2
      echo "$out" >&2
      exit 1
    fi
    echo "tracked-children: ok"

# Lint GitHub workflows (skipped when there are none)
actionlint: _tempdir
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -d .github/workflows ]; then actionlint; echo "actionlint: ok"; else echo "actionlint: no .github/workflows, skipped"; fi

# Secret scan of the git history
gitleaks:
    gitleaks git --redact --no-banner -v .

# Denylist scan of tracked files (prints file:line only; skipped when the local denylist is absent)
denylist:
    @{{python}} tools/ws/denylist-scan

# Before a commit: gitleaks and the denylist on staged content only
precommit-scan:
    gitleaks git --pre-commit --staged --redact --no-banner .
    @{{python}} tools/ws/denylist-scan --staged

# Everything CI runs
ci: test tracked-children actionlint gitleaks denylist

# Create the folder named by `set tempdir` (plain recipe: needs no temp file)
[private]
_tempdir:
    @mkdir -p .tmp-session/just
