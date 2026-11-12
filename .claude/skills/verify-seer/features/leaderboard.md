# Leaderboard

## Sub-features

- Equity curves of every active strategy against SPY over the window they share, with the champion crowned.
- The go-live checklist (design §1): 18 months forward, beats SPY, profit factor ≥ 1.3, max drawdown ≤ 25%, backtest gate. Each row shows Passed / Not yet with the measured number.
- Per-strategy cards and the month-by-month table.
- Claude twins (Seer Adversarial): a twin's card sits right after its original's, in its original's **partner** colour (F4 sky, F4+Claude teal), with an icon of its own (F4 gauge, F4+Claude rocket) and no pill on its card (no card carries a `Paper` or `Not ranked` pill: the checklist says "Paper only"); its chart line is the partner colour with the twin dash (`3 3`). Every original keeps the colour it had before twins existed. The twin's checklist reads rule 5 as `Backtest gate · Can't be run`, with "Paper only. No backtest possible. Claude knows how the past turned out". Its name links to the original's Sera method page.
- Every strategy is unique on the board (R1): no two cards share a sheet, a chart line colour or an icon while there are at most twelve research strategies. Originals take lav, sky, sage, rose, plum, stone in roster order, then amber, orchid, berry, moss, teal, iris; a twin takes its original's partner (lav/iris, sky/teal, sage/moss, rose/berry, plum/orchid, stone/amber), or the first free sheet when an original holds it. The live board claims before the retired shelf, so past twelve a repeat lands on a folded shelf card, never on two live cards (the real board on 2026-11-10 had 13). Icons come from `displayIcons` in `web/components/roster.ts`: a twin draws its original's partner icon, a collision draws the next spare, and the same icon shows on Positions, History and Sean's plan.
- Desktop (≥ 1024 px) card row as one spread (owner, 2026-11-12): every live card in board order, all the same width, each laid over the left 40% of the card to its right ("left covers right"), the row filling its width exactly with no scroll. SPY, the baseline, is always on top and nothing ever covers it. A card's code, chips, total return and metrics sit right-aligned in its uncovered right 60%, with its icon top-left. Clicking a card picks it: it rises above every card but SPY in its own place, with the front card's shadow (cast up and sideways, never onto the month sheet), and no card moves or resizes except that the pick is the tab into the month-by-month sheet. A Claude twin is an ordinary card: picking it leaves its original exactly as it was. A keyboard-focused card rises just under the pick so its focus ring shows. The shadow fade is CSS only and off under `prefers-reduced-motion`. Codes show whole, chips stay inside the card, the chart legend is one row. Below 1024 px the cards are the same column as before.
- Desktop retired shelf (owner, 2026-11-12): the same spread as the live row, `live.length` cards to a line, so each retired card sits exactly under a live card (same x, width and overlap, edge to edge across the shelf sheet), wrapping onto further lines. Retired cards are opaque there (muted sheet, faded contents) so no neighbour shows through an overlap; a picked retired card rises with the front shadow and its outline. On the phone the shelf is unchanged.
- The same ranking from the engine: `compare`.

## How to get to it (user POV)

Third icon (trophy). The checklist switches strategy with its own icon row: on desktop always one row, its round buttons shrinking together once the strategies outnumber the 46px circles the sheet can hold (about 41px at 7 strategies, about 23px at 12); on a phone it wraps as before. A twin is the card named `<original>+Claude`, e.g. `F4+Claude`.

## Driving it with verify.sh

