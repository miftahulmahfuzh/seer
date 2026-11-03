# Leaderboard

## Sub-features

- Equity curves of every active strategy against SPY over the window they share, with the champion crowned.
- The go-live checklist (design §1): 18 months forward, beats SPY, profit factor ≥ 1.3, max drawdown ≤ 25%, backtest gate. Each row shows Passed / Not yet with the measured number.
- Per-strategy cards and the month-by-month table.
- The same ranking from the engine: `compare`.

## How to get to it (user POV)

Third icon (trophy). The checklist switches strategy with its own icon row.

## Driving it with verify.sh

```sh
$V up
$V api RUN GET /leaderboard     # "Forward test Aug 3 – Nov 2", "+5.3% SPY , champion", "+2.6% Best · F1",
                                # "66 Sessions", "Go-live checklist · A · Quant", "1 / 5 Paper only.",
                                # "[Not yet] Profit factor ≥ 1.3 0.78", "[Passed] Max drawdown ≤ 25% 7.9%"
$V engine RUN compare           # common window 2026-08-03..2026-11-02, 66 sessions; 1 SPY +3.87, 2 F1 +2.20,
                                # 3 F4 +1.24, 4 A +0.56 (Sharpe); C "not ranked: 29 sessions of its own"
$V shoot RUN --theme light --width 1280 /leaderboard
```

The page and `compare` must agree on the order: both rank by Sharpe, which is why F1 (+2.6%) is "best" ahead of F4 (+3.1%).

## Gotchas

- The checklist's drawdown bar (25%) is mirrored from the engine and pinned by a test. A change to it is a dated owner revision (CLAUDE.md), never something a verify run should "fix".
- `compare` reads the run's DB, so it works on demo data. `paper_check` does not (see engine-night.md).
