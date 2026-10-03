# Handover: revise the shared trade rules, and search widely for a strategy that can pass (roadmap P7a)

Written 2026-10-03, after P6a landed on `main` @ `2086664` with a **failed** gate. Strategy B was
the third strategy to fail. The owner chose option **(c)**: revisit the design-§5 trade rules. The
owner's words: *"open all options and approaches and possibilities and strategies … do not give up
… let's take our time. slowly, but sure. there is no rush."*

Pass this file straight to `/analyze` in a fresh session, and read all of it first. Like the P3,
P3b and P6a handovers, it separates three things:
- decisions that are **already made**;
- facts that were **verified**;
- questions the analysis still has to settle.

Two things are new. §4 is a wide **catalogue of options**, and §3 defines a **protocol** that makes
a wide search honest. Both matter more than any single strategy idea.

---

## 0. In plain words: what "beat SPY buy-and-hold" means

SPY is one fund that holds all 500 of the biggest US companies. "Buy-and-hold" means the laziest
possible plan:
- on day one, put the whole 20,000,000 IDR into SPY;
- keep the dividends it pays, invested;
- do nothing else, ever.

Over our test period, 2018-01-02 → 2026-10-02, the lazy plan grew the money by **+187.6%**, which
is about **12.8% a year**. The money nearly tripled.

The rule fixed in design §1 says a strategy may use real money only if it does **both**:
1. **Ends with more money than the lazy plan.**
2. **Never falls more than 15% from its own previous high** (max drawdown ≤ 15%). It must also win
   at least $1.30 for every $1 it loses (profit factor ≥ 1.3).

The lazy plan itself fell **30%** at its worst, in the COVID crash of 2020. So the bar is **more
upside than SPY with half of SPY's downside**. Most professional funds do not beat SPY even
without the drawdown condition. That is why the bar is right: if Seer cannot clearly beat the lazy
plan, the lazy plan is the honest answer, and that answer is also worth having.

So yes, we are still trying to beat SPY buy-and-hold. Nothing in this handover lowers that bar.
§3 says how to search widely without fooling ourselves.

---

## 1. Where we are

| Phase | Strategy | Rules | Result (walk-forward 2018-01-02 → 2026-10-02 unless noted) |
|---|---|---|---|
| P3 | A: RSI(2) dip-buy, A's bracket | design §5 | OOS 2022 → 2026: **−15.0%** vs SPY TR +71.9%; PF 0.92; DD 33.3% |
| P3b | A2: A + regime/calm/floor variants, tuned per fold | design §5 | **+9.1%** vs +187.6%; PF 1.02; DD 29.1% |
| P6a | B: gradient-boosted ranker on A's candidates and A's bracket | design §5 | **+13.3%** vs +187.6%; PF 1.03; DD 57.6% (B-linear: +20.6%, PF 1.05, DD 32.4%) |

ROADMAP says:
- **A, A2 and B are closed on this data.** None of them is reworked again.
- **P4 stays blocked.**
- The owner decides between (b), (c) and (d). **The owner chose (c).**

What all three failures share is not the stock *selection*. It is the **trade shape** that design
§5 and A's bracket impose on every strategy:
- **Short holds:** a time stop at 5 days.
- **Small positions:** 4 slots of about $370 each, in whole shares.
- **Tight exits:** a fixed bracket of TP +1 ATR and SL −1.5 ATR from a limit 0.5 ATR below the
  close.
- **Mostly idle cash:** money waiting between trades earns nothing.

§2 shows the evidence. That is why (c) is the right lever, and why this time the rules themselves
are the thing being explored.

Read before planning:
- `docs/plans/2026-10-03-seer-design.md`, §1, §2, §4 and §5. **§1 stays law.** §5 is what this
  handover opens.
- The three backtest reports:
  - `docs/backtests/2026-10-02-strategy-a.md`;
  - `docs/backtests/2026-10-02-strategy-a2-walkforward.md`;
  - `docs/backtests/2026-10-02-strategy-b-walkforward.md`.

  The "Diagnostics" and "Calibration" sections matter most.
- `docs/handover/2026-10-03-strategy-b-ranker.md`. Its environment section (§5) still holds.
- `docs/ROADMAP.md`, P3 → P6a.
- `engine/package_readme.md`:
  - `sim`, `strategies`, `backtest`;
  - `backtest walk-forward (P3b)`, the B sections;
  - `## Performance`.
- `engine/data/SOURCES.md` (index membership history).

---

## 2. What three failures tell us (verified unless marked *derived*)

**1. The average order was worth nothing after costs, whichever stock it picked.**

