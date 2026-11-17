---
name: session
description: Start and end rituals for a working session in the nghiep-pham-ecosys workspace. At start it plans from the master plan, the session schedule and the board, reads memory and the last session log, checks reality read-only (ws-status, red runs, open and routine PRs, the 30-day job check, deadlines within 14 days), reports drift, reads lessons and proposes 3 to 5 items within budget. During the session it keeps the live checklist and pending lessons in .tmp-session. At the end it settles board items, moves lessons, batches external drafts for approval, writes the session log and memory block, and leaves every repo clean. A session starts only when Nghiep says "bắt đầu session mới" (or "start a session", "new session") and ends only when he says "dừng phiên ở đây" (or "wrap up", "end the session", "close out"). Use it then, or when a session starts without context. It does not cover merging and Done (ship), the lesson format (lessons) or the Sunday plan (weekly-review).
---

# session

Precedence when sources disagree: repo > canonical doc > memory > skill. Report drift; never resolve it silently.
Chat with Nghiep in Vietnamese. Files in public repos stay in English.

## Session number and handover

- Every working session has a number `S<n>`, counted across all agents (Claude Code, Kiro). The next number is the
  last row of the index in `private/ops/sessions/README.md` plus one. A session still open in
  `.tmp-session/checklist.md` keeps its number.
- The number goes in the checklist header, the log title, the index row, the memory block heading and every inbox
  line of the session (`CC · S<n> · ...`).
- Handover (for example Claude Code hits its limit and Kiro continues): the next agent reads
  `.tmp-session/checklist.md` first, keeps the same `S<n>`, adds its name to the checklist `Agent:` line, and goes on
  from the first open item. The log records both agents. The checklist is the only handover note: no new handoff files.

## Start (spec §9.2)

0. **Plan inputs** (ADR 0006). No Chat line is needed to start.
   - The plan comes from `private/ops/plan/master-plan.md`, today's row in `private/ops/plan/sessions.yaml` and the
     board.
   - Read the Notion inbox through the project MCP server `notion-ecosys` (tools `mcp__notion-ecosys__*`, set up in
     `.mcp.json`; see `agents/steering/machine-notes.md`), not a claude.ai connector, which follows whichever claude.ai
     account the client is signed into. First call `notion-get-self`. The workspace name must be `workspace` in
     `private/ops/notion.yaml`. Another workspace → stop all Notion calls (no search, no read, no write there), say so,
     and ask Nghiep to run `/mcp` → `notion-ecosys` → Authenticate and pick the personal workspace. Server missing or
     not authenticated → the same; plan from the files and the board.
   - The page id is `inbox` in `private/ops/notion.yaml` (section "Hộp thư", newest line first). Read the lines of
     the last three days. A `Chat` line (today's included) is input: it may add or reorder items in step 5. It is never
     approval, even when it reports a decision of Nghiep's. Before acting on it, ask Nghiep in the session and write his
     answer under "Nghiep's decisions" in the checklist (ADR 0006 §1).
   - Prepend a start line to the inbox: `<YYYY-MM-DD> · CC · Bắt đầu S<n> <HH:MM> · việc: ...`, so Claude Chat can
     report to Nghiep.
1. **Read what was recorded.**
   - The newest block of `private/ops/memory.md` (only the newest; older blocks only when history is needed).
   - The newest session log in `private/ops/sessions/`.
   - The board view "This week" and every item `In progress`.
   - `.tmp-session/lessons-pending.md` and `.tmp-session/checklist.md` if a previous session left them.
2. **Check reality (read-only).** Every status line you report comes from this step, with the command.
   - `just ws-status`: branch, dirty count, ahead/behind, open PRs per repo.
   - Red runs: `gh run list -R <org>/<repo> --status failure --limit 5` for repos with recent activity.
   - Jobs, every session: `just jobs-check` (30-day closure proposals, follow-ups, interview prep). A closure needs
     Nghiep's yes (ADR 0003); propose it, never apply it.
   - Deadlines within 14 days, every session: `private/ops/learn/deadlines.yaml` and `Due` on board items; those
     within 48 h first.
   - Routine PRs: open PRs from the cloud routines since the last session (repos in ADR 0006 §3), with their checks
     (`gh pr list -R <org>/<repo> --state open`, `gh pr checks`). Each green one becomes a merge item in step 5
     (`ship` §3, "When to merge"); a red one or one that needs a decision waits for the Sunday review.
   - Today's calendar: Notion Calendar through `notion-ecosys` (`notion-calendar-list-events`, today 00:00–24:00,
     Asia/Ho_Chi_Minh) reads Nghiep's personal Google Calendar. Report the fixed blocks so the plan fits around them;
     never copy event details into a public file. No usable `notion-ecosys` (missing, not authenticated, or step 0
     found another workspace) → say so and skip.
