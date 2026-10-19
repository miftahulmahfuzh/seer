# Handover — the gate is out on the wrong days, and buys back into crashes

**Written:** 2026-10-19 by the session that measured it · **State:** `main` @ `000dbd4`, tree clean
**Lab:** N (methods) 271 · dev trials 824 · test-window looks 4 · insights 464 · next free id **M0258**
**Nothing in this handover has been through `lab run`.** Every number below is a study on market
data. It is a prior, not a result, and the whole point of the next session is to let it fail.

---

## 1. What this session established (evidence)

**`lab shortfall` swept over all 824 recorded dev trials** (162 methods, era 2009-2015):
824 decomposed, 0 refused, 0 errored. `REF-SPY-HOLD` against itself returns a gap of exactly
`0.00000000`. Data: `docs/backtests/2026-10-19-shortfall-sweep.csv`, written up beside it.
Insight 463.

- Of the 439 trials carrying the shared SPY-200 gate, era exposure is p10 0.668 / **median
  0.782** / p90 0.795, so the premium is p10 3.40 / **median 3.62** / p90 5.52 pts/yr.
- Median losing trial: gap −4.48, gate −3.65, fees −1.33.
- **The residual is a residual.** Across the whole population it reads *positive* (+0.74) and
  invites "the signals were ahead all along". That is the modelled fee term on books turning
  60-119 times a year leaking into it with the opposite sign. In the cut where fees contribute
  0.2 pts (turnover < 1/yr) the residual is **−0.76**. State any residual claim in the
  low-turnover cut or not at all. The stock-picking term is small either way.

**Then the gate itself, on SPY alone** (`docs/backtests/2026-10-19-gate-band-study.md` and its
re-runnable `2026-10-19-gate-band-variants.py`). Insight 464.

- **The gate flips 151 times across 76 episodes**, not the 11 insight 452 quotes. 43 episodes
  last ≤5 days; 2000 alone has a dozen one- to three-day flips. The short episodes sat out
  **+106%** of cumulative market movement.
- A **price band** — exit b% below the average, re-enter b% above — beats the bare gate on every
  axis measured:

  | | whole | whole DD | dot-com DD | GFC DD | 2009-15 | premium | flips |
  |---|---|---|---|---|---|---|---|
  | bare gate | 6.05% | −28.7% | −21.3% | −9.7% | 6.96% | −5.27 | 151 |
  | **band 3%** | **7.87%** | **−20.3%** | **−11.4%** | **−8.2%** | **8.83%** | **−3.39** | **19** |
  | SPY buy-and-hold | 7.01% | −56.5% | — | — | 12.22% | — | 0 |

- It also beats buy-and-hold on return **and** drawdown over the whole window.
- After the band, **11 episodes remain** — the number the lab has been quoting all along.

## 2. Why — and it is not what the search was for

**The band is invested LESS and earns MORE.**

| 2009-2015 | time invested | cagr | avg return on IN days | avg return on OUT days |
|---|---|---|---|---|
| bare gate | 80.6% | 6.96% | 9.23%/yr | **31.57%/yr** |
| band 3% | 79.4% | 8.83% | 11.56%/yr | **21.28%/yr** |

The bare gate sits out the best days. **This refines insight 463**: the premium accounting
(1 − exposure) × market return is right, but the implication drawn from it — that the lever is
time spent out of the market — is wrong. The lever is *which days*.

**The bigger half was never the target.** The bare gate's worst habit is **re-entering during a
crash**. It fragments the dot-com into two exits with a re-entry between (314d + 261d) and the
GFC likewise (98d + 259d). The band holds each as one exit — 2000-10-10 → 2003-04-22 (633 days,
−44.2% sat out) and 2007-11-13 → 2009-06-09 (395 days, −52.6%). That is why the dot-com drawdown
falls −24.5% → −11.4%.

**Disproof attempts that failed to kill it:** smooth across b = 1.5–6% (whole-window return
7.16–8.50%, DD −19.1 to −21.6% — a plateau, so never quote 3% as *the* value); better on return
in 4 of 5 eras and drawdown in 3 of 5 (the one loss is 1994-1999, a calm bull run); and
leave-one-crash-out holds both ways — excluding 2008-09 entirely it still wins +1.87 pts and
+9.1 pts DD, excluding the dot-com entirely +1.39 pts and +0.6 pts DD.

## 3. What is already dead — do not spend a method id re-testing these

- **Turning the gate off.** Helped 22 of 22 variants whole-window, 0 of 22 after 2009; every
  gate-off arm was worse on return *and* drawdown at once.
- **A time lock on the switch.** Costs return *and* deepens the fall 20% → 32%. The mechanism of
  that failure matters here: it suppressed the **2008-05-21** exit, one day after the previous
  episode ended 2008-05-19. **A price band has no such failure mode** — do not read the standing
  "stop hunting hysteresis here" as covering a band in price.
