# Leaderboard

## Sub-features

- Equity curves of every active strategy against SPY over the window they share, with the champion crowned.
- The go-live checklist (design §1): 18 months forward, beats SPY, profit factor ≥ 1.3, max drawdown ≤ 25%, backtest gate. Each row shows Passed / Not yet with the measured number.
- Per-strategy cards and the month-by-month table.
- Claude twins (Seer Adversarial): a twin's card sits right after its original's, in the original's colour, with a `Paper` chip; its chart line is the original's colour with its own dash (`3 3`). Cards after it keep their colours. The twin's checklist reads rule 5 as `Backtest gate · Can't be run`, with "Paper only. No backtest possible. Claude knows how the past turned out". Its name links to the original's Sera method page.
- The same ranking from the engine: `compare`.

## How to get to it (user POV)

Third icon (trophy). The checklist switches strategy with its own icon row. A twin is the card named `<original>+Claude`, e.g. `F4+Claude`.

## Driving it with verify.sh

```sh
$V up
$V api RUN GET /leaderboard     # "Forward test Aug 3 – Nov 2", "+5.3% SPY , champion", "+2.6% Best · F1",
                                # "66 Sessions", "Go-live checklist · A · Quant", "1 / 5 Paper only.",
                                # "[Not yet] Profit factor ≥ 1.3 0.78", "[Passed] Max drawdown ≤ 25% 7.9%";
                                # the cards read "F4 · Momentum" then "F4+Claude · Momentum Paper" then "F1 · Trend"
$V api RUN GET '/leaderboard?s=F4-MOM12-N20-TREND-CX'
                                # "Go-live checklist · F4+Claude · Momentum", "Paper only. No backtest possible.",
                                # "Claude knows how the past turned out", "[Not yet] Backtest gate Can't be run"
$V ui RUN .claude/skills/verify-seer/features/steps/leaderboard-twin.mjs   # order, colours, dash, chip, rule 5; result: PASS
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
- The demo twin is built after every other demo row, so it moves none of the numbers above. Read the PNGs: F4 and F4+Claude are both sky; F1 sage and C rose, as before twins.
- A twin's legend swatch is dashed like a second-lap original's. Its label (`F4+Claude`) is what tells them apart.
- At desktop width a card shows only the code, and `F4+Claude` is too long for a 30px card head: it ellipsises to `F4+…` (the tooltip has the full name; the mobile row reads `F4+Claude · Moment…`). Before the bound it ran under the icon.