B's training labels give the net return of A's bracket order placed on *every* eligible
candidate. Their mean per fold was **−0.036% to +0.012%** (B report, "Training per fold"). So
under §5 and A's bracket, a randomly chosen order roughly loses its 0.2% round trip. A selector can
only help if it finds the rare good orders. B's calibration says it did that weakly:
- only the top decile had a clearly positive realized label, +0.158%;
- deciles 2–9 sat between −0.13% and +0.05%.

**2. Costs ate most of the gross edge.**

| | A2 walk-forward | B | B-linear |
|---|---:|---:|---:|
| Closed trades | 1,329 | 1,095 | 1,182 |
| Gross P/L (USD) | +1,035 | +769.60 | +953.29 |
| Costs (USD) | 901 | 573.03 | 630.13 |
| Cost drag | 87% | 74.5% | 66.1% |
| Trades with < 3 shares | 36.9% | 32.7% | 42.0% |

**3. Half the money sat idle (*derived*: closed trades × average days held ÷ (2,200 sessions × 4
slots)).**
- A2 was invested about **51%** of the time, B about **45%**, B-linear about **46%**.
- SPY buy-and-hold is invested **100%** of the time and also collects dividends.
- To match SPY's 12.8% a year while invested only half the time, the invested half must earn
  roughly **25% a year**.
- The simulator credits **no dividends** to strategy positions (verified: `seer_engine/sim` has
  no dividend handling). The SPY total-return benchmark does get them.
- The analysis must measure exposure exactly, not trust this estimate.

**4. The time stop lost money.**
- B's time-stop exits: **390 trades, −$1,491.86**.
- B's take-profits: +$6,605.43. Its stop-losses: −$3,289.71. Its gap exits: −$1,627.30.

A 5-day horizon cuts trades before most effects can pay.

**5. The learned model mostly learned *market timing*, not stock picking.**
- In every fold, B's top three features were SPY's own: `spy_ret_5`, `spy_close_sma200` and
  `spy_ret_20`, together about 75–87% of split gain.
- In 7 of B-linear's 9 folds, its top feature was `spy_close_sma200`.

The signal in this data is about *when to be in the market* far more than *which stock*. That
argues for strategies that control **exposure** (risk on or off), not only selection.

**6. Small slots block good trades.**
- A $370 slot cannot buy one share of a stock above $370. Those orders were rejected:
  `lt_one_share` 380 (A2), 504 (B) and 461 (B-linear).
- Many trades hold 1–2 shares, so rounding dominates.

**7. The bar.**
- SPY total return over 2018 → 2026-10-02: +187.6%, CAGR 12.8%, max DD 30.2%.
- Over 2015-10-19 → 2026-10-02 it had a similar drawdown, from COVID.
- SPY's best years (2019, 2021, 2023, 2024) each made over 20%.
- The gate wants more return than SPY at half its drawdown.

**8. Data is limited, and 2015 → 2026 has been looked at three times.**
- `bars`: 1,817,429 rows, 663 symbols, 2015-01-02 → 2026-10-02 (more from the nightly job, Mon
  2026-10-05 onward).
- Every strategy so far was judged on 2015-10 → 2026. **That window is no longer fresh.** Every
  further idea tested on it is selected partly on noise, and the more ideas we try, the worse it
  gets.
- §3's protocol exists because of this.

**9. Older history is available and unseen** (verified 2026-10-03, `engine/data/`):
- `sp500_history.csv` has point-in-time S&P 500 membership from **1996-01-02**.
- `ndx_history.csv` has Nasdaq-100 membership from **2007-02-01**.
- yfinance has daily bars for the survivors back to the 1990s, and for major ETFs from their
  launch:
  - SPY 1993, QQQ 1999, IWM 2000;
  - sector SPDRs 1998;
  - TLT and IEF 2002, GLD 2004, BIL 2007.
- **Nobody in this project has looked at any pre-2015 result.** That makes 1996/2000 → 2015 a
  genuinely fresh window for developing ideas, though it carries a worse survivorship caveat for
  single stocks (§3, D4).

---

## 3. Decisions

### Law: do not reopen

| Topic | Rule |
|---|---|
| Go-live checklist | **Design §1, all 5 items, thresholds unchanged.** Beat total-return SPY, PF ≥ 1.3, max DD ≤ 15%, ≥ 3 months and ≥ 100 trades forward, passed a 10-year backtest. Nothing here lowers them |
| No look-ahead | Decisions for session S use data through `prev_session(S)` only, from point-in-time membership where membership applies. The same holds for training labels and for any signal-based exit |
| Determinism and purity | Same inputs give `==` results and byte-identical report files. Strategy and backtest cores stay pure (`test_strategy_purity.py`) |
| Closed records | A, A2 and B as specified stay closed on 2015 → 2026. Their modules, frozen constants, tests and `docs/backtests/2026-10-02-*` reports stay as they are. **Under the default rules, their reports re-render byte-identically**, and the analysis must keep that true (see D2) |
| Read-only on Neon for research | Backtests never write Neon. The data pipeline may add rows, under the storage rule D5 |
| Honest reporting | The repo is public on purpose, losing reports included. Every report states how many candidates were tried (D7) |
| Gotrade reality | Every rule set must be something the owner can actually execute in Gotrade by hand, at most once a day. If a rule needs an unverified Gotrade feature, the owner verifies it before real money, and the report says the rule depends on it (§3, "Owner inputs") |