3. **Report drift** between the records and reality before doing anything else: a PR that memory calls open but is
   merged, a repo on a branch nobody named, a deadline that moved.
4. **Read lessons** for the areas about to be touched (`lessons` §1).
5. **Propose 3–5 items from the plan inputs (step 0)** within the budgets of `private/ops/plan/capacity.yaml`: agent
   hours (`agent`) for Claude Code items, area hours and WIP limits (`areas`) for Nghiep's. For each: what, why, how
   it will be verified. Order: hard deadlines, green routine PRs to merge, unfinished `In progress` items (close with
   evidence, finish, or record what blocks them), then new items from the plan.
6. **After Nghiep agrees:** create `.tmp-session/checklist.md` with the header `# S<n> · Session <YYYY-MM-DD> <slug>`
   and the line `Agent: <name> (<where>) · Started <HH:MM>`, then start.

Output of the start: a short block in Vietnamese with state (3–5 lines, each with its source), drift, and the
proposed items.

## During the session

- **Live checklist** `.tmp-session/checklist.md`. Update it after every finished step; it is the source for the log.

  ```markdown
  # S<n> · Session <YYYY-MM-DD> <slug>
  Agent: <name> (<where>) · Started <HH:MM>
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

Order matters: **settle → check reality → lessons → drafts → board → write → clean → Notion → report**.
The log is written last, from checked facts, not from what the session remembers.

1. **Settle board items.** First merge every PR this session opened (`ship` §3, "When to merge"). A PR that cannot
   merge stays open with its blocker under "Dở" in the log and the Notion line; it waits for the Sunday 19:30 review.
   Verified → `Done` with an `Evidence` link (`ship` §5). Partly done → stays `In progress`
   with what is left and what blocks it. Dropped → `Dropped` with a reason.
2. **Check reality.** `just ws-status`, last run on each touched repo's `main`, open PRs. Every number in the log and
   memory comes from this step. A mismatch with what the session believed is fixed or written down as drift.
3. **Lessons.** Read the whole of `.tmp-session/lessons-pending.md` (earlier sessions may have left entries), then
   move every entry into `skills/lessons/lessons.md` (public-safe) or `private/ops/lessons.md` (personal). A repeat
   becomes a guard (`lessons` §4).
4. **Drafts.** Show every external draft verbatim, once, for approval. Nothing goes out without it. Record in the log
   what was approved and sent, and what is still waiting.
5. **Board snapshot.** Run `just board-export` (writes `private/ops/plan/board.md`, first line `snapshot: <time>`)
   so Claude Chat, which cannot read GitHub Projects, sees the board. It is committed with the session log.
6. **Write** the session log `private/ops/sessions/YYYY-MM-DD-<slug>.md` and **prepend** the memory block to
   `private/ops/memory.md`. Formats: [`references/log-and-memory.md`](references/log-and-memory.md).
7. **Clean.** Every repo on a clean default branch; worktrees removed (`git worktree remove`); the session's
   `.tmp-session` files deleted after their content is in the log. Commit `ops` changes through the normal flow.
8. **Mirror to Notion** through `notion-ecosys`, only after `notion-get-self` names the personal workspace (Start
   step 0); otherwise say so and skip. Ids and what each
   target holds: `private/ops/notion.yaml`. From the facts checked in step 2: replace the Dashboard callout on the
   home page, update the Projects rows (Status, Focus, Open PRs, Last synced), and prepend one line to the top of the
   inbox page: `<YYYY-MM-DD> · CC · Xong: ... / Dở: ... / Cần anh: ...`, with the issue or PR link for each item.
   Read the inbox first: a line from Claude Chat is input for the next session.
   Notion is a mirror: totals only for jobs, never company names, pay, contacts or anything not in a public-safe or
   `ops` summary.
9. **Report** three lines to Nghiep, in Vietnamese: done / left and why / where the next session starts.

## Maintenance

Follow `skills/README.md`. A ritual step that gets a tool or a check shrinks to one line naming it.
