# Today

## Sub-features

- The champion's picks for the next US session as order tickets: limit buy, take-profit, stop-loss, shares, each with a copy button, cost and profit in USD and rupiah.
- The "Seer recommends no buys" state while SPY buy-and-hold is champion.
- The day-5 time-stop reminder ("Action needed"), dismissed with "Mark as done".
- The slot count ("3 of 4 slots filled") and the `Demo data` pill on demo rows.
- A Claude twin (Seer Adversarial) is never the champion, so it never shows on Today, even if its row is flagged champion.

## How to get to it (user POV)

Open the site. Today is `/`, the first icon of the bottom bar (phone) or left rail (desktop).

## Driving it with verify.sh

```sh
$V up                         # SPY champion
$V api RUN GET /              # "0 Buys tonight" ... "SPY buy-and-hold is the champion. Seer recommends no buys."

$V up --champion=A            # Strategy A champion: the tickets
$V api RUN GET /              # "3 Picks tonight", "[3 of 4 slots filled]", "Action needed",
                              # "NVDA : day 5 of 5 . Cancel bracket and sell at market.", three "Limit buy" tickets
$V ui RUN .claude/skills/verify-seer/features/steps/today-dismiss.mjs --width 390   # result: PASS
$V sql RUN "select o.symbol, d.order_id from action_dismissals d join orders o on o.id = d.order_id"
                              # NVDA | 4  (one row; a parallel run's action_dismissals stays empty)

$V up --champion=F4-MOM12-N20-TREND-CX   # flags F4's Claude twin as champion in the demo DB
$V api RUN GET /                          # "No champion yet." "Seer recommends no buys." — never "F4+Claude"
$V sql RUN "select id from strategies where is_champion"   # F4-MOM12-N20-TREND-CX (the row says champion; the web refuses it)
```

The dismiss journey proves the banner leaves and the tickets stay (`Copy limit price` is still there).

## Gotchas

- The demo champion is SPY, so `--champion=A` is the only way to see tickets locally. It is a demo tweak, applied by `up`, never through `sql`.
- Dismissal is a server action (`app/(app)/actions.ts`). Drive it through `ui`: there is no route to `curl`.
- `--champion=<twin id>` is the only way to test the twin guard: the engine never writes `is_champion` on a twin (contract C2), and the web refuses it anyway.
