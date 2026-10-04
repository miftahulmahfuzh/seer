# P7b pre-registration

Written by P7a from the development-window run [`2026-10-04-p7a-dev-exploration.md`](../backtests/2026-10-04-p7a-dev-exploration.md). Registry source sha256 `110abce5a77205e367b09d3ffb9dcb112a9e470f7f455dc6841076137813b5a4`; research store fingerprint `5451195fd552e208eaadfc6bc89241b9b8e3e6ccb0f4c447a84bbc4f32e7d90a`; 54 trials.

This file fixes what P7b runs before any test-window number exists (handover D1, D8, D10). Nothing below may change between this file and P7b. P7b runs each finalist **once** on the test window and applies the gate. It does not tune, swap or add finalists.

## None eligible

No candidate met every D8 condition on the development window, so there are no finalists and **P7b does not run** (handover D8, §9).

The evidence is the frontier, [`2026-10-04-p7a-dev-exploration-frontier.svg`](../backtests/2026-10-04-p7a-dev-exploration-frontier.svg), with every row in [`2026-10-04-p7a-dev-exploration.md`](../backtests/2026-10-04-p7a-dev-exploration.md). It shows what drawdown was reachable at a SPY-beating return on the development window. The owner decides next with it: (b) SPY buy-and-hold as the champion, (d) Strategy C as forward paper only, or another revision.

| D8 condition | Candidates failing |
|:---|---:|
| beats SPY TR | 19 |
| max DD <= 15% | 54 |
| PF >= 1.3 | 14 |
| >= 100 trades | 21 |
| owner inputs | 11 |

The five candidates with the highest MAR, and why each failed:

| Candidate | Family | Return | SPY TR | Max DD | PF | Trades | MAR | Failed |
|:---|:---|---:|---:|---:|---:|---:|---:|:---|
| `F4-MOM12-N20-TREND` | F4 | +1864.8% | +351.4% | 22.2% | 2.27 | 1,154 | 0.73 | max DD <= 15% |
| `F4-MOM6-N10-TREND` | F4 | +3708.9% | +351.4% | 30.4% | 2.09 | 849 | 0.66 | max DD <= 15% |
| `F4-MOM12-N10-TREND` | F4 | +2535.6% | +351.4% | 28.2% | 2.20 | 638 | 0.64 | max DD <= 15% |
| `F9-SPY200M70-MOM30` | F9 | +878.6% | +351.4% | 19.2% | 4.28 | 635 | 0.64 | max DD <= 15% |
| `F4-MOM12-N10-TREND-IVOL` | F4 | +2278.0% | +351.4% | 27.7% | 2.10 | 638 | 0.63 | max DD <= 15% |

**Survivorship (handover D4).** Development results on single stocks are optimistic: yfinance serves no delisted tickers, and a reused ticker can map a past member onto a different company's prices. ETF-only candidates have no survivorship bias. P7b's test window and forward paper trading do the proving.

## The owner's date

- **The owner's 2026-11-01 date and design §1.** The owner plans to put 20,000,000 IDR of real money in on 2026-11-01. Design §1 is law: real money needs a strategy that has passed the backtest gate and then at least 3 months and at least 100 closed trades of forward paper trading. No strategy has passed, and P4 paper trading has not started. Even if a P7b finalist passes, the earliest §1-compliant date is about 3 months after its paper trading starts: around February 2027 at the soonest. §1 does not move to fit the date. The owner remains free to put the 20,000,000 IDR into SPY directly on 2026-11-01; that is the benchmark, and it needs no Seer approval.
