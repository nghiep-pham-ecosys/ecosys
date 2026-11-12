# Language and style

## Which language where (spec Appendix B)

| Text | Language |
|---|---|
| Code, comments, commits, PRs, issues, ADRs, runbooks, technical docs | English |
| Chat with Nghiep, session logs, memory, private notes | Vietnamese |
| Posts | per the lab-to-prod rules |

## Style

- Short sentences. Active voice. One idea per sentence.
- Numbers with units (`3 h`, `14 days`, `2,000 min/month`).
- No claim without a source. A live status is checked or labelled *unverified*.
- A free-tier number not checked today is marked *(verify)*.
- Say what to do, not what to avoid, when both work.

## Commits and PRs

- Subject: `type: description`, lower case, imperative, no trailing period.
  Types: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `ci`.
- Body: one line `Refs <repo>#<n>` (several refs are comma-separated).
- Never `Fixes`, `Closes` or `Resolves`: they close the issue before Done is verified.
- PR title follows the same format. The `pr-title` check enforces it.

Example:

```
fix: skip dirty repos in ws-sync

Refs ecosys#7
```

## Code

- Tools: Python 3.12, stdlib + PyYAML only. Executables have no extension and start with `#!/usr/bin/env python3`.
- Importable logic goes in a sibling module (for example `tools/ws/_wslib.py`).
- Tests: stdlib `unittest`, files `test_*.py`, synthetic data only (Example Co, Acme).
