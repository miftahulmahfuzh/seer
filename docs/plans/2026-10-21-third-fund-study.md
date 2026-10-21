# What a third permitted fund would buy the lab

Read-only. Dev store `engine/.research` (fingerprint 640fc25e…), bars to 2015-10-16, total return
(split-adjusted close + split-adjusted cash dividends on the ex-date). No lab command was run, no
constant changed, nothing implemented. `lab/lab.sqlite` was copied, not opened in place.

**Calibration.** The pipeline reproduces M0267's pre-registered figures exactly: 191 QQQ month-ends
from 1999-12-31, 126 above the line at +0.2373%/mo, 64 below at −0.7120%/mo, GATE +1.91 / MIRROR
−2.84 / one-sided **+2.41** (M0267 published +1.89 / −2.88 / +2.38; the 0.03 is rounding). Every
number below is on that scale.

---

## 1. Coverage — and the window a method would actually get

`dev.candidate_window` starts a candidate where every symbol it reads has `lookback` bars. At the
gate's 200 bars:

| fund | first bar | window start | years to 2015-10-16 | crashes covered |
|---|---|---|---|---|
| SPY | 1993-01-29 | 1993-11-12 | 21.9 | dot-com, GFC |
| DIA | 1998-01-20 | 1998-11-03 | 17.0 | dot-com, GFC |
| XLE XLF XLK XLP XLU XLV | 1998-12-22 | 1999-10-08 | 16.0 | dot-com, GFC |
| QQQ | 1999-03-10 | 1999-12-22 | 15.8 | dot-com, GFC |
| IWM | 2000-05-26 | 2001-03-14 | 14.6 | **GFC only** |
| EFA | 2001-08-27 | 2002-06-19 | 13.3 | **GFC only** |
| IEF SHY TLT | 2002-07-30 | 2003-05-15 | 12.4 | **GFC only** |
| GLD | 2004-11-18 | 2005-09-06 | 10.1 | **GFC only** |

All four research stores (`.research`, `.research-test`, `.research-sv`, `.research-dv`) carry all
fifteen symbols with identical first bars. **There is no data obstacle anywhere in the pipeline.**

The obstacle is history. Every fund that is genuinely *different* from SPY — the bonds, gold —
arrives after the dot-com crash. A method built on one has **one** crash in the dev window and no
second one to confirm it.

## 2. Correlation and beta to SPY (daily TR log returns, paired sessions)

| fund | whole | 2000-2002 | 2003-2008 | 2009-2015 | stable? |
|---|---|---|---|---|---|
| DIA | β0.91 r0.96 | β0.89 r0.92 | β0.93 r0.97 | β0.89 r0.98 | very |
| QQQ | β1.21 r0.82 | β1.76 r0.82 | β1.00 r0.88 | **β0.98 r0.93** | no — β fell 1.76→0.98 |
| XLK | β1.12 r0.84 | β1.51 r0.83 | β0.99 r0.88 | β0.95 r0.92 | no — tracks QQQ |
| IWM | β1.11 r0.90 | β0.96 r0.87 | β1.09 r0.89 | β1.23 r0.93 | drifting up |
| EFA | β1.03 r0.89 | β0.75 r0.80 | β1.03 r0.90 | β1.14 r0.91 | drifting up |
| XLF | β1.31 r0.83 | β0.97 r0.78 | β1.36 r0.85 | β1.54 r0.87 | no |
| XLE | β0.96 r0.69 | β0.49 r0.42 | β1.15 r0.74 | β1.20 r0.87 | no |
| XLV | β0.72 r0.78 | β0.76 r0.71 | β0.65 r0.80 | β0.75 r0.83 | yes |
| XLP | β0.52 r0.68 | β0.37 r0.42 | β0.53 r0.79 | β0.59 r0.82 | yes |
| XLU | β0.62 r0.64 | β0.49 r0.47 | β0.74 r0.76 | β0.59 r0.69 | fairly |
| **GLD** | **β0.06 r0.06** | n/a | β0.06 r0.07 | β0.05 r0.05 | **yes — orthogonal** |
| **IEF** | **β−0.15 r−0.41** | β−0.20 r−0.72 | β−0.11 r−0.34 | β−0.18 r−0.44 | **yes** |
| **SHY** | β−0.03 r−0.36 | β−0.05 r−0.70 | β−0.03 r−0.38 | β−0.02 r−0.30 | yes (≈cash) |
| **TLT** | **β−0.30 r−0.42** | β−0.28 r−0.65 | β−0.18 r−0.33 | β−0.43 r−0.49 | **yes, sign-stable** |