### What (c) opens

Design §5 becomes a **parameter**, not a constant. Concretely, these may now differ from today's
§5, per strategy and per rule set:
- the holding horizon and the time stop;
- the number of slots and their size;
- the entry order type;
- the exit rules (bracket, signal exit, rebalance);
- the universe, including ETFs;
- the rebalance cadence;
- position sizing;
- what idle cash does;
- dividend crediting.

**What stays from §5:** backtest and live use identical rules; 0 picks is always valid; and the
0.1% per side cost assumption, unless the owner verifies a better number.

A changed §5 is a design change, so `docs/plans/2026-10-03-seer-design.md` §5 gets a revision
section that names the new rule sets, written once the protocol below picks them. **P7a only
proposes.** The owner signs off on the design edit (D10).

### Decided in this handover (pre-registered before any new result exists)

These are recommendations, and each can be overturned with a one-line change before planning. They
are fixed now, before anyone sees a result.

| # | Topic | Decision | Why |
|---|---|---|---|
| D1 | **Split the work in two** | **P7a (this handover)** builds the machinery and explores **only on a development window**. It ends with a committed **pre-registration file** naming at most 3 finalists, each exactly specified. **P7b (a later handover)** runs those finalists **once** on the test window and applies the gate. P7a never runs a candidate on the test window | "Slowly, but sure." Every look at the test window costs freshness. Building, exploring and finalizing first keeps that number at one |
| D2 | **Rules as a value** | Introduce a `TradeRules` value carrying every §5 lever in §4.A. `TradeRules.DESIGN_V0` reproduces today's §5 exactly. The simulator and runner take it, and with `DESIGN_V0` they are **byte-for-byte unchanged in behaviour**: the A, A2 and B reports re-render identically, proven by a test and by a real-data `cmp`, as P6a did for A2. New behaviours (signal exits, rebalancing, dividends, fractional shares, market-on-open entries) are new code paths reached only through non-default rules | The existing evidence must stay reproducible, and P4 must later run the same code path the backtest ran |
| D3 | **Windows** | **Development window:** from the first session where a candidate's instruments have ≥ 200 bars (ETFs: around 2001–2005; stocks: around 1997), through **2015-10-16**. **Test window (P7b only):** 2015-10-19 → data end, the "10-year backtest" of §1 item 5. A 2018-01-02 → data-end slice is reported beside it for comparison with A2 and B | The dev window has never been looked at by anyone in this project. The test window matches §1's 10-year backtest and the period everything else was judged on |
| D4 | **Survivorship in the dev window** | Backfill pre-2015 bars for every S&P 500 member since 1996 and every Nasdaq-100 member since 2007 that yfinance can serve. Count and report the members it cannot serve, year by year, like `runner.survivorship`. Expect far more missing names than the 115 seen since 2015. **Dev results on single stocks are therefore optimistic**, and the pre-registration file says so. ETF-only candidates have no survivorship bias | The dev window is for ranking ideas, not for proving them. P7b's test window plus forward paper do the proving |
| D5 | **Where research history lives** | Pre-2015 bars and ETF history used only for research live in a **local, gitignored research store** (for example `engine/.research/*.parquet`, rebuilt by a command), **not in Neon**. ETFs needed nightly by a finalist are added to Neon's `bars` only in P7b or P4, after the owner agrees. Measure Neon's storage before adding anything there | Neon free tier is small. The web app and the nightly job never need 1996 data |
| D6 | **The search is wide but finite** | Before any dev run, P7a commits a **candidate registry**: a file listing every candidate (strategy family × rule set × fixed parameters), with a one-line rationale each. The catalogue in §4 is the menu, and the analysis chooses the registry from it. **Size cap: 60 candidates.** Parameters are fixed per candidate. A family may enter as several candidates (for example 3 lookbacks), and each counts toward the cap. The registry may grow during P7a, but only by appending, and each append is committed **before** its dev run, with its own timestamp | A wide search is fine on dev data as long as the number of tries is known and every try is reported. Appending is allowed; editing a candidate after seeing its result is not |
| D7 | **Report every try** | The dev report has one table row per registry candidate: return, CAGR, max DD, PF, trades, exposure, turnover, cost drag, worst year, and gate status *on dev*. It also shows a **return-vs-drawdown frontier chart** with SPY total-return marked. No candidate is hidden. The report states the trial count and a deflated-Sharpe or similar multiple-testing note | Showing every try is what makes a wide search honest |
| D8 | **How finalists are chosen** | This rule is written now, so it cannot bend to results. **Eligible:** beats SPY total-return over the dev window **and** max DD ≤ 15% **and** PF ≥ 1.3 **and** ≥ 100 closed trades **and** Gotrade-executable under the owner's verified answers. **Rank:** CAGR ÷ max DD (MAR), highest first. **Keep the top 3, at most one per strategy family**, so three near-copies of one idea do not use up all three places. **None eligible:** P7a's report says so, shows the frontier, and P7b does not run. The owner then decides with that evidence (§8) | The §1 thresholds applied to the dev window, plus a diversity rule |
| D9 | **Selection never sees the test window** | Code-level guarantee: the dev runner refuses any session after 2015-10-16, and a test proves it. P7a's report has no test-window number at all | Freshness by construction, not by good intentions |
| D10 | **The design edit** | P7a writes the proposed §5 revision **as a section of the pre-registration file**, not into the design document. The design document changes in P7b, and only for finalists that pass | The design follows evidence. A proposal stays a proposal until the evidence arrives |
| D11 | **Dividends** | Rule sets that hold positions longer than 5 days **must** credit cash dividends on the ex-date for held shares, from yfinance dividend history. `DESIGN_V0` keeps "no dividends" so the closed reports stay identical | Holding SPY or TLT for months without dividends would understate a strategy by about 1.5–4% a year, an unfair handicap against SPY total-return |
| D12 | **A, A2 and B ideas may return, renamed, as dev candidates** | For example, "RSI(2) dip-buy with a 20-day horizon and no TP" is a new candidate with a new ID, tested on the dev window like any other. It is never re-run on 2015 → 2026 inside P7a | The closed records stay closed, but a good idea under better rules deserves a fair, fresh test |
| D13 | **Runtime** | Measure it. Vectorize where P3b and P6a did. 60 candidates × about 15 dev years should take minutes to tens of minutes. Parallelize only above 60 min, gathering results in a fixed order | The P3 rule, unchanged |

