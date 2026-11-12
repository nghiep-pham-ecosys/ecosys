---
name: session
description: Start and end rituals for a working session in the nghiep-pham-ecosys workspace. At start it reads memory, the last session log and the board, checks reality read-only (ws-status, red runs, open PRs, deadlines within 48 h), reports drift, reads lessons and proposes 3 to 5 items within budget. During the session it keeps the live checklist and pending lessons in .tmp-session. At the end it settles board items, moves lessons, batches external drafts for approval, writes the session log and memory block, and leaves every repo clean. Use it when Nghiep says "start a session", "new session", "wrap up", "end the session", "close out", or when a session starts without context. It does not cover merging and Done (ship), the lesson format (lessons) or the Sunday plan (weekly-review).
---

# session

Precedence when sources disagree: repo > canonical doc > memory > skill. Report drift; never resolve it silently.
Chat with Nghiep in Vietnamese. Files in public repos stay in English.

## Start (spec §9.2)

1. **Read what was recorded.**
   - The newest block of `private/ops/memory.md` (only the newest; older blocks only when history is needed).
   - The newest session log in `private/ops/sessions/`.
   - The board view "This week" and every item `In progress`.
   - `.tmp-session/lessons-pending.md` and `.tmp-session/checklist.md` if a previous session left them.
2. **Check reality (read-only).** Every status line you report comes from this step, with the command.
   - `just ws-status`: branch, dirty count, ahead/behind, open PRs per repo.
   - Red runs: `gh run list -R <org>/<repo> --status failure --limit 5` for repos with recent activity.
   - Deadlines within 48 h: `private/ops/learn/deadlines.yaml`; job follow-ups and interviews: `just jobs-check`.
   - Today's calendar: the Notion Calendar connector (`notion-calendar-list-events`, today 00:00–24:00,
     Asia/Ho_Chi_Minh) reads Nghiep's personal Google Calendar. Report the fixed blocks so the plan fits around them;
     never copy event details into a public file. No connector in this client → say so and skip.
   - Digest "red" items, once the digest exists **[P1]**.
3. **Report drift** between the records and reality before doing anything else: a PR that memory calls open but is
   merged, a repo on a branch nobody named, a deadline that moved.
4. **Read lessons** for the areas about to be touched (`lessons` §1).
5. **Propose 3–5 items within the area budgets** (`private/ops/plan/capacity.yaml`, WIP limits). For each: what, why,
   how it will be verified. Unfinished `In progress` items come before new ones: close with evidence, finish, or
   record what blocks them. Items with a hard deadline come first.
6. **After Nghiep agrees:** create `.tmp-session/checklist.md` and start.

Output of the start: a short block in Vietnamese with state (3–5 lines, each with its source), drift, and the
proposed items.

## During the session

- **Live checklist** `.tmp-session/checklist.md`. Update it after every finished step; it is the source for the log.

  ```markdown
  # Session <YYYY-MM-DD> <slug>
  ## Items
  - [x] <repo>#<n> <title> — evidence: <link>
  - [~] <item> — running: <what>
  - [!] <item> — blocked: <by what>
  - [ ] <item>
  ## Constraints
  - <budget left, permission windows, things not to touch>
  ## Nghiep's decisions
  - <only what Nghiep said, with the time>
  ```

  Tell Nghiep it opens with Markdown Preview (Ctrl+Shift+V).
- **Pending lessons:** the moment a root cause is found, add one entry in the `lessons` format to
  `.tmp-session/lessons-pending.md`. Lanes return lessons in their JSON; the orchestrator writes them here.
- **Each item, when it starts:** 3–6 lines in Vietnamese to Nghiep: problem / what will be done / who does it / how it
  will be checked.
- **Lanes:** briefed with the template in `core` (`references/issue-and-brief.md`). One worktree per lane under
  `.tmp-session/wt/<session>-<lane>`. Lanes never push, merge or run workflows (`ship-guard`).
- **Shipping:** only the orchestrator pushes, opens PRs and merges, following `ship`.
- **Scripts that live longer than one turn** go to `.tmp-session/<session>/`, not to the agent scratchpad.
- **External drafts** (post text, e-mails, application answers) are collected in `.tmp-session/drafts.md` for one
  approval at the end, unless Nghiep asks for one now.
- **Keep going.** While there is work the session can do itself (an item in progress, a found side issue, a verify
  step), do it. Close only when Nghiep says so or everything left is blocked, with the blocker named.

## End (spec §9.3)

Order matters: **settle → check reality → lessons → drafts → write → clean → report**. The log is written last, from
checked facts, not from what the session remembers.

1. **Settle board items.** Verified → `Done` with an `Evidence` link (`ship` §5). Partly done → stays `In progress`
   with what is left and what blocks it. Dropped → `Dropped` with a reason.
2. **Check reality.** `just ws-status`, last run on each touched repo's `main`, open PRs. Every number in the log and
   memory comes from this step. A mismatch with what the session believed is fixed or written down as drift.
3. **Lessons.** Move `.tmp-session/lessons-pending.md` into `skills/lessons/lessons.md` (public-safe) or
   `private/ops/lessons.md` (personal). A repeat becomes a guard (`lessons` §4).
4. **Drafts.** Show every external draft verbatim, once, for approval. Nothing goes out without it. Record in the log
   what was approved and sent, and what is still waiting.
5. **Write** the session log `private/ops/sessions/YYYY-MM-DD-<slug>.md` and **prepend** the memory block to
   `private/ops/memory.md`. Formats: [`references/log-and-memory.md`](references/log-and-memory.md).
6. **Clean.** Every repo on a clean default branch; worktrees removed (`git worktree remove`); the session's
   `.tmp-session` files deleted after their content is in the log. Commit `ops` changes through the normal flow.
7. **Mirror to Notion** (only when the Notion connector is present; otherwise say so and skip). Ids and what each
   target holds: `private/ops/notion.yaml`. From the facts checked in step 2: replace the Dashboard callout on the
   home page, update the Projects rows (Status, Focus, Open PRs, Last synced), and prepend one line to the inbox page
   (`date · Claude Code · summary`). Read the inbox first: a line from Claude Chat is input for the next session.
   Notion is a mirror: totals only for jobs, never company names, pay, contacts or anything not in a public-safe or
   `ops` summary.
8. **Report** three lines to Nghiep, in Vietnamese: done / left and why / where the next session starts.

## Maintenance

Follow `skills/README.md`. A ritual step that gets a tool or a check shrinks to one line naming it.
