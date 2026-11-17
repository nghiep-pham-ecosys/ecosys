# Weekly review template

Output path: `private/ops/reviews/YYYY-Www.md`, using the ISO week being reviewed (for example `2026-W46`). The file
is private, so its content may be in Vietnamese. Keep the headings as below so the next review can find them.
Every number names its source; unchecked numbers are marked *unverified*.

```markdown
# Review <YYYY-Www> (<Mon YYYY-MM-DD> – <Sun YYYY-MM-DD>)

Drafted in: <session S<n> YYYY-MM-DD-<slug>> · Finished by Nghiep: <date, minutes spent>

## Hours per area
| Area | Budget (h) | Planned (h) | Done (h) | WIP limit | In progress now |
|---|---|---|---|---|---|
| jobs | | | | | |
| learn | | | | | |
| content | | | | | |
| lab | | | | | |
| ecosys | | | | | |
| work-block | fixed | | | — | — |
| buffer | <buffer_pct>% | — | <used for> | — | — |

## Agent hours (Claude Code)
| Budget (`agent.hours`) | Buffer (`agent.buffer_pct`) | Planned (h) | Done (h, session logs) | Sessions planned / held |
|---|---|---|---|---|
| | | | | |

Larger gap this week: <Nghiep's hours | agent hours> — <cause>

## Done (with evidence)
- <repo>#<n> <title> — <evidence link>

## Moved out or dropped
- <item> — <to Next | Dropped | Paused> — <why>

## Jobs funnel (this week)
- Sent: <n> · Replies: <n> · Screens: <n> · Interviews: <n> · Offers: <n>
- Closed by the 30-day rule (confirmed by Nghiep): <n>
- Follow-ups due next week: <n> (details stay in applications.yaml)

## Deadlines, next 14 days
- <YYYY-MM-DD> <what> — <status> (within 48 h first)

## Content
- Published: <n> of <n> planned · Drafts waiting for approval: <n>

## Automations
- Red or missed runs: <name, date, cause>
- Not listed in automations.md (propose disabling): <name>

## Plan limits
- Hit on: <dates, account> · Work moved because of it: <items>

## Decisions (Nghiep)
- <only what Nghiep decided>

## Next week's plan
| Area | Item | Owner | Estimate (h) | Due | Status |
|---|---|---|---|---|---|
| | | <nghiep or claude-code> | | | This week |

Sum per area within Nghiep's budget: <yes | no → list what moved out>
Agent hours within `agent.hours`: <yes | no → list what moved out>
WIP within limits: <yes | no → which area, which item waits in Next>

## Does not fit this week
- <item> — <estimate> — <why it waits>
```