### Owner inputs (the analysis plans around these and never blocks on them)

These are facts about Gotrade and about the owner's habits that the engine cannot verify. For each
one, the analysis plans against the **conservative default**. A rule set that needs the
non-default answer is marked `needs-owner-verification` in the registry and **cannot become a
finalist** until the owner confirms it.

| Question | Conservative default |
|---|---|
| Can Gotrade buy US **ETFs** (SPY, QQQ, sector SPDRs, TLT, IEF, GLD, BIL/SGOV)? Which ones? | Assume **SPY and QQQ only** |
| Are **fractional shares** allowed for **market** orders? Design §2 says only that *limit* orders need whole shares | Whole shares only |
| Can an order be placed as **market-on-open**, or is "a limit far above the price" the workaround? | Limit orders only |
| The real **fee** per trade (the FX question is settled; see "Owner facts" below) | 0.1% per side, as now |
| **Leveraged ETFs** (QLD, SSO, TQQQ, UPRO): available, and acceptable to the owner? | Not used |
| How often will the owner place or modify orders: nightly, weekly or monthly? Will they change a stop by hand every night? | Nightly placement allowed; no nightly stop edits (brackets stay fixed at order time); signal exits and rebalances happen at most once a day, as a market or limit sell at the next open, the way the time stop already works |
| Can idle cash sit in a T-bill ETF (BIL or SGOV) or in a money-market product? | Idle cash earns 0% |

### Owner facts (stated by the owner, 2026-10-03)

**The Gotrade wallet is in USD.**
- A top-up in IDR is converted to USD once, on arrival, and the money stays in USD while trading.
  Nothing converts back after each trade.
- The owner converts to IDR only when withdrawing, and withdraws only *some* winnings, at the end
  of a period.

So:
- **FX is not a per-trade cost.** The 0.1% per side covers fees and slippage only, and no rule set
  may add an FX spread per trade.
- **The engine already models this correctly.** `initial_cash_usd(20,000,000 IDR, usd_idr on the
  start date)` converts once, and every trade, metric and SPY benchmark is in USD after that. No
  change is needed, and none should be planned. The IDR value is display only (design §5,
  "tracked in USD, displayed in both").
