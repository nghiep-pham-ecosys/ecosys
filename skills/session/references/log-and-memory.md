# Session log and memory block

Read this at the end of a session (`session` End step 5). Both files are in the private `ops` repo, so their
content may be in Vietnamese. Headings stay as below so tools and later sessions can find them.

## Session log

Path: `private/ops/sessions/YYYY-MM-DD-<slug>.md`. `<slug>` is 2–4 lowercase words joined by hyphens. Two sessions on
the same day get different slugs. Add one line to `private/ops/sessions/README.md` (date, slug, title).

```markdown
# <YYYY-MM-DD> <title>

Agent: <Claude Code | Claude app | Kiro> · Where: <machine / editor> · Duration: <h>

## Goal
<what Nghiep asked for, one or two lines>

## Agreed items
- <repo>#<n> <title> — <result: done | in progress | blocked | dropped>

## Done (with evidence)
- <item> — <PR link, run link, URL, file path>

## Left and why
- <item> — <what is left, what blocks it>

## Nghiep's decisions
- <only decisions Nghiep stated, not the agent's proposals>

## State at end (checked)
- <repo>: <branch>, clean | dirty, open PRs, last run on main <green|red> (command used)

## Drafts
- <draft>: approved and sent | approved, not sent (why) | waiting

## Lessons
- <n> new, <n> became guards, where they were written

## Next session starts with
1. <first thing>
2. <second thing>
```

## Memory block

Prepend to `private/ops/memory.md`, newest first. **Prepend only.** Agents never trim, move or delete older blocks;
Nghiep archives them by hand.

```markdown
## <YYYY-MM-DD> <slug> (<agent> — <where>): <short title>
**Nghiep's decisions** — only what Nghiep said
**Results** — items, PRs, evidence
**State at end** — from the end-of-session check, with the date and time
**Next session starts with** — ordered list
**Notes** — only new facts that are not yet in a skill or a canonical doc
```

Rules:

- Every state line comes from the end-of-session check (`session` End step 2), never from memory.
- A note that repeats in two or more blocks moves into the right skill or doc, then leaves the memory block.
- No secrets, tokens or credentials. Names of people and companies are allowed here (private repo), but never copied
  from here into a public file.