The 0.98 QQQ beta the brief names is confirmed — and it is a *late* number. QQQ's beta was 1.76 in
2000-2002, which is the whole reason M0267's opinion looked big whole-window.

**What a third fund adds beyond QQQ** — correlation of (fund − SPY) monthly with (QQQ − SPY):
XLK **+0.90** (it *is* QQQ, residual sd 6.2 vs QQQ's 14.3 — permitting it adds nothing), IWM +0.19,
everything else **negative**: XLP −0.60, XLU −0.53, DIA −0.41, XLF −0.39, TLT/IEF −0.32, SHY −0.29,
XLE −0.28, XLV −0.23, GLD −0.18, EFA −0.17. Thirteen of fourteen funds genuinely open a new axis.

## 3. The spread an opinion could capture (monthly, each fund's own window, pts/yr)

`PERFECT` = pick the better of SPY/fund every month with foresight. `WORST` = pick the worse.
`random` = coin flip. The bracket [WORST, PERFECT] is the whole prize.

| fund | buy&hold vs SPY | mean abs monthly diff | sd ann | PERFECT | WORST | random |
|---|---|---|---|---|---|---|
| GLD | +1.36 | 5.13% | 22.8 | **+36.95** | −25.99 | +0.68 |
| TLT | −1.00 | 4.82% | 22.4 | **+32.87** | −25.49 | −0.50 |
| XLE | +3.45 | 3.76% | 17.0 | +27.46 | −18.84 | +1.71 |
| IEF | −2.48 | 3.81% | 17.6 | +24.13 | −21.44 | −1.25 |
| XLU | +1.16 | 3.46% | 15.8 | +23.75 | −18.26 | +0.58 |
| **QQQ** | +0.35 | 3.05% | 16.2 | **+20.29** | −16.58 | +0.17 |
| SHY | −5.61 | 3.29% | 15.0 | +18.36 | −20.25 | −2.85 |
| XLP | +0.96 | 2.61% | 12.5 | +17.49 | −14.07 | +0.48 |
| XLK | −2.19 | 2.76% | 14.6 | +16.68 | −16.17 | −1.10 |
| IWM | +2.93 | 2.15% | 9.5 | +15.45 | −10.84 | +1.46 |
| XLF | −2.74 | 2.60% | 13.3 | +15.28 | −15.63 | −1.38 |
| XLV | +2.47 | 2.16% | 9.5 | +15.22 | −11.07 | +1.23 |
| EFA | −0.83 | 1.91% | 8.6 | +11.69 | −11.21 | −0.41 |
| DIA | +0.65 | 1.02% | 5.1 | +6.64 | −5.62 | +0.32 |

The brief's hypothesis is **confirmed on this axis**: TLT and GLD offer ~1.7x QQQ's prize, and at a
beta of −0.30 / +0.06 instead of +0.98. The instruments really are wider.

## 4. The deciding number — what the lab's one known-real opinion earns through each

The lab's only swept, era-stable opinion is the SPY 200-day gate (3.6 pts/yr over 824 trials).
Wire it risk-off: **hold SPY above the line, hold X below it.** Common window 2005-01..2015-10 so
every fund is live and the columns are comparable. `timing` strips each fund's unconditional
drift, so a fund that simply beat SPY gets no credit for it. **CASH is what the lab already has,
for free, with no owner input.**

| X | buy&hold | arm vs SPY | timing | **arm − CASH** | **timing − CASH** |
|---|---|---|---|---|---|
| **CASH** | −6.57 | **+2.11** | **+3.73** | — | — |
| TBILL (T13W) | −5.38 | +2.27 | +3.59 | +0.16 | −0.14 |
| **TLT** | +0.01 | **+5.63** | **+5.63** | **+3.52** | **+1.90** |
| IEF | −1.49 | +4.48 | +4.84 | +2.36 | +1.11 |
| SHY | −4.41 | +2.86 | +3.94 | +0.75 | +0.21 |
| GLD | +1.93 | +3.23 | +2.78 | +1.12 | −0.95 |
| XLP | +2.82 | +2.24 | +1.59 | +0.13 | −2.14 |
| QQQ | +3.22 | +1.81 | +1.06 | −0.31 | −2.66 |
| XLK | +0.91 | +1.47 | +1.26 | −0.64 | −2.46 |
| XLV | +2.67 | +1.06 | +0.45 | −1.05 | −3.28 |
| XLU | +1.23 | +0.76 | +0.47 | −1.36 | −3.26 |
| DIA | −0.06 | +0.54 | +0.55 | −1.58 | −3.18 |
| IWM | −0.10 | +0.31 | +0.34 | −1.80 | −3.39 |
| XLE | +0.83 | −0.67 | −0.86 | −2.78 | −4.59 |
| EFA | −2.76 | −1.08 | −0.44 | −3.19 | −4.17 |
| XLF | −6.85 | −4.70 | −3.13 | −6.81 | −6.85 |

**Only four funds beat cash as a risk-off leg, and only two by more than a point.**

### Now the era split, which is the whole answer

`timing` contribution by era:

| era | CASH | TLT | IEF | SHY | GLD | QQQ | XLP |
|---|---|---|---|---|---|---|---|
| 2000-2002 | **+3.48** | n/a | n/a | n/a | n/a | −6.40 | −0.44 |
| 2003-2008 | **+6.80** | **+11.37** | +9.01 | +7.22 | +5.37 | +0.89 | +2.24 |
| **2009-2015** | **−0.05** | **−0.20** | **+0.11** | **−0.07** | **+0.77** | +2.02 | −0.59 |

**Post-2009 the gate's timing contribution is zero through every instrument on the menu.** Cash
−0.05, TLT −0.20, IEF +0.11, SHY −0.07, GLD +0.77. The entire gain from a third fund — TLT's whole
+1.90 — is 2003-2008, and inside that it is the GFC.

The gate-arm-vs-SPY figures say the same thing from the other side: in 2009-2015 the gate wired to
cash costs **−2.90 pts/yr** (independently reproducing insight 462's ~3.6-point post-2009 gate
drag); wired to TLT it costs **−2.27**. A third fund repairs 0.6 of a 2.9-point hole. It does not
turn the gate positive post-2009, and the brief's premise — that the instrument spread is what
failed M0265 and M0267 — is only half right. The spread was narrow, **and the opinion was empty in
the era that matters.** Multiplying an edge of ~0 by a 3.5x wider instrument gives ~0.

## 5. The crashes

Total return across the window, and the max drawdown inside it:

| fund | dot-com 2000-03-24→2002-10-09 | max DD | GFC 2007-10-09→2009-03-09 | max DD |
|---|---|---|---|---|
| SPY | −47.5% | −47.5% | −55.2% | −55.2% |
| **GLD** | *no coverage* | — | **+23.9%** | −29.4% |
| **TLT** | *no coverage* | — | **+25.0%** | −16.2% |
| **IEF** | *no coverage* | — | **+20.1%** | −6.2% |
| **SHY** | *no coverage* | — | **+8.8%** | −2.2% |
| XLP | **+1.2%** | −32.9% | −28.5% | −32.4% |
| XLV | −17.2% | −29.8% | −38.3% | −39.2% |
| XLF | −22.2% | −36.6% | **−81.6%** | −81.8% |
| XLE | −23.8% | −41.5% | −47.9% | −57.4% |
| IWM | −26.8% | −38.7% | −58.4% | −58.4% |
| EFA | −29.8% | −29.8% | −60.2% | −61.0% |
| DIA | −31.5% | −33.9% | −51.9% | −51.9% |
| XLU | −35.7% | −52.2% | −42.5% | −46.5% |
| **QQQ** | **−82.9%** | −83.0% | −51.6% | −53.4% |
| XLK | −81.9% | −82.0% | −51.4% | −53.0% |

This is the brief's real case, and it is real: in the GFC, when SPY (−55%) and QQQ (−52%) fell
together, **TLT, IEF, GLD and SHY were the only instruments on the menu that went up.** Summed over
the 18 months of 2008–H1'09 that the gate spent below the line, holding GLD instead of SPY was
worth +52.8%, IEF +52.3%, TLT +50.1%, SHY +48.9% — against XLP +24.1%, XLV +16.4% and QQQ +9.2%.

And this is also its limit: **that is one observation.** None of the four existed during the
dot-com crash, which is the dev window's other crash and the one QQQ was punished by. Every bond
number here is drawn from 2002-2015, which is thirteen years of a secular bond bull market. I did
not look at the test window; public history (not a store read) says 2022 is the one episode where
long bonds and equities fell hard together, and 2022 is inside the test window. That is precisely
the scenario a third fund is wanted for, and the dev window cannot see it.

---

## 6. Recommendation

**Permit nothing — or, if one fund, TLT.** Ranked:

1. **Nothing (recommended).** The measurement does not support the premise. The instruments *are*
   narrow and a wider one *is* available, but the binding constraint on M0265 and M0267 was not the
   spread: it was that neither opinion had post-2009 content. Through the single opinion the lab
   has actually proved (the 200-day gate), every instrument on the menu contributes between −0.2
   and +0.8 pts/yr after 2009, against cash's −0.05. Permitting TLT buys +1.90 pts/yr whole-window,
   all of it from one crash, in a 12.4-year window with no second crash to confirm it, and it still
   leaves the gate at −2.27 pts/yr post-2009 — losing to doing nothing, for the same reason it
   always has. The honest sentence is: *a third fund does not fix a rule that has nothing to say.*

2. **TLT**, if the owner wants the option anyway. It is the best of them on every axis that
   matters and the cheapest to permit: largest prize (PERFECT +32.9), most negative and most
   sign-stable beta (−0.18 to −0.43, never positive in any era), best gate-wired arm (+5.63 vs
   SPY, +3.52 over cash), best 2003-2008 timing (+11.37), only +25% in the GFC, pays dividends the
   store already holds (157 of them), and — see §7 — it is the only strong candidate that collides
   with no frozen record. Trade-offs, stated: window shrinks to 12.4 years, dot-com invisible,
   every number drawn from a bond bull market, post-2009 contribution is −0.20, and the 2022
   stock-bond crash sits in the test window where it cannot be checked first.

3. **IEF**. Nearly as good on the numbers (+2.36 over cash, −6.2% drawdown in the GFC, the
   steadiest negative beta) and strictly safer as an instrument — but it is **more expensive to
   permit than TLT**: three frozen `REGISTRY` entries declare `etf:IEF` as literal data and
   `test_registry.test_declared_owner_inputs_match_the_computed_ones` asserts declared == computed.
   Permitting IEF makes that test red and the only fixes are editing closed records or weakening
   the test. Same objection to **EFA** (one entry) and **BIL** (one entry).

4. **GLD**. The only truly orthogonal instrument (β 0.06, r 0.05-0.07) and the one with the biggest
   raw prize, +23.9% in the GFC, and the *only* fund whose post-2009 timing is clearly positive
   (+0.77). Against it: 10.1-year window — the shortest on offer — no dot-com, no dividends, and a
   2011-2015 collapse that makes any whole-window figure a story about one decade of gold.
   Worth a look only if the owner specifically wants an uncorrelated leg rather than a safety leg.

5. **SHY** — do not. It is cash with a ticker (β −0.03) and measures +0.21 over cash. The lab
   already has that lever twice (`idle_symbol`, `cash_yield="T13W"`, measured here at +0.16 and
   already known to be worth 0.8 pts/yr and only before 2008).

6. **XLK** — do not. r = +0.90 with QQQ's own differential. It is QQQ under another name.

7. **DIA, IWM, EFA, XLE, XLF, XLP, XLU, XLV** — do not. Every one of them is *worse than cash* as
   a risk-off leg (−1.05 to −6.81 arm-vs-cash), and DIA's prize (PERFECT +6.64) is a third of
   QQQ's: it is narrower than what the lab already has.

## 7. What permitting one would actually cost

**Not a data question.** All 15 funds are in all four research stores with identical first bars.
Nothing to buy, nothing to rebuild.

**Not a fee question.** `sim/costs.py` is fitted to order *amount* (trading rate + min, regulatory
rate + cap, PPN), with no instrument dimension at all. It prices a TLT order exactly as it prices
an AAPL order. The whole-share rule for bracket orders and the fractional rule for plain limits
apply unchanged. **The owner real-fee model already covers any of these.**

**It is an owner fact, not a code decision.** `docs/handover/2026-10-03-trade-rules-revision.md`
lists this as an open owner input with a conservative default: *"Can Gotrade buy US ETFs (SPY, QQQ,
sector SPDRs, TLT, IEF, GLD, BIL/SGOV)? Which ones? → Assume SPY and QQQ only."* `DEFAULT_ETFS` is
the placeholder for an unanswered question, not a measured limit. **Step one is the owner opening
Gotrade and saying whether TLT is buyable there.** I cannot verify that from here and did not try.

