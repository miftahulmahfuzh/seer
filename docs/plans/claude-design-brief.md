# Claude Design brief — Seer

Paste everything below the line into Claude Design.

---

Design a mobile-first web app called **Seer** (Strategic Econometric Ensemble Resolver).
It is a personal tool for one user. Every night it proposes up to 4 US stocks to buy on the
next US trading session. Each pick has exactly four numbers the user copies into their
broker app: **Limit price, Take profit price, Stop loss price, Number of shares**.

## Hard rules

1. **Every button is icon-only. No text labels on buttons, ever.** Use Lucide icons.
   Show a tooltip on hover (desktop) or long-press (mobile).
2. Primary target: **iPhone XS Max in Safari, saved to the home screen** (standalone,
   414×896pt, respect notch and home-indicator safe areas). Must also work well on desktop.
3. Follow system dark/light mode. Design both.
4. The user is a trading beginner: numbers must be large, unambiguous and labelled
   (labels are fine on data, just not on buttons).

## Tone

Calm, precise, trustworthy instrument, not a casino. No flashing tickers, no confetti.
Green/red only for profit/loss semantics. The four letters S-E-E-R echo the 4 pick slots.

## Navigation

Bottom tab bar, 4 icon tabs: Today, Positions, Leaderboard, History.
Header: date and a sign-out icon.

## Screens

**1. Sign-in.** Seer logo/wordmark, a single Google-logo icon button. An
"unauthorized account" state (only one email is allowed).

**2. Today (home).**
- Subtitle: "Picks for US session Thu, Oct 8" and the champion strategy name, e.g.
  "Strategy A · Mean Reversion".
- Up to 4 pick cards. Each card:
  - Ticker (large) and company name, current price
  - Four big values: Limit, Take profit, Stop loss, Shares. Each has a copy icon button.
  - Est. cost, Est. profit (green), Est. loss (red), in USD with IDR underneath
  - Expand icon → plain-language explanation paragraph ("Why this pick")
- "Action needed" section above the picks for open positions, e.g.
  "NVDA: day 5 of 5. Cancel bracket and sell at market." with a check icon to dismiss.
- Empty state: "No setups today. Cash is a position."
- Stale-data state: prominent warning, "Data is from Oct 6. Do not trade today."
- Show the empty slots too (e.g. 2 picks + 2 empty slots) so the 4-slot idea is visible.

**3. Positions.** Open mock positions for the champion: ticker, entry price, current price,
P/L % and USD, a horizontal bar showing where price sits between SL and TP, and
"Day 3/5".

**4. Leaderboard.** One row/card per strategy (A Quant, B ML, C LLM-veto) plus SPY
benchmark: equity curve chart (all strategies vs SPY on one chart), total return, win rate,
profit factor, max drawdown, number of trades. Crown icon on the champion.
A **Go-live checklist** for the champion with 5 items, each ✓/✗:
≥3 months forward · ≥100 trades · beats SPY · profit factor ≥1.3 · max drawdown ≤15%.

**5. History.** List of closed trades: ticker, strategy, entry → exit, exit reason
(TP / SL / Time / Gap) as a small icon, P/L % and USD. Filter icons for strategy and
win/loss.

## Sample data

Account: 20,000,000 IDR (~$1,210). Picks:

| Ticker | Limit | TP | SL | Shares |
|---|---|---|---|---|
| GE | 271.40 | 278.90 | 260.15 | 1 |
| LRCX | 98.20 | 102.10 | 92.35 | 3 |
| CSCO | 66.85 | 68.30 | 64.70 | 4 |

(one slot empty)

Deliver: all 5 screens, mobile in dark and light, plus a desktop layout for Today and Leaderboard.