- **The gate compares in USD.** Strategy equity and SPY are both USD, so the exchange rate cannot
  make a strategy look better or worse than SPY.

**The owner's first real-money plan:**
- top up 20,000,000 IDR on **2026-11-01**;
- trade with Seer every trading day of November 2026;
- withdraw some winnings, if any, on **2026-11-30**.

**This conflicts with design §1, which is law.**
- Real money needs a strategy that has passed the backtest gate **and** ≥ 3 months plus ≥ 100
  closed trades of forward paper trading.
- As of 2026-10-03, no strategy has passed, and P4 paper trading has not started.
- So even if a P7b finalist passed tomorrow, the earliest §1-compliant real-money date is about 3
  months after its paper trading starts. That is around **February 2027 at the soonest**, not
  2026-11-01.

What this handover does about it:
- **It does not move §1** to fit the date.
- **It does not hurry P7a.** The owner said there is no rush.
- **The reports and ROADMAP state this plainly,** so the date is a conscious owner decision, not a
  surprise.
- **The owner remains free to put 20M IDR into SPY itself on 2026-11-01.** That is the benchmark,
  and it needs no Seer approval.

**What the plan means for strategy design (information for the registry, not a rule):**
- **One month is short.** A monthly-rebalance family (F1–F4) makes one decision in November. A
  daily family makes about 20.
- **Neither horizon proves an edge in one month.** That is exactly why §1 asks for 3 months and
  100 trades.
- **The withdrawal is fine.** Taking out *some* winnings at a period end only shrinks the next
  period's equity. The engine sizes slots from equity, so it needs no new rule.

---

## 4. The catalogue of options

The analysis turns this menu into the candidate registry (D6). Each entry says what it is, why it
might help on the three gate items (**R**eturn vs SPY, **P**rofit factor, max **D**rawdown), and
what it needs. Nothing here has been tested. Rough expectations are labelled as expectations.

### 4.A Trade-rule levers (the `TradeRules` value)

| # | Lever | Options | Expected effect | Needs |
|---|---|---|---|---|
| L1 | Holding horizon / time stop | 5 days (today); 10, 20, 60 days; none (exit only by TP/SL, signal or rebalance) | Longer means fewer trades and less cost drag (§2.2), and lets trend effects pay (§2.4). It can raise DD | Nothing new: the time stop is already a manual sell |
| L2 | Slots | 1, 2, 3, 4 (today), 6, 8, 10 | Fewer slots mean bigger positions (fixes §2.6) but more concentration, hence DD. More slots diversify but create tiny positions unless fractional shares exist | Fractional answer |
| L3 | Sizing | equal slots (today); volatility-scaled (inverse ATR%); risk-parity across ETFs | Vol-scaling cuts DD from wild names | Pure math |
| L4 | Entry | limit 0.5 ATR below the close (today); limit at the close; buy at the open (or a marketable limit) | Dip-limits fill on bad days (adverse selection). Open entries fill nearly always and keep exposure up (§2.3) | Market-on-open answer |
| L5 | Exit structure | fixed bracket (today); SL-only, no TP (let winners run); **signal exit** ("sell at next open when close < SMA(N)" or "rank falls out of the top K"); **scheduled rebalance** (weekly or monthly target holdings) | The TP caps winners at +1 ATR while losers run to −1.5 ATR. Signal and rebalance exits suit momentum and trend | A new sim path (D2): exit intents from the strategy, and a rebalance mode |
| L6 | Rebalance cadence | nightly (today), weekly, monthly | Monthly cuts turnover about 20× vs nightly | Owner's habit answer |
| L7 | Idle cash | 0% (today); a T-bill ETF; SPY as a "core" (satellite strategy on top) | A T-bill yield adds a few % in some years. A SPY core fixes exposure (§2.3) but inherits SPY's DD unless it is itself timed | ETF answer |
| L8 | Dividends | none (today); credited on ex-date (D11) | Fair comparison with SPY TR on long holds | yfinance dividends; sim change |
| L9 | Universe | S&P 500 ∪ NDX (today); + broad ETFs (SPY, QQQ, IWM, DIA); + sector SPDRs (XLK, XLF, XLE, XLV, XLY, XLP, XLI, XLB, XLU, plus XLRE/XLC from launch); + defensive ETFs (TLT, IEF, SHY, GLD, BIL); + leveraged ETFs | ETFs enable rotation and defensive switching, the main way to cut DD without leaving the market for good. They have no survivorship bias | ETF answer; research store (D5) |
| L10 | Portfolio exposure switch | always allowed (today); all to cash or defensive when SPY is below its 200-day SMA (or 10-month SMA, or 12-month absolute momentum < T-bills) | The classic DD cutter. It historically sidestepped much of 2001–02, 2008 and 2022, and it whipsaws in V-shaped crashes like 2020 | Pure math on SPY bars |
| L11 | Volatility targeting | fixed exposure (today); scale total exposure to a target volatility (for example 12%), capped at 100% | Cuts exposure when markets are wild, which is when big drawdowns happen | Pure math |
| L12 | Costs | 0.1% per side (today); the verified Gotrade number | Monthly strategies hardly care; nightly ones live or die by it | Fee answer |

