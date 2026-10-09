# Seer

**Strategic Econometric Ensemble Resolver** — a one-person quantitative trading lab that runs
itself: it searches for a stock-picking rule that beats the S&P 500, proves or disproves each one
on paper before a single rupiah is risked, and tells its owner exactly what to type into his
broker app each morning.

Seer is not a prediction engine. It is a **disproving** engine. Its design goal, written before any
code, is to kill bad strategies cheaply — so that the one that survives is worth real money.

<p align="center">
  <img src="docs/media/today.gif" alt="Today: tonight's picks with a copyable limit / take-profit / stop-loss ticket, and the plain-language reason behind each one" width="100%">
</p>

<p align="center">
  <sub>Live at <a href="https://seertrade.site">seertrade.site</a> · private to one Google account ·
  every screenshot below is generated from this repo (<a href="#reproducing-the-screenshots-and-gifs">how</a>)</sub>
</p>

---

## Table of contents

- [What Seer does](#what-seer-does)
- [The product, in four screens](#the-product-in-four-screens)
  - [Today: the ticket you copy into your broker](#today-the-ticket-you-copy-into-your-broker)
  - [Positions: every strategy, one tap apart](#positions-every-strategy-one-tap-apart)
  - [History: every closed trade, and what the night did](#history-every-closed-trade-and-what-the-night-did)
  - [Leaderboard: the honest scoreboard](#leaderboard-the-honest-scoreboard)
- [Sera: the method lab](#sera-the-method-lab)
- [Sean: the real-money tracker](#sean-the-real-money-tracker)
- [On a phone](#on-a-phone)
- [What makes Seer different](#what-makes-seer-different)
  - [1. Pre-registration, enforced by git](#1-pre-registration-enforced-by-git)
  - [2. A luck gate, not just a profit gate](#2-a-luck-gate-not-just-a-profit-gate)
  - [3. The test window is a budget, not a dataset](#3-the-test-window-is-a-budget-not-a-dataset)
  - [4. One simulator for backtest and live](#4-one-simulator-for-backtest-and-live)
  - [5. Real broker fees, measured off real receipts](#5-real-broker-fees-measured-off-real-receipts)
  - [6. Survivorship bias is measured, not waved away](#6-survivorship-bias-is-measured-not-waved-away)
  - [7. The UI is allowed to say no](#7-the-ui-is-allowed-to-say-no)
  - [8. The night is replayable](#8-the-night-is-replayable)
  - [9. Research that runs without a human](#9-research-that-runs-without-a-human)
  - [10. It closes the loop to actual money](#10-it-closes-the-loop-to-actual-money)
- [How it works](#how-it-works)
  - [Architecture](#architecture)
  - [One night, step by step](#one-night-step-by-step)
  - [Scheduled jobs](#scheduled-jobs)
- [The research pipeline](#the-research-pipeline)
  - [The gate a method must pass](#the-gate-a-method-must-pass)
  - [The method lab](#the-method-lab)
  - [Where the search stands](#where-the-search-stands)
- [Data](#data)
- [Repository layout](#repository-layout)
- [Running it yourself](#running-it-yourself)
  - [Prerequisites](#prerequisites)
  - [Setup](#setup)
  - [Demo data](#demo-data)
  - [Reproducing the screenshots and GIFs](#reproducing-the-screenshots-and-gifs)
  - [The engine CLI](#the-engine-cli)
- [Tests and CI](#tests-and-ci)
- [Project status](#project-status)
- [Design documents](#design-documents)

---

## What Seer does

Every night, while the owner sleeps in Jakarta, a GitHub Actions cron job wakes up after the New
York close and does this:

1. pulls the day's end-of-day bars for the S&P 500 ∪ Nasdaq-100, plus dividends and USD/IDR;
2. settles yesterday's simulated orders for every strategy on the roster — fills, take-profits,
   stop-losses, time stops, gaps;
3. asks each strategy what it wants to own for the *next* session;
4. reads the news on each candidate and lets an LLM veto any of them;
5. writes an explanation, in plain words, for every pick;
6. commits the whole night in one database transaction.

In the morning the owner opens a web page on his phone and sees up to four stocks, each with a
limit price, a take-profit, a stop-loss and a share count that map 1:1 onto a bracket order ticket
in his broker's app. Tap, copy, paste. Everything else — the leaderboard, the research lab, the
real-money tracker — exists to decide whether that ticket deserves to be typed at all.

**It runs on free tiers.** Vercel Hobby, Neon Postgres, GitHub Actions cron, Massive's free market
data plan, Finnhub's free news plan. No server is rented and nothing scales beyond one user; the
only recurring costs are the domain and the LLM tokens the nightly explanation step spends.

---

## The product, in four screens

> All the screenshots in this section run on **generated demo data** (note the `Demo data` pill) —
> see [Demo data](#demo-data) for the one command that produces it.

### Today: the ticket you copy into your broker

![Today](docs/media/today.png)

Four slots, equity ÷ 4 each, whole shares, recomputed daily. Each card carries the exact numbers
the broker's bracket ticket wants, each with its own copy button, plus the estimated cost, profit
and loss in **both USD and rupiah** — because that is the currency the owner actually thinks in.
A slot nobody qualified for says so rather than reaching for a fifth-best idea.

The coral bar at the top is the one thing a brokerage cannot do for you: the 5-day time stop is not
an order type, so Seer reminds you, and the reminder stays until you dismiss it.

"Why this pick" expands into either the LLM's plain-language explanation or, if the model was
unavailable, the raw facts the rule used. It never fabricates a reason.

### Positions: every strategy, one tap apart

![Positions](docs/media/positions-bracket.png)

<p align="center">
  <img src="docs/media/roster.gif" alt="Switching between roster strategies with a single icon: each keeps its own portfolio, clock and paper label" width="90%">
</p>

Every strategy on the roster runs its own independent portfolio with its own start date and its own
clock. One icon switches between them. Bracket strategies show four slot cards with a live
stop/target rail; basket strategies show their whole book.

![A monthly basket strategy's positions](docs/media/positions-book.png)

Research strategies are labelled **Paper** everywhere their orders, holdings or trades appear.
There is no screen on which simulated money can be mistaken for real money.

### History: every closed trade, and what the night did

![History](docs/media/history.png)

Closed trades for both engines, filterable by strategy and by win/loss, with the exit reason named:
target, stop, day 5, gap, signal, forced. The second tab is the **Activity** log — every buy and
sell the paper books actually made, with the fees each one paid.

![Activity](docs/media/history-activity.png)

### Leaderboard: the honest scoreboard

![Leaderboard](docs/media/leaderboard.png)

Equity curves against total-return SPY over the window the strategies actually share, a crown on
the champion, and — the part most dashboards omit — a **go-live checklist** whose job is to fail.
Its rules were fixed in the design document before any strategy existed:

| # | Rule | Where it comes from |
|---|---|---|
| 1 | ≥ 18 months of forward paper trading | design §1, revised 2026-10-07 |
| 2 | Beats SPY buy-and-hold over the same forward period | design §1 |
| 3 | Profit factor ≥ 1.3 | design §1 |
| 4 | Max drawdown ≤ 20% | design §1, revised 2026-10-07 |
| 5 | Passed a 10-year backtest under identical rules | design §1; *not applicable* ⇒ not passed |

A strategy that fails any of them cannot be recommended for real money, and the page says which one
it failed and by how much. Changing a threshold takes a dated owner revision in the design
document — not an edit to a constant. The drawdown bar is the clearest case: a test asserts the
number the leaderboard judges by equals the one in the lab snapshot, so the app can never score a
strategy at a bar the engine has abandoned.

---

## Sera: the method lab

**Sera** (`/sera`) is the research half of the system: a desktop-first site over a committed
SQLite database of every idea the lab has ever tried, every run of every variant, and every
conclusion drawn from them.

<p align="center">
  <img src="docs/media/sera.gif" alt="Sera: the lab overview, the hurdle scatter, the methods list, and one method's page with its pre-registered hypothesis" width="100%">
</p>

![Sera overview](docs/media/sera-overview.png)

The Overview is a state-of-the-search report: how many methods have been tried, how many *tries*
that is (the number that deflates every result), how many of the precious test-window looks have
been spent, the closest any method has come, and the best SPY-beating return achieved at an
acceptable drawdown.

![A method page](docs/media/sera-method.png)

Each method gets a page, and each page leads with two panels written **before the method was ever
run**: *The idea* and *What could go wrong*. A failure that was predicted in advance teaches
something; a failure explained afterwards teaches nothing. The rest of the page is the evidence:
the method's variants plotted against the hurdles, equity against SPY, every variant's row, the
analysis in plain language, and an opinion that ends with a recommendation.

| | |
|---|---|
| ![Methods](docs/media/sera-methods.png) | ![Journal](docs/media/sera-journal.png) |
| **Methods** — every method the lab has touched, with its verdict | **Journal** — every insight, with unread badges |
| ![Ideas](docs/media/sera-ideas.png) | ![How it works](docs/media/sera-how.png) |
| **Ideas** — the backlog, the blocked-on-data wishlist, the reading list | **How it works** — the path, the calendar, the hurdles, the honesty rules |

Every chart on these pages is hand-built SVG — a dependency-free chart kit of about a thousand
lines, because a 300 kB charting library for a private research site is a bad trade.

---

## Sean: the real-money tracker

**Sean** (`/sean`) is where the loop closes. The paper roster is simulated; Sean tracks what the
owner *actually* bought, from the only artefact his broker gives him: a screenshot of the "Order
Summary".

<p align="center">
  <img src="docs/media/sean.gif" alt="Sean: real profit and loss from broker receipts, the order ledger with its fees, and the plan's buy/sell reminders" width="100%">
</p>

![Sean overview](docs/media/sean-overview.png)

Drop the screenshots in — or a zip of them — and a vision model reads each receipt into numbers,
which are then **arithmetically checked** against each other before anything is stored. The image
itself is thrown away; only its SHA-256 is kept, so re-uploading the same screenshot is a no-op.
Partial fills, duplicate receipts of one order, and a model that returns something unparseable are
all handled explicitly rather than hopefully.

![Sean trades](docs/media/sean-trades.png)

From there Sean keeps an average-cost ledger with fees inside the cost basis, marks the holdings to
market every night, and plots real profit and loss — split into what is locked in, what is still
moving, and what the fees have taken.

![Sean plan](docs/media/sean-plan.png)

The **Plan** tab follows one roster method and turns the gap between its picks and your real
holdings into a short to-do list, sized in dollars against your holdings *plus* a derived cash
balance (a broker receipt never shows a balance, so the wallet is reconstructed from the owner's
deposit schedule minus what the plan's own orders spent). Holdings bought before the plan started
are never sold by it, and an order can be claimed as personal so its shares leave the plan without
touching the cash.

> The ledger arithmetic exists twice — once in TypeScript for the web, once in Python for the
> nightly job — and both are replayed against **one shared fixture file** in CI, so the two halves
> cannot drift apart.

---

## On a phone

The whole app is mobile-first — it was designed for an iPhone XS Max, installed to the home screen
as a PWA — and every button is icon-only with an `aria-label` and a tooltip.

| Today | Positions | Leaderboard | Sean |
|---|---|---|---|
| ![Today on a phone](docs/media/phone-today.png) | ![Positions on a phone](docs/media/phone-positions.png) | ![Leaderboard on a phone](docs/media/phone-leaderboard.png) | ![Sean on a phone](docs/media/phone-sean.png) |

Light mode is a first-class citizen, not an afterthought:

| | |
|---|---|
| ![Today in light mode](docs/media/today-light.png) | ![Sera in light mode](docs/media/sera-overview-light.png) |

The screenshot tool that produced every image on this page **fails the build on horizontal scroll
at any width** — which is how a bug that pushed a Fees column 51 px off the right edge of a phone
was caught, after a review that had read the rendered HTML and seen nothing wrong with it.

---

## What makes Seer different

Most hobby trading projects are a backtest and a dashboard. The interesting part of this one is
everything built to stop its owner from fooling himself.

### 1. Pre-registration, enforced by git

A method is a Python file with a hypothesis and a predicted failure mode written in prose. It must
be **committed and pushed before `lab run` is allowed to touch the data**. The run records the
commit it ran at. There is no path by which a result can be produced first and a story attached to
it afterwards — which is the single most common way a backtest lies.

### 2. A luck gate, not just a profit gate

Beating the market once in 127 tries is not evidence; it is arithmetic. Every trial is scored with
a **deflated Sharpe ratio** that discounts for how many times the lab has looked, and a method must
reach DSR ≥ 0.90 at the current N *on top of* every profit hurdle. N is measured, not asserted: it
counts distinct methods, floored at the participation ratio computed from the actual pairwise
correlation of all the stored equity curves. Each recorded trial keeps the N it was scored at, so
the bar visibly rises as the search goes on.

### 3. The test window is a budget, not a dataset

The data is split once: a **development window** (1993 → 2015-10-16) where anything may be tried as
often as you like, and a **test window** (2015-10-19 → today) that is spent one counted look at a
time, only by promoting a method that already cleared every hurdle on development data. Two looks
have been spent. The split is enforced in code, not by discipline — the research store physically
refuses to serve a dev caller a test-window store.

### 4. One simulator for backtest and live

The fill simulator is the highest-priority code in the repo and has exhaustive unit tests on
synthetic bars: touch versus penetrate, gaps through either side, take-profit and stop-loss in the
same bar (stop wins), time stops, holidays, whole-share sizing, slot arithmetic. The nightly paper
job and the ten-year backtest call **the same code path**, so "it worked in the backtest" and "it
works live" cannot diverge quietly.

### 5. Real broker fees, measured off real receipts

The original cost assumption was a round 0.1% per side. It was replaced by the broker's actual fee
schedule — four dated regimes, each with its own trading rate and minimum, a regulatory fee that
rounds *up* and is capped, an extra charge that applies only to sells, and VAT on top that rounds
*half-down* — all reverse-engineered from thirty of the owner's own order receipts and reproduced
to the cent by a test fixture. Methods are re-run against it, and a method that only worked at the
imaginary rate is allowed to fail.

### 6. Survivorship bias is measured, not waved away

The free data source does not serve delisted tickers, which quietly flatters every backtest. Rather
than apologise in a footnote, Seer measures the hazard — how often a member of the index stopped
being priceable, from its own point-in-time membership records — and runs a Monte Carlo stress that
injects delistings at that rate into an in-memory market. The stress module is unit-tested to prove
it *cannot* record a lab trial or spend a test-window look, even by accident.

### 7. The UI is allowed to say no

- SPY buy-and-hold is the reigning champion, so the home screen's main job right now is to say
  **"Seer recommends no buys."**
- Stale data or a failed run shows a do-not-trade state. Picks are never rendered without a
  successful run behind them.
- A pure classifier names *which* of five situations "nothing to act on" is — paper paused, never
  started, the nightly late, the last decision already spent, or simply nothing due — and says in
  the owner's own timezone when the next decision lands.
- An expired decision is kept visible as a *record* with every order-ticket field stripped out, so
  a stale instruction can never be mistaken for a live one.

### 8. The night is replayable

Every night is one transaction and is idempotent per session. A separate `paper_check` command
**re-derives every fill, exit and equity snapshot from the stored bars and rules** and asserts the
database agrees — including replaying the LLM's news verdicts from the stored headlines rather than
asking the model again. The release gate for v0.1.0 is `paper_check --require-sessions 5` passing
on the production database.

### 9. Research that runs without a human

Two skills drive the lab end to end with nobody in the loop: one explores a single idea
(pre-register → run → plain-language analysis → at least one insight → at least one queued idea),
and one fans out several of those in parallel, each in its own git worktree and terminal window,
promotes what qualifies, and closes the batch with a synthesis. Every roster change, promotion and
rejection is journalled.

### 10. It closes the loop to actual money

Most projects stop at the backtest. Seer goes all the way to *"you hold 1.86 shares of INTC at an
average cost of $31.755, the method wants $71.24 of KMI that you do not own, and your spare cash
covers it."* And when a swap between two personal holdings confused the plan into thinking it owned
shares it never paid for, the fix was a schema change and a written rationale — not a hard-coded
exception.

---

## How it works

### Architecture

```
GitHub Actions  (cron, ~06:17 UTC Tue–Sat, Python)
   1  fetch EOD bars + dividends + USD/IDR        →  Neon
   2  settle every roster strategy's open orders
   3  each strategy proposes next session's picks
   4  news check: LLM may veto a candidate
   5  LLM writes a plain-language reason per pick
   6  mark the owner's real holdings to market
        │                                    one transaction per night
        ▼
Neon Postgres   (single source of truth, 20 migrations)
        │
        ▼
Vercel / Next.js 16   —  the UI  —  seertrade.site
                         Seer's four screens and Sera are a pure read model
                         (plus dismissals and read-receipts); Sean owns its
                         own tables and is the one section that writes

lab/lab.sqlite  (committed, append-only)  →  web/data/lab.json  →  /sera
```

Compute lives in GitHub Actions because it is free, has no function timeout and speaks Python.
Vercel only renders; **it never computes a signal**. No page can trade, and no page can move a
number the engine wrote.

### One night, step by step

| Step | What it does | On failure |
|---|---|---|
| Bars | Grouped-daily for the whole market in one call, plus dividends and held-symbol bars | Retry, then mark the run failed; the UI shows do-not-trade |
| Paper | Settle, then decide, for every roster strategy, in one transaction | Night is rolled back; no partial state |
| Paper check | Replay the night from stored bars and assert the database agrees | Loud failure in the run log |
| Veto | Up to 20 headlines from the last 3 days plus earnings dates, under a frozen prompt | Any failure is a `failed` verdict, which means **no trade** |
| Explain | A plain-language reason per pick | Explanation reads "unavailable"; the pick stands |
| Sean marks | Mark the owner's real holdings and rebuild his P&L series | Graph lags one night |

Decisions for session *S* read data only through `prev_session(S)`. Look-ahead is prevented by the
date arithmetic, not by care.

### Scheduled jobs

| Workflow | When | What |
|---|---|---|
| `nightly.yml` | 06:17 UTC Tue–Sat, retries 09:41 and 12:41 | The night above. Every retry is a no-op once the session has succeeded |
| `universe.yml` | 00:30 UTC Monday | Refresh point-in-time index membership |
| `watch.yml` | daily | Five facts to the owner's phone over Telegram: session stepped, picks published, news check done, CI green, paper paused |
| `sean.yml` | on demand | Re-mark real holdings right after a receipt upload |
| `repick.yml` | on demand | Re-take waiting decisions after the owner edits what the broker will not sell |
| `backfill.yml` | on demand | Ten-year historical backfill |
| `engine-ci.yml` | every push | Lint, type-check and both test suites |

`watch.yml` is deliberately a *separate* workflow: a step inside the nightly cannot report that the
nightly never ran.

---

## The research pipeline

### The gate a method must pass

A method is **dev-eligible** only when all six hold on the development window:

| Hurdle | Bar |
|---|---|
| Beats total-return SPY | over its own window |
| Max drawdown | ≤ 20% |
| Profit factor | ≥ 1.3 |
| Closed trades | ≥ 100 |
| Owner inputs required | none |
| Deflated Sharpe ratio | ≥ 0.90 at the current N |

Only then may it be promoted, and a promotion spends one of the finite test-window looks.

### The method lab

`lab/lab.sqlite` is committed to the repository. Trials and insights are **append-only, enforced by
SQLite triggers** — a verdict can never be quietly rewritten. The engine stages a JSON snapshot of
it under the database's write lock on every lab commit, a CI test fails any commit whose JSON does
not match its database, and the site reads only that snapshot.

```
idea  →  pre-registered file (committed)  →  dev run  →  verdict
                                                 │
                                        dev-eligible?  →  promote  →  one test-window look
                                                 │                          │
                                              rejected                 pass / fail
                                                                            │
                                                                     forward paper
                                                                            │
                                                                       18 months
                                                                            │
                                                                       real money
```

### Where the search stands

As of the committed snapshot (2026-10-08):

| | |
|---|---|
| Methods on record | **47** — 33 from the lab, 14 from the search that preceded it |
| of which still only an idea | 15 |
| of which carry a verdict | 32 (22 rejected, 8 dev-eligible, 2 failed their final test) |
| Distinct methods with a development trial | **29** — this is the N every result is deflated by |
| Development trials | **127** |
| Test-window looks spent | **2** of a finite budget |
| Insights journalled | **55** |
| Methods that have passed the full gate | **0** |

Zero. That number is the point. A market-beating claim would have been easy to manufacture out of
127 tries, and none of them would have been true. SPY buy-and-hold is still the champion, and the
home screen says so.

---

## Data

| What | Source | Note |
|---|---|---|
| Nightly EOD bars | Massive (ex-Polygon) free tier | Grouped-daily: the whole market in one call |
| 10-year backfill | yfinance, one-off | Free, unofficial; no delisted tickers — hence the survivorship stress |
| Research store | yfinance + Frankfurter, local and gitignored | 2,490,793 bar rows, 539 of 1,061 symbols served, 28,206 dividends, content-addressed by a manifest fingerprint |
| Index membership | vendored point-in-time CSVs | From 1996-01-02 |
| Fundamentals | SEC EDGAR | Point-in-time company facts |
| News | Finnhub free tier | Up to 20 headlines, last 3 days, published before the step started |
| LLM | GLM via an Anthropic-compatible endpoint | Frozen prompt and model id per strategy |
| FX | Neon `fx_rates`, Frankfurter for research | USD/IDR, so every figure can be read in rupiah |

The research store is **never** Neon: the whole train/evaluate pipeline reads exactly one database
table, which keeps 384 MB of fundamental facts off a 0.5 GB production tier.

---

## Repository layout

```
engine/          Python 3.11 package `seer_engine` — the whole pipeline
  src/seer_engine/
    commands/      one module per CLI subcommand; cli.py never changes
    sim/           the fill simulator, trade rules, Gotrade fees, contributions
    strategies/    A, B, C, the P7a factor families, allocators, evidence
    backtest/      backtest, walk-forward, dev runner, report, registry
    lab/           pre-registration, the N policy, the derived verdict, methods/
    paper/         pure night functions mirroring the runner loop bodies
    sean/          the owner's real ledger (the Python half of contract B)
    fundamentals/  SEC EDGAR facts
  tests/         3,513 tests

web/             Next.js 16 / React 19, app router; a read model over Neon (Sean writes its own)
  app/(app)/       Today, Positions, History, Leaderboard
  app/sera/        the method lab, over a committed JSON snapshot
  app/sean/        the real-money tracker
  components/      shared UI + Sera's own chart kit and SVG diagrams
  lib/             one DB layer; everything else pure and unit-tested
  scripts/         migrate, seed demo data, sign in, screenshot, film

db/migrations/   20 SQL files, applied by either runner (Python or Node)
lab/lab.sqlite   the method lab, committed, append-only
docs/            design, roadmap, plans, handovers, backtest reports, runbooks
.github/         seven workflows
```

Roughly 102,000 lines of Python (source and tests), 22,000 of TypeScript, and about a thousand of
SQL. Nearly every module carries a prose docstring explaining not just what it does but **why it is
shaped that way** — including the bugs that shaped it.

---

## Running it yourself

Seer is built for exactly one user and gates every page behind one allowlisted Google account, so
there is nothing to sign up for. But it runs locally end to end, against a database you own.

### Prerequisites

- Python 3.11, Node 22+, Docker (for the test database)
- A Postgres database — Neon's free tier is what production uses
- A Google OAuth client, for sign-in
- Optional, for the full night: Massive, Finnhub and an LLM endpoint

### Setup

```bash
git clone git@github.com:miftahulmahfuzh/seer.git && cd seer
cp .env.example .env.local      # then fill it in

# engine
python3.11 -m venv engine/.venv
engine/.venv/bin/pip install -e 'engine[dev]'

# database
cd web && npm ci && npm run db:migrate
```

### Demo data

Production starts empty, and an empty app is a bad demo. Two seeders fill a database with a
complete, internally consistent story — three months of paper trading across five strategies, and a
real-money plan mid-rotation:

```bash
cd web
npm run db:seed-demo          # roster, 66 sessions, orders, trades, equity, news vetoes
npm run db:seed-demo-sean     # broker receipts, the ledger, the P&L series, the plan
npm run dev:env               # http://localhost:3111
```

Both refuse to run against a database the real engine has written to, and every row they create is
flagged so the UI wears a `Demo data` pill. The Sean seeder prices every receipt with the **real**
Gotrade fee schedule at the regime in force on each order's date, so the demo's totals are
arithmetic you can check rather than numbers that were typed in.

> Every screenshot and GIF in this README comes from exactly these two commands.
> `/sera`, by contrast, needs no seeding — it reads the committed lab snapshot, so it shows the
> real research.

### Reproducing the screenshots and GIFs

Every page redirects to `/signin`, which used to mean a change could only be proved by tests. Two
scripts fix that, and **neither one waits for a human**: they keep a session in `web/.auth/`, mint
one when there is none, and renew it when it is nearly out.

```bash
cd web
npm run dev:env &

# stills — every page × theme × width, plus the page's own text for diffing
npm run shoot -- --theme dark --width 1280 / /positions /leaderboard /sera /sean

# animation — a little scene language: goto, click, scroll, hold
npm run film -- --out ../docs/media/today.gif --fps 12 --height 900 --scale 900 \
  goto:/ hold:800 'click:button[aria-label="Why this pick"]' hold:300 scroll:380 hold:2200
```

`shoot` exits non-zero on an HTTP error, a redirect to `/signin`, any browser console error, **or
horizontal scroll at any width**. `film` needs `ffmpeg` on the PATH and builds a per-GIF palette,
which is what stops a dark UI from banding.

### The engine CLI

One entry point, whose subcommands are discovered from a directory — adding a command means adding
a module, and the CLI file itself never changes. `--dry-run` runs every read and every write and
then rolls the whole thing back.

```bash
python -m seer_engine [--dry-run] [-v|-vv] <command>
```

| Command | What it does |
|---|---|
| `migrate` | Apply pending SQL migrations, one transaction per file |
| `universe` · `backfill` · `nightly` | Membership, ten-year history, the nightly fetch |
| `paper` · `paper_check` | Run one paper night; replay it and assert the database agrees |
| `veto` · `explain` | The news check; the plain-language reasons |
| `backtest` · `backtest_wf` · `backtest_b` | Strategy A, the walk-forward, the ML ranker |
| `research_store` · `backtest_dev` | Build the local research store; run the dev search |
| `lab run/test/promote/remeasure/reevaluate/luck/status/costs/names` | The method lab |
| `compare` · `promote` | Compare roster candidates; promote one onto the roster |
| `sean marks` · `sean calibrate` | Mark real holdings; calibrate against real receipts |
| `fundamentals` | SEC EDGAR company facts |

---

## Tests and CI

```bash
engine/.venv/bin/pytest engine/tests     # 3,513 tests
cd web && npm test                       # 672 tests across 49 files
```

Every push runs `ruff check` and pytest for the engine, and `tsc --noEmit` plus vitest for the web.
Database tests get a throwaway schema each and are **required** — CI fails the build if they skip
for lack of a database, and it checks that the guard itself still matches the fixture's wording so
the two cannot drift. An autouse fixture points every test at a nonexistent env file and an
`.invalid` database host, so no test can reach production by accident.

Beyond the usual, CI also asserts a set of cross-language invariants:

- the committed `lab.json` matches `lab.sqlite` row for row;
- the web's copy of the engine's constants (the drawdown bar, the contribution schedule, the resize
  band, the fee minimums) equals the engine's own;
- the TypeScript and Python ledgers agree on one shared fixture;
- every argparse help string still formats — a stray `%` once killed `lab --help` for a week with
  nothing to catch it.

---

## Project status

Paper only. No real money is allocated by Seer, and no strategy has passed the backtest gate.

| Phase | State |
|---|---|
| Foundations, data pipeline, fill simulator | Done |
| Strategy A, A-rework, B (ML ranker) | All three failed their gate — reports committed |
| Trade rules as a searchable parameter | 54 candidates, none eligible |
| Method lab + Sera | Running since 2026-10-04; by design it never finishes |
| Nightly forward paper trading | Live; release waits on five clean consecutive sessions |
| Web app | Live at [seertrade.site](https://seertrade.site) |
| Sean, the real-money tracker | Live |

Every failed gate above is written up in full, with its numbers, in `docs/backtests/` and
`docs/handover/`. Nothing is quietly deleted; the record of what did not work *is* the asset.

---

## Design documents

| Document | What it holds |
|---|---|
| [`docs/plans/2026-10-03-seer-design.md`](docs/plans/2026-10-03-seer-design.md) | The design. §1 (the go-live rules) moves only by a dated owner revision |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Every phase, with its verdict |
| [`docs/plans/2026-10-04-method-lab-design.md`](docs/plans/2026-10-04-method-lab-design.md) | The lab, the luck gate, the roster replacement rule |
| [`engine/package_readme.md`](engine/package_readme.md) | The engine's full API, module by module |
| [`web/package_readme.md`](web/package_readme.md) | The web app's full API, module by module |
| [`docs/runbooks/`](docs/runbooks/) | Paper trading, the data pipeline, monitoring |
| [`docs/handover/`](docs/handover/) | One per major piece of work: what was decided and why |

---

<sub>A personal project: one user, one allowlisted account. Not investment advice — and by its own
rules, it is not giving its owner any yet either.</sub>
