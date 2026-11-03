# Sera

## Sub-features

- Overview, Methods, one method's page (`/sera/methods/MNNNN`: The idea, What could go wrong, variants, verdict), Journal, Ideas, Not on Gotrade, How it works.
- Journal unread badges, cleared by `POST /api/sera/journal/seen` (sendBeacon from the Journal page) into `journal_seen`.
- Gate: only `SERA_EMAIL` (`lib/sera/access.ts`) sees Sera. Anyone else gets 404.

## How to get to it (user POV)

The telescope icon at the bottom of the rail ("Sera, the method lab"). Sera has its own rail and a "Back to Seer" link.

## Driving it with verify.sh

```sh
$V up
$V api RUN GET /sera                       # "Overview", "[Journal, 859 new] 99+"
$V api RUN GET /sera/methods               # "Every method tried", "As of Nov 1, 2026"
$V api RUN GET /sera/methods/M0007         # "M0007 · Residual momentum: ...", "The idea", "What could go wrong"
$V labsql RUN "select max(id) from insights"                                 # 891
$V api RUN POST /api/sera/journal/seen '{"ids":[891,890],"via":"click"}'      # HTTP 204, no body
$V sql RUN "select insight_id, via from journal_seen order by 1"             # 890 | click, 891 | click
$V api RUN GET /sera                       # "[Journal, 857 new]"  (859 - 2)
$V api RUN POST /api/sera/journal/seen '{"ids":"nope"}'                       # HTTP 400
```

## Gotchas

- Sera pages read the committed `web/data/lab.json` in the run's web snapshot, not `lab.sqlite` and not the database. The counts above are the snapshot's as of the commit under test and move with every lab commit. Re-read them (`labsql`) rather than trusting these numbers. The seen marks, by contrast, live in Postgres.
- `/sera` is 4 MB of HTML. Its first compile takes several seconds.
- "Not on Gotrade" (`/sera/gotrade`) adds and removes symbols with a server action that also dispatches `repick.yml`. The dispatch is skipped ("GITHUB_DISPATCH_TOKEN is not set") and would be blocked by the preload anyway, so only the `unavailable_symbols` row can be proved here.