```sh
$V up
$V api RUN GET /leaderboard     # "Forward test Aug 3 – Nov 2", "+5.3% SPY , champion", "+2.6% Best · F1",
                                # "66 Sessions", "Go-live checklist · A · Quant", "1 / 5 Paper only.",
                                # "[Not yet] Profit factor ≥ 1.3 0.78", "[Passed] Max drawdown ≤ 25% 7.9%";
                                # the cards read "F4 · Momentum" then "F4+Claude · Momentum" then "F1 · Trend"
$V api RUN GET '/leaderboard?s=F4-MOM12-N20-TREND-CX'
                                # "Go-live checklist · F4+Claude · Momentum", "Paper only. No backtest possible.",
                                # "Claude knows how the past turned out", "[Not yet] Backtest gate Can't be run"
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs   # order, partner colour, own icon, unique sheets and icons, dash, no pills, rule 5; result: PASS
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-switch-row.mjs --width 1280   # one row at the real count, at 7 and at 12; positions unchanged
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 1440 --theme light
                                # SPY | A | F4 | F4+Claude | F1 | C one flat row, 40% overlap, filling the row; left covers right,
                                # SPY whole; codes and returns in each card's right 60%; Tab raises a focused card; picking the
                                # twin raises it in place (front shadow, F4 untouched, nothing moves); ?s=C gives data-tab=last; result: PASS
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 1280
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-spread.mjs --width 390
                                # phone: the unchanged column, each sheet tucked 40px under the next; result: PASS
# Retired shelf: demo retires nothing, so retire two in the run's own DB first (`sql` is read-only):
docker exec seer-pg-verify psql -U postgres -d v_${RUN//-/_} -c "update strategies set status='retired', paper_end='2026-10-30' where id in ('F1-SPY-SMA200-M','C')"
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-shelf.mjs --width 1440 --theme light
                                # SHELF n=4: F1 under SPY, C under A, same x and width; result: PASS
$V shoot RUN --theme both --width 1280 --width 1440 /leaderboard '/leaderboard?s=F4-MOM12-N20-TREND-CX'
$V sql RUN "select id, twin_of, is_champion from strategies where twin_of is not null"
                                # F4-MOM12-N20-TREND-CX | F4-MOM12-N20-TREND | f
$V engine RUN compare           # common window 2026-08-03..2026-11-02, 66 sessions; ranks by Sharpe, the twin among them;
                                # C "not ranked: 29 sessions of its own"
$V shoot RUN --theme light --width 1280 /leaderboard
$V shoot RUN --theme dark --width 390 /leaderboard '/leaderboard?s=F4-MOM12-N20-TREND-CX'
```

The page and `compare` must agree on the order: both rank by Sharpe, which is why F1 (+2.6%) is "best" ahead of F4 (+3.1%).

## Gotchas

- The checklist's drawdown bar (25%) is mirrored from the engine and pinned by a test. A change to it is a dated owner revision (CLAUDE.md), never something a verify run should "fix".
- `compare` reads the run's DB, so it works on demo data. `paper_check` runs on demo data but cannot replay it (see engine-night.md).
- A twin is ranked like any paper strategy once it shares enough sessions; it is never crowned (the web refuses `is_champion` on a row with `twin_of`).
- The demo twin is built after every other demo row, so it moves none of the numbers above. Read the PNGs: A lav, F4 sky with a gauge, F4+Claude teal with a rocket, F1 sage and C rose. The originals look as they did before twins.
- A twin's legend swatch is dashed (the twin dash) and in its own partner colour, so neither its colour nor its dash matches any original's line.
- At desktop width a card shows its code whole in its uncovered right 60%: `F4+Claude` breaks after the `+` onto two lines, never `F4+…`. The full name and description are the tooltip.
- Where cards overlap only the top one takes a click, so a desktop Playwright click on a card must land in its right 60% (`click({ position: { x: width * 0.7, y: height / 2 } })`): its left 40% belongs to the card on its left unless it is the pick.
- When the pick is not the card right after SPY, it covers its left neighbour's right 40%, code and return included; only that neighbour's middle 20% shows while the pick is in front. That is the agreed cost of raising a card in place; the neighbour keeps its name as a tooltip.
- The picked card is 12px taller than the rest (its tab reaches over the gap onto the month sheet); every other card keeps its exact place and size on a pick. Measure card positions relative to the row: the checklist above can change height with the pick and move the whole row.