### 4.B Strategy families to put through the levers

| # | Family | What it does | Why it might pass | Watch-outs |
|---|---|---|---|---|
| F1 | **Trend-timed index** | Hold SPY (or QQQ) while it is above its 200-day / 10-month SMA, otherwise T-bills or cash. Checked daily or monthly | About the simplest known DD reducer. Holding QQQ instead of SPY adds return in tech-led eras | Lags SPY in bull markets with sharp dips. Whipsaw costs. Return may fall short of SPY |
| F2 | **Dual momentum (GEM-style)** | Monthly: if US stocks beat T-bills over 12 months, hold the stronger of US and international stocks (or of SPY and QQQ); otherwise bonds | Published long-history results show lower DD than SPY with similar return | Few instruments. One bad switch hurts. Needs ETFs |
| F3 | **Sector / ETF rotation by momentum** | Monthly: hold the top K of the sector SPDRs by 3–12 month momentum, with an absolute-momentum or trend filter to cash or bonds | Rides leadership, and the filter cuts DD | Needs sector ETFs (sector SPDRs from 1998, so the dev window works) |
| F4 | **Cross-sectional stock momentum** | Monthly: buy the top N large caps by 12-1 month return (skipping the last month), with or without a market trend filter (L10) and vol-scaling (L3) | One of the most documented equity effects, and suited to long holds and low turnover | Momentum crashes (2009). Survivorship flatters it most of all (D4). Concentrated N=4 gives a high DD |
| F5 | **Low-volatility / defensive stocks** | Monthly: hold the N least volatile large caps, maybe with a trend filter | Smaller drawdowns are the whole point | Usually lags SPY in strong bull markets, so beating SPY is the hard part |
| F6 | **Combined momentum + low vol + trend filter** | Rank by momentum among lower-volatility names, and step aside when SPY is below trend | Aims at both gate items at once | More parameters means more overfitting risk, so it counts as several candidates (D6) |
| F7 | **Longer-horizon mean reversion** | A's idea under L1, L4 and L5: buy the oversold in an uptrend, exit by signal (close > SMA(5) or RSI recovery) or after 10–20 days, no TP | Tests whether A failed because of its trade shape rather than its idea | Must be a new candidate, never A re-run (D12) |
| F8 | **Learned ranker, longer horizon** | B's machinery with a target of 20-day or monthly forward return, net of costs, under monthly rebalancing, plus a market-exposure model (§2.5 says timing is where the signal was) | Reuses P6a's machinery; a monthly horizon is less noisy | More complex. Dev-window training data is survivor-biased (D4) |
| F9 | **Core plus satellite** | Hold a trend-timed SPY or QQQ core (F1) in idle slots, with a small stock-picking satellite | Keeps exposure up and DD down when the core is timed | Two moving parts. Measure whether the satellite adds anything over F1 alone |
| F10 | **Leveraged trend** | Hold 2× index ETFs (SSO or QLD) only while above trend, else T-bills | The extra return could clear SPY | Leverage decay. A drawdown above 15% is likely even with the filter. **Owner must explicitly allow leverage**; default is excluded |
| F11 | **Calendar / seasonality** | Turn-of-month, "sell in May", pre-holiday effects on SPY or QQQ | Cheap and low exposure, so DD is lower | Weak, decaying effects. Mainly a combiner |
| F12 | **Earnings / news drift** | Post-earnings drift on surprises (Finnhub free tier has an earnings calendar) | A documented effect, with short-to-medium holds | History before 2015 is hard to get free, which makes a dev-window test weak. Probably later, not in P7a |

### 4.C Validation options (already decided above; listed so the menu is complete)

- Anchored or rolling walk-forward inside the dev window: the analysis picks per family. Fixed-
  parameter candidates need no inner tuning at all.
- The deflated Sharpe ratio, or the probability of backtest overfitting, as a multiple-testing
  note in the dev report (D7).
- Bootstrap or block-resampled DD distributions per finalist (information only).
- Forward paper trading is still the final judge (§1 items 1–4) after P7b.

### 4.D Things outside (c), not taken (for the owner's awareness only)

