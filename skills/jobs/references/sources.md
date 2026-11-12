# Job sources and scan methods

The scan list for job search sessions (spec §5.2). Read it at the start of a scan. Order: the sources that list the
most new postings first. Mornings bring the most new postings.

Before reading any posting, drop the ones already in `private/ops/jobs/skipped.yaml`. Placeholders: `<country>` is
the ISO country code of the search, `<geoId>` the matching location id, `<kw>` a keyword. Their values are in
`private/ops/jobs/rules.md`.

## Terms of service rule (MUST, spec §5.2)

- A site whose terms forbid scraping or automated access is read only **as a normal signed-in user, page by page**,
  in the browser. No bulk fetching, no hidden endpoints.
- A site that offers a public API or a member feed may be read through it, at a slow pace (one request at a time,
  about 1 s apart; back off on HTTP 429).
- Each source below has a "Terms checked" column. *(verify)* means nobody has read the current terms yet. Read them
  before the first automated read and record the result here.

## Sources

| Source | How to read | Terms checked | Notes |
|---|---|---|---|
| LinkedIn Jobs | Browser (the Claude app browser works when Chrome does not). Location = `<country>` or Worldwide, Remote filter on. Page by page as a signed-in user. | **Pending Nghiep's decision** (see below) | The "remote" label is often wrong; read every description. Easy Apply: Nghiep clicks. |
| Himalayas | Open the country page in the browser and wait for the bot check. Public JSON API: `/jobs/api/search?country=<country>&sort=recent&page=N`, optional `&q=<kw>`. Apply: "Apply now" → "I'm ready to apply" → the employer's ATS. | *(verify)* | Many postings from AI-interview platforms: skip them (`rules.md` §3). |
| ViecRemote | Member account. Member feed: open `/jobs-feed/member/current.json`, fetch `meta.url`, read the array (title, company, datePosted, location, salaryRange, experience, summary, applyUrl). Keep the last 3 days. | *(verify)* | Often lists pay. Many duplicates of Himalayas. |
| timviecremote | Read section pages one by one (data-ai, lap-trinh, tieng-viet, part-time) with a page fetch. | *(verify)* | Mostly on-site and old postings. Quick pass, low expectations. |
| Glints | Nghiep signs in; Claude fills forms. | *(verify)* | Remote postings mostly from one neighbouring market. |
| Remote OK, We Work Remotely, Jobicy | Browser, page by page. | *(verify)* | Many postings tied to other regions; check the location rule. |
| Arc | Needs an account to apply. | *(verify)* | Ask Nghiep before any sign-up. |
| DailyRemote | Browser. | *(verify)* | Hides the company behind a paywall: skip (`rules.md` §2). |
| ITviec | — | — | Blocked by its bot check for automated reads. Skip unless Nghiep opens it himself. |
| Company ATS pages (Workable, Ashby, Greenhouse, Lever, Dover, Teamtailor) | Reached from the sources above. Workable apply URLs follow `apply.workable.com/<account>/j/<id>/apply/`. Some ATS pages open only in the Claude app browser. | n/a (applying, not scanning) | Form tips: `rules.md` §7. |
| Candidate profile on an ATS vendor site | Use as a quick-apply profile, not for search (search there finds little). | n/a | Re-check profile fields after uploading a new CV. |
| Mail | The scheduled mail check (listed in `private/ops/automations.md`); by hand: the last 3 days, excluding repo notifications and job alerts. | n/a | Job alert mails from boards are a secondary source of leads. |

## LinkedIn guest endpoints: pending

The old scan used LinkedIn's unauthenticated "guest" job search endpoints. LinkedIn's terms forbid scraping, so under
the rule above they are **not used** until Nghiep decides at the first weekly review whether they stay in the list
(spec §5.2). Until then, LinkedIn is read only as a signed-in user, page by page. Record the decision here and in an
ADR note.

## Keywords

Start with: AI engineer, machine learning, LLM, data scientist, data analyst, Python developer, data engineer,
research analyst, automation engineer, backend developer, AI trainer, Vietnamese. Worldwide searches add: AI trainer
chemistry, environmental data scientist, LLM evaluation, Vietnamese.

## After a scan

- New leads → `applications.yaml` with `stage: lead`, or straight to drafting if Nghiep is present.
- Postings that fail a rule → `skipped.yaml` with the reason.
- One line in the session log: sources scanned, postings read, leads, skips.