- **An account-reading drawdown brake.** Pays 10 pts/yr of 2009-2015 to save 40 of 2008.
- **A learned fall-sizing brake** (M0132): lost to the plain gate on both axes.
- **VIX-level confirmation** of the exit: measured in this study's grid, worse on both axes at
  every threshold tried (20, 25, 30). **VIX3M only starts 2006-07-17**, so any term-structure
  rule cannot be validated against the dot-com claim at all.
- **Exit-buffer only, confirm-N-days, partial exposure, fast re-entry on the 50-day**: all in the
  grid, all worse than the symmetric band. The grid is in the committed script; read it before
  proposing a variant.

## 4. The implementation constraint, which is load-bearing

`FactorParams.trend` is `tuple[str, int] | None` and `config_text` renders it `"SPY:200"`.
**Widening it to carry a band would move every recorded config digest in the lab.** The band must
live in a new method file behind a **new allocator id**. That costs one method id (M0258 is free)
and that is the correct price.

## 5. The task for the next session

**Build and pre-register one method that carries the band, run it, and let it fail.**

The arms this needs, at minimum, so the result is readable rather than merely good:

1. **The band arm** — the idea, at a band inside the measured plateau.
2. **The bare-gate arm** — the same book with today's `("SPY", 200)` gate, so the comparison is a
   paired difference on one book and not a comparison against the lab's history.
3. **A dose-response ladder across the band** (e.g. 0% / 1.5% / 3% / 6%), because the plateau is
   the evidence. A monotone response across the plateau is far stronger than one good value, and
   a ladder beats a placebo as a control — see the lab's own standing note on that.
4. **A control arm matched on the book's own trade count and turnover**, or D17 will refuse the
   method at promotion. The band *reduces* turnover sharply, so a control drawn at the bare
   gate's trade count would be mis-shaped by construction. Re-read `lab control` before drawing it.

Decide for yourself, from the plan ladder, whether this rides on an existing book's chassis or a
new one. **Measure, do not assume, whether the band helps a book that holds stocks** — everything
in §1 and §2 is SPY alone, and that gap is the single biggest reason this might not survive.

**Do not spend a test-window look.** Four are spent, all four failed. The band must clear the dev
screen first, then a majority of walk-forward folds, before anyone argues for a look.

## 6. Other leftovers, in priority order

1. **Nine dev-eligible methods are blocked by D17** — M0047, M0201, M0202, M0208, M0215, M0221,
   M0225, M0227, M0243 — each carrying a control whose trade count or turnover does not match the
   arm it controls. The remedy **costs no method id**: re-draw the control at the book's own shape
   and record it as an amendment under the existing id. This is the cheapest information left in
   the lab and it re-tests nine standing verdicts.
2. **The buyback holdability problem**, which the lab itself calls its single most valuable: the
   cheap-buyback book led by 11.4 pts/yr in 2009-2015 on honest prices and won all four
   out-of-sample stretches, but falls 55-85% so it cannot be held. A containment problem.
3. **Insight 452 says eleven exits; the gate actually flips 151 times across 76 episodes.** 464
   records the discrepancy but no correction row was appended against 452 itself. `insights` is
   append-only, so the fix is a correction row, never an edit.
4. **Insight 457's practical conclusion still stands on `/sera`** — "weight by company size" —
   withdrawn by 462 but, being append-only, 457's own text remains. Readers see both.
5. Two pre-existing open tasks: **P2-ENG-N3LB** (`name_count.py`'s docstring still calls the dev
   trial count "the lab's N") and **P3-ENG-V2KQ** (append a dated §7.3 revision recording the N
   policy move to the lab design doc).

## 7. Environment notes that will save you an hour

- `engine/.venv` exists and is installed. **`python3.11` is not on this machine** — the
  interpreter is `/home/miftah/miniconda3/bin/python3.12`. Use `engine/.venv/bin/{python,pytest,ruff}`
  with `PYTHONPATH=engine/src`.
- Postgres: `docker` container `seer-pg` on 55432;
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`. CI fails if the DB tests skip.
- Baseline at `000dbd4`: engine **6028 passed, 3 skipped**; web **688 passed**; `ruff` clean.
- **This machine has ONE core.** Parallel workers buy nothing. The `lab shortfall` CLI pays a
  Python start and a 129MB `bars.csv` parse per trial (~44 min for 824); drive the module instead —
  `gate_history(store)` once, then `gate_shares` + `measure` per trial. Point `SEER_LAB_DB` at a
  throwaway copy so the committed database cannot be dirtied.
- **This shell prints `setValueForKeyFakeAssocArray: command not found: _encode` on startup.**
  Never judge a `lab` command by a piped exit code — a `grep -v` owns the pipeline's status.
  Redirect to a file and echo the command's own `$?`.
- The dev store is `/home/miftah/seer/engine/.research`; never rebuild one.