- **§1 item 5 interpretation.** §1 item 5 says "passed a 10-year backtest under identical rules"
  without defining "passed". ROADMAP P3 applied items 2–4's thresholds (beat SPY, PF, DD) to the
  backtest. That reading has been the gate since P3. Changing it would be the owner's decision
  under (b) or §1. **This handover keeps it.**
- **(b)** SPY buy-and-hold as the champion, and **(d)** Strategy C as forward-paper only, are still
  available whatever P7 finds.

---

## 5. Verified facts (2026-10-03): trust these

**Main.** P6a is on `main` @ `2086664`. The prune commit `2a73f9c` sits on top. The suite was
green at the landing.

**Reusable engine pieces:**
- `runner.ParamsSchedule`, `run_backtest`, `survivorship`;
- `walkforward.folds`, `diagnostics`, `window_metrics`, `curve_window_metrics`;
- `metrics.*`, `benchmark.spy_curves` (SPY price-only and total-return with dividends);
- `backtest.io.load_market` with its pickle cache;
- `strategies.indicators` (SMA, Wilder RSI, Wilder ATR, mean dollar volume, mean, stdev of
  returns), all under the bit-identity rule;
- B's `b_model` (tree and ridge, digest identity), `labels.label_orders`, `b_walkforward`.

**Simulator rules today** (`seer_engine/sim`):
- 4 slots, equity ÷ 4, whole shares;
- strict-low limit fill at min(open, limit), on the order session only;
- SL before TP;
- gaps exit at the open;
- time stop at the next open once `days_held ≥ 5`;
- 0.1% per side;
- a forced close at the last close once a symbol's bars end;
- **no dividends** and **no signal exits**.

**Data:**
- `bars`: 1,817,429 rows, 663 symbols, 2015-01-02 → 2026-10-02.
- `engine/data/sp500_history.csv` from 1996-01-02.
- `ndx_history.csv` from 2007-02-01.
- `spy_dividends.csv` from 2015-03-20 only. The dev window needs older SPY dividends from yfinance,
  or the benchmark is wrong there.

**Massive free tier** reaches about 2 years back. yfinance is the only free source for older bars,
and it has no delisted tickers.

**Benchmark** (`benchmark.spy_curves`): buy SPY at the first session's open with whole shares,
after 0.1% cost. The total-return curve reinvests dividends per the vendored file.

**SPY total return 2018-01-02 → 2026-10-02:** +187.6%, CAGR 12.8%, max DD 30.2%. Price-only:
+169.0%, max DD 31.4%.

---

## 6. Environment

Unchanged from `docs/handover/2026-10-03-strategy-b-ranker.md` §5:
- **Shell:** WSL2 Ubuntu, zsh. Python 3.11 via pyenv, no `uv`.
- **Worktree venv:** a worktree needs its own `engine/.venv`:
  `python3 -m venv engine/.venv && engine/.venv/bin/pip install -e 'engine[dev]'`.
