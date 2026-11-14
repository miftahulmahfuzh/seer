# Sera

## Sub-features

- Overview, Methods, one method's page (`/sera/methods/MNNNN`: The idea, What could go wrong, variants, verdict), Signal map, Journal, Ideas, Not on Gotrade, How it works.
- Signal map (`/sera/signals`): every stock-picking idea the signal panel has measured, ranked best first by its controlled reading, 50 a page (`?page=N`). Each row is named by what it ranks on and says, in words, whether it passed, the engine's reasons when it did not, its three readings (whole window, since 2009, with the dead companies back), whether it repeats another row's picks (by name), and whether it came from a strategy already tested or was tested as a signal first. No id, digest or code appears. With no panel rows it shows "Nothing measured yet"; with rows and no pass, a "Not one idea passed" finding above the ranking.
- One method's page, the seventh condition: "Beats look-alikes" (the random-twin check) in "Did it work?", in every variant row and card, and in the technical record ("Random look-alikes", "Kind of variant"). A variant with no reading reads "not measured yet" and is drawn as a dashed circle, never a tick; a book that only holds funds reads "does not apply"; a control arm carries a "comparison book" chip instead of a crossed hurdle. The how page lists seven hurdles; the methods list shows seven dots and `n/7`.
- Journal unread badges, cleared by `POST /api/sera/journal/seen` (sendBeacon from the Journal page) into `journal_seen`.
- Gate: only `SERA_EMAIL` (`lib/sera/access.ts`) sees Sera. Anyone else gets 404.

## How to get to it (user POV)

The telescope icon at the bottom of the rail ("Sera, the method lab"). Sera has its own rail and a "Back to Seer" link. The signal map is the radar icon ("Signal map"), third in the rail and third in the phone bar.

## Driving it with verify.sh

```sh
$V up
$V api RUN GET /sera                       # "Overview", "[Journal, 859 new] 99+"
$V api RUN GET /sera/methods               # "Every method tried", "As of Nov 1, 2026"
$V api RUN GET /sera/methods/M0007         # "M0007 · Residual momentum: ...", "The idea", "What could go wrong"
$V api RUN GET /sera/methods/M0007         # "Beats look-alikes: not measured yet" (committed lab: no readings yet)
$V api RUN GET /sera/how                   # "Seven things every method must clear", "Better than random picks"
$V api RUN GET /sera/signals               # "The signal map", "No idea has been measured yet.", "Nothing measured yet" (committed lab: no panel rows until Sera's first replay)
$V api RUN GET '/sera/signals?page=2'      # with fixture rows (see Gotchas): "Page 2 of 2", "[Previous page]" — in the saved HTML or `shoot`'s page text; `api` truncates what it prints
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
- Until the post-merge backfill (`docs/runbooks/yardstick-backfill.md`) runs on `main`, the committed `lab.json` has `role: null` and `yardstick: null` on every trial, so every page reads "not measured yet". To see the measured, unmatched and comparison-book states, write role and reading rows into the run's own lab copy and re-export into the run's web snapshot (`$RUN_DIR/web/data/lab.json`), as the phase-5 Proof does; never into the checkout.
- `/sera/signals` reads `panel.signals` from the committed `lab.json`, which is empty until the post-merge `lab panel-replay` runs on `main`, so it shows its empty state. To see the ranked map, overwrite `panel` in the run's own web snapshot (`~/.local/state/seer-verify/<RUN>/web/data/lab.json`) with fixture rows, as the sera-signal-panel phase-6 Proof does, then GET the page again: `next dev` recompiles on the change. Never write fixture rows into the checkout's `web/data/lab.json`; the snapshot test byte-compares it against `lab/lab.sqlite`.
- Sera's phone bar holds seven tabs at 48 px wide (364 px). An eighth would not fit 390 px without another trade.