**If he says yes, the code that moves:**

- `engine/src/seer_engine/sim/rules.py:76` — one line, `DEFAULT_ETFS`. Precedent exists:
  `LEVERAGED_ETFS` at :77 is already a second list, read at `backtest/dev.py:288`.
- `engine/tests/test_sim_rules.py:72` — the pin on the frozenset. One line.
- `engine/src/seer_engine/backtest/dev.py:286` — **no change.** `candidate_owner_inputs` reads the
  constant; the gate is `dev.py:471`, where a non-empty owner-input tuple writes the fifth
  `FAILURE_LABELS` entry and `eligible = not failed` goes false forever. That is the real gate,
  and it moves by itself.
- `engine/src/seer_engine/backtest/registry.py` — **must not change** (append-only, frozen). For
  TLT, GLD, DIA, IWM and SHY nothing there needs to: the registry declares only
  `etf:BIL`, `etf:EFA`, `etf:IEF` (×3), `etf:SSO` (×2), `etf:QLD` and the nine sector flags, and
  those five tickers appear nowhere in it. **This is the single strongest practical argument for
  TLT over IEF.**
- Recorded lab rows: **safe, by design.** `lab/store.py:OWNER_INPUTS_LABEL` carries the
  `owner inputs` label from the recorded `failed` string rather than re-deriving it, precisely
  because there is no column to re-derive from. No past verdict silently flips. `trials` has no
  `owner_inputs` column at all.
- `web/`: no occurrence of either constant. Nothing to mirror.
- One side effect worth naming before he decides: `DEFAULT_ETFS` also gates
  `TradeRules.idle_symbol` (`rules.py:482`). Adding TLT silently makes `idle_symbol="TLT"` an
  owner-input-free rule set — idle cash parked in 20-year Treasuries. If that is not wanted, the
  third fund belongs in its own list next to `LEVERAGED_ETFS` rather than inside `DEFAULT_ETFS`.

So: roughly two lines of production code and one test line, plus a deliberate choice about
`idle_symbol`. **The cost of permitting is near zero. The reason not to permit is that the
measurement says it would not buy anything.**