- **Tests:** `docker start seer-pg`, then
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres engine/.venv/bin/pytest engine/tests -q`.
  It must report 0 skipped.
- **Real runs:** from a worktree, set `SEER_ENV_FILE=/home/miftah/seer/.env.local`. Never `source`
  it.
- **yfinance downloads:** they are network calls, so they belong in an impure command (like
  `backfill`). Be polite: batch the downloads and cache them in the research store (D5), so the
  dev runs never touch the network.
- The repo is public on purpose. Losing reports are published too.

---

## 7. Acceptance criteria (P7a)

1. **`TradeRules`:**
   - `DESIGN_V0` reproduces today's §5. With `DESIGN_V0`, the A, A2 and B reports re-render
     **byte-identically** on the same data. That is checked by a test on synthetic data and by a
     real-data `cmp` of all committed `docs/backtests/2026-10-02-*` files.
   - Each new lever has its own synthetic-bar tests:
     - signal exit at the next open;
     - rebalance to target holdings;
     - dividends on ex-date;
     - fractional shares;
     - market-on-open entry;
     - slots ≠ 4;
     - time stop ≠ 5 or none;
     - vol-scaled sizing;
     - idle cash in a T-bill instrument.
2. **Research data:**
   - a command builds the local research store: pre-2015 member bars, the ETF set from L9, and
     dividends for every ETF and for SPY back to the start;
   - it records what yfinance could not serve, per year;
   - nothing is written to Neon;
   - the store is deterministic: the same downloads give the same files, and a fingerprint is
     recorded.
3. **No look-ahead and P4 identity** for every new strategy family: changing any bar dated ≥ S
   leaves S's decisions unchanged. Prepared and single-window paths agree wherever a strategy has
   both.
4. **The dev window is enforced in code:** the dev runner rejects any session after 2015-10-16,
   and a test proves it.
5. **The candidate registry** is committed **before** the dev runs, as appended entries with
   their commit order preserved. It holds ≤ 60 entries, each with a family, `TradeRules`, fixed
   parameters, a rationale and a `needs-owner-verification` flag.
6. **One dev run over every registry candidate.** The committed report
   `docs/backtests/<run date>-p7a-dev-exploration.md` + `.csv` + frontier `.svg` contains:
   - every candidate's row (D7);
   - SPY price-only and total-return curves on the dev window;
   - year by year for the top candidates;
   - exposure, turnover and cost drag per candidate;
   - the survivorship table (D4);
   - the trial count and the multiple-testing note;
   - the finalist rule (D8) applied, in one sentence per finalist or "none eligible".
7. **The pre-registration file** `docs/plans/<date>-p7b-preregistration.md`. It names each
   finalist exactly: code IDs, `TradeRules` values, parameters, instruments, the test window, the
   gate, and the proposed design-§5 revision text. Or it states that none was eligible.
8. **Determinism and purity:** `==` results and byte-identical files on a re-run, and the new
   pure modules pass the purity glob.
9. **Docs:**
   - `engine/package_readme.md` documents `TradeRules`, the new sim paths, the research store
     command, the dev runner and the families;
   - `docs/ROADMAP.md` gets a **P7a** entry with the result, and a **P7b** entry: "run the
     pre-registered finalists once on the test window", or "not run: none eligible".

   The suite is green with 0 skipped, and CI is green.

---

## 8. Open questions for the analysis to settle (recommend, don't ask open-ended)

- **How much the simulator changes.** One generalized lifecycle with a `TradeRules` value, or the
  existing bracket simulator kept intact plus a second, **rebalance-mode** portfolio simulator for
  F1–F6? Recommended: keep `sim.step` exactly as it is for `DESIGN_V0` and bracket-style rule sets,
  and add a separate pure `sim.rebalance` path for target-weight strategies. They share the cost,
  sizing and dividend helpers, and the runner dispatches on `TradeRules`. Prove `DESIGN_V0`
  byte-identity either way.
- **Strategy interface for rebalance strategies.** `picks(...)` returns brackets. A rebalance
  strategy returns target holdings (symbol → weight, or slots). Recommended: a second protocol,
  `Allocator.targets(history, members, data_date, params) -> dict[str, float]`, with the same
  purity and P4 identity contract.
- **Registry format.** Recommended: a Python module (`backtest/registry.py`) holding a tuple of
  frozen `Candidate` values. It is typed, testable and diff-able. The commit history proves the
  append order, and a test asserts the tuple only grows relative to the last released version.
- **Which candidates.** The analysis proposes the first registry from §4 within the cap of 60.
  Recommended shape: about 6–10 families, 3–6 fixed variants each, conservative-default
  instruments first, and `needs-owner-verification` entries marked.
- **ETF data before an ETF's launch.** Recommended: a candidate's dev window starts where **all**
  its instruments have ≥ 200 bars. The report shows each candidate's own window, and the
  comparison with SPY uses that same window.
- **The T-bill proxy before BIL (2007).** Recommended: idle cash earns 0% before BIL exists, or
  use IEF/SHY if the candidate allows. Never use a made-up yield series.
- **Dividends for single stocks pre-2015.** Recommended: from yfinance per symbol, cached in the
  research store. Where yfinance has none, the dividend is 0 and is counted in the report.
- **Splits pre-2015.** Verify how the existing backfill handles split adjustment, and do the same
  for the research store. yfinance's auto-adjust differs from our `bars` convention.
- **Runtime and memory** for about 15 dev years × up to 1,000 symbols × 60 candidates. Measure,
  then decide caching and preparation per family.
- **Phase split.** This is large: the rules engine, the research data, maybe 6–10 strategy
  families, the dev runner and report, and the registry. The analysis should make it many small
  phases, as it did for P3b (6 phases) and P6a (7 phases), and keep the families in phases of
  their own, so each is reviewable alone.

---

## 9. After P7a (not part of it)

- **P7b:** run the ≤ 3 finalists once on 2015-10-19 → data end, with the §1 gate. It gets its own
  handover, written from P7a's pre-registration file.
  - On a pass: edit design §5, freeze the finalist, and P4 starts with it. Forward paper is still
    the final judge.
  - On a fail: the owner decides again, with the dev frontier in hand. That frontier shows what
    drawdown was reachable at a SPY-beating return, which is the honest evidence for (b) or a §1
    discussion.
- **If none was eligible on dev:** P7b does not run, and the owner has the frontier to decide with.
  That is also a real result: it says the go-live bar cannot be met by these families on 25 years
  of US data, and SPY buy-and-hold is the honest champion until something new is found.
