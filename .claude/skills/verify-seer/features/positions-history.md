# Positions and History

## Sub-features

- Positions: one strategy's open book at a time (unrealized P/L in USD and rupiah, open count, exits today, the `Paper` label), plus a strategy switcher (`SPY`, `A · Quant`, `F4 · Momentum`, `F4+Claude · Momentum`, `F1 · Trend`, `C · News veto` on demo data; a Claude twin sits right after its original and carries the `Paper` label). Bracket strategies show slot cards with a stop/target rail; basket strategies show the whole book.
- History, Trades tab: closed trades with strategy and outcome filters and the net result.
- History, Activity tab (`?v=activity`): every buy and sell the paper books made, with fees.

## How to get to it (user POV)

Second icon (Positions) and fourth icon (History) of the bar. The strategy switcher is the row of round icons under "Unrealized P/L".

## Driving it with verify.sh

```sh
$V up
$V api RUN GET /positions                             # "Unrealized P/L A · Quant", "−$2.10 −Rp 35.000", "3 Open", "1 Exits today",
                                                      # "Paper On paper since Tue, Aug 4.", first card "NVDA Nvidia · 1 share"
$V api RUN GET '/positions?s=F4-MOM12-N20-TREND'      # "Unrealized P/L F4 · Momentum", "+$11.44 +Rp 189.000", "12 Open"
$V api RUN GET '/positions?s=F4-MOM12-N20-TREND-CX'   # "Unrealized P/L F4+Claude · Momentum", "10 Open", "Paper"
$V api RUN GET /history                               # "[Strategy filter]", "[Outcome filter]", "−$45.04 Net result", "24 Won"
$V api RUN GET '/history?v=activity'                  # "[Side filter]", "[Buys and sells]"
$V shoot RUN --theme both --width 390 --width 1280 /positions /history   # exit 0, "no HTTP error, console error or horizontal scroll"
$V ui RUN .claude/skills/verify-seer/features/steps/nav-sections.mjs     # walks all sections; result: PASS
```

Read the PNGs in `NN-shoot-*/`: the phone Positions shot shows the NVDA card with Entry $184.20, Now $186.95, Stop $176.80, Target $190.60, "Day 5/5 · exit today".

## Gotchas

- `?s=` takes the strategy id (`A`, `C`, `F1-SPY-SMA200-M`, `F4-MOM12-N20-TREND`, `F4-MOM12-N20-TREND-CX`, `SPY`), not the short label.
- The `Demo data` pill wraps onto two lines at 390px. It is cosmetic and demo-only.
