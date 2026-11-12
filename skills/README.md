# Skills

Personal skills for this workspace. Claude Code reads them through the `.claude/skills -> ../skills` symlink. Kiro
reads the same files through a steering file. There is one copy: this folder.

This folder is in the **public** `ecosys` repo. Everything here follows the public-safe rule (spec §10.2) and the
day-job boundary (spec §10.3).

## Index

| Skill | Use it for | Phase |
|---|---|---|
| [`core`](core/SKILL.md) | hard rules and their guards, roles, sources of truth, which skill when, issue and lane brief templates, language | P0 |
| [`session`](session/SKILL.md) | session start and end rituals, live checklist, pending lessons, session log and memory block | P0 |
| [`ship`](ship/SKILL.md) | branch → PR → checks → `tools/ship/merge` → verify → Done with evidence; commit format | P0 |
| [`lessons`](lessons/SKILL.md) | lesson format (Rule, Why, Seen, Guard), where to write, promotion to a guard; log in [`lessons/lessons.md`](lessons/lessons.md) | P0 |
| [`jobs`](jobs/SKILL.md) | job pipeline stages and transitions, 30-day rule, form-filling rules, `tools/jobs/check`, sources | P0 |
| [`weekly-review`](weekly-review/SKILL.md) | Sunday review, capacity and WIP check, review template | P0 |
| `learn` | deadlines, study tracks, coaching | **P1, not written** |
| `content` | pointer to the lab-to-prod skills and approval flow | **P1, not written** |
| `cv` | profile facts → Typst CV variant, number-to-fact check | **P1, not written** |

Until a P1 skill exists, use the spec section it will cover (§5.3 learn, §5.4 content, §5.1 cv) and say so.

## Layout

```
skills/<name>/SKILL.md          ← ≤ ~150 lines: what to do, in order
skills/<name>/references/*.md   ← details, loaded only when the SKILL.md points to them
skills/lessons/lessons.md       ← public-safe lesson log
```

## Rules for writing a skill

1. **Frontmatter:** `name` (same as the folder) and `description`. The description names the triggers (words Nghiep
   says, situations) **and** what the skill does not cover, with the skill that does.
2. **Size:** `SKILL.md` stays at or under ~150 lines. Move detail to `references/` (progressive disclosure). A reference
   file is linked from `SKILL.md` with one line that says when to read it.
3. **No live numbers.** No counts, versions, open items or dates that change. Those come from the live source
   (`just ws-status`, the board, `private/ops`) at the time of use.
4. **Point, don't copy.** A fact that has a home elsewhere (spec, `CONTEXT.md`, a repo's `CLAUDE.md`, a YAML file)
   is linked, not repeated. Precedence when they disagree: repo > canonical doc > memory > skill.
5. **Delete what is replaced.** Do not mark old text "outdated" and keep it. History lives in git.
6. **A rule that a guard enforces stays as one line plus the guard name.** The guard is the rule; the skill only
   explains it. A rule with no guard is a SHOULD (spec §0), unless it is a ritual step with an owner.
7. **English, short sentences, active voice.** Private notes, session logs and memory may be Vietnamese; skills are not.
8. **Public-safe.** No employer, client, recruiter or company names from the job search, no salaries, no contact
   details, no claude.ai links, no account ids, no day-job issue keys or examples. Examples use synthetic names
   (Example Co, Acme). Anything personal goes to `private/ops/` and the skill points there.

## Maintenance

- Change a skill in a PR to `ecosys`, like any other change (`ship`). The PR body says which skills changed.
- Add a new rule to the right section. Do not append an "additions" block at the end.
- A lesson that repeats becomes a guard (`lessons` §4). When the guard is merged, shorten the skill text to one line
  that names the guard.
- New skill: add it to the index above and to the "Which skill when" table in `core`.
- After a skill changes, the next Claude Code session reads the new version from the repo. For Claude chat and
  Desktop, which do not read the repo, run `just skills-zip` (all skills, or name some) and upload the changed
  `dist/skills/<name>.zip` in Settings → Capabilities → Skills, replacing the old version. The zips are build output
  and are not committed; `tools/skills/pack` checks the frontmatter (name = folder, description ≤ 1024 characters)
  before writing anything.
- Review the whole set at the first weekly review of each month: line counts, dead links, rules now covered by a
  guard, P1 skills that became due.
