# Handover — the gate wants to be read monthly, and the lab was already reading it there by accident

**Written:** 2026-10-19 · **Branch:** `feature/gate-reading-cadence` (merged to `main`)
**Method spent:** M0260 · **Next free id:** M0262

**The lab after this run**

| | |
|---|---|
| dev trials | **836** (830 + 6) |
| test-window looks used | **4 — unchanged. None was spent.** |
| methods | **275** (273 + M0260 + the queued idea M0261) |
| insights | **470** (465 + 5: three `lab costs` observations #466-468, the synthesis #469, the risk #470) |
| N the luck gate judges at (policy: methods) | **164** (163 + 1) — the `n_at_run` recorded on all six trials |
| next free id | **M0262** |

*Phase 3 never wrote a `16-final.txt`, so these six counts were re-derived here by a read-only
`sqlite3 "file:…?mode=ro"` query against `/home/miftah/seer/lab/lab.sqlite`, with the file's
`git hash-object` checked identical before and after. Every other number below comes from a
`/tmp/m0260` capture and is attributed to it by name.*

---

## What this session established

M0260 swept how often the SPY 200-day gate is read, on a book that actually holds stocks —
`M0072-Z2-RAWRANK`, carried verbatim — from weekly to yearly. **Six arms**, one book, nothing
moving but the rule set's cadence and the gate's checking interval. Every figure below is the
**money-weighted** return on the owner's own monthly deposits (`trial_funding.mwr`, what `lab show`
prints as "your money earned"), against **7.19%/yr** for the same deposits put into SPY TR
(`06-ladder.tsv`'s `spy_pct` column, confirmed equal to M0258's handover figure). The curve-shape
columns are not quoted anywhere: these books are funded and `total_return` and `cagr` count the
owner's deposits as gains.

**Six arms, not seven, and the monthly ladder has four rungs.** `lab/method.py:40` caps a method at
`MAX_VARIANTS = 6` and `Method.__post_init__` raises outside `1..6`, so a seventh arm would have
failed at import. The two-month rung was measured as a prior on SPY alone
(`docs/backtests/2026-10-19-gate-reading-cadence.md`: 8.56%/yr, 19.7% fall, **unfunded**) and
deferred to an `Amendment` under this same id, **which costs no method id**. Read the four-rung
monthly ladder as four rungs, not as five with a hole in it.

### The ladder

| arm | re-pick | gate read | money | worst fall | trades | turnover | PF | DSR | screen |
|---|---|---|---|---|---|---|---|---|---|
| `M0260-W-NATIVE` | weekly | weekly | 5.32% | 35.49% | 1923 | 10.002 | 1.28 | 0.416 | failed SPY, PF, DSR |
| `M0260-W-G1` | weekly | **monthly** | 11.28% | 26.07% | 1492 | 8.055 | 1.76 | 0.890 | failed DSR |
| `M0260-M-NATIVE` | monthly | monthly | **12.33%** | **23.80%** | 1208 | 6.529 | 1.98 | **0.928** | **eligible** |
| `M0260-M-G3` | monthly | quarterly | 8.78% | 33.64% | 1184 | 6.459 | 1.60 | 0.695 | failed DSR |
| `M0260-M-G6` | monthly | half-yearly | 12.10% | 30.34% | 1202 | 6.422 | 1.81 | **0.915** | **eligible** |
| `M0260-M-G12` | monthly | yearly | 8.64% | 25.64% | 1099 | 5.731 | 1.62 | 0.780 | failed DSR |

*(every cell from `06-ladder.tsv` at full precision, cross-read against `04-show.txt`; trials
#835-#840. Six rows, not seven — the two-month rung was not run. Method status: `dev-eligible`.)*

**Where it turns: at monthly, and the ladder above it does not fall — it zig-zags.** Money goes
12.33 → 8.78 → 12.10 → 8.64 as the reading slows from monthly to quarterly to half-yearly to
yearly. **No slow rung beats `M-NATIVE` on money** — the pre-registered falsifier did not fire — and
**every slow rung falls deeper** than its 23.80%: 33.64%, 30.34%, 25.64%. So the best cadence on
both axes at once is the one the lab already runs, and it is also the fastest rung of the ladder.

The zig-zag is the finding, not noise to be smoothed. A monotone fall would have meant "a gate read
less often is a weaker gate, in proportion". What actually happens is that `k = 6` nearly matches
`k = 1` on money (12.10 against 12.33) while falling **6.5 points deeper**, and `k = 3` and `k = 12`
both give up 3.5 points a year. Past monthly the reading interval stops behaving like a rate at all
and starts behaving like a lottery over *which calendar dates get read* — `k = 3` reads the calendar
quarters, `k = 12` reads Decembers only, and whether those particular dates happen to sit before or
after a fall is luck. That is why `M-G6` cannot be promoted on its near-tie: it is the same lottery,
with a kinder draw.

**It is not a fee story, and the fee read is what proves it.** `lab costs` at three rungs
(`10-costs-M-NATIVE.txt`, `10-costs-M-G3.txt`, `10-costs-M-G12.txt`) shows real-Gotrade fees falling
monotonically as the reading slows — **$57,243 → $42,339 → $37,593** — while money zig-zags. The slow
rungs pay *less* and earn *less*. Fee drag as a share of gross trade P&L moves the other way
(11.5% → 15.1% → 15.5%) precisely because the gross P&L shrank faster than the fee bill did. A fee
story improves monotonically as trading falls; this one does not, so what the slow rungs lost was
timing.

### The reproduction

**Both reproduction arms came back exact, on all six fields.** `M0260-M-NATIVE` returned
`M0258-M-B0` = `M0072-Z2-RAWRANK`'s recorded row digit for digit — 12.3314% money-weighted, 23.8026%
worst fall, 1208 trades, turnover 6.5288, exposure 0.6949, PF 1.9781 — and `M0260-W-NATIVE` returned
`M0258-W-B0`'s — 5.3178%, 35.4908%, 1923, 10.0021, 0.6855, 1.2767. `06-decomp.txt` prints
`REPRODUCES` field by field for both and closes `REPRODUCTION: CLEAN`. So every paired difference
below is the gate reading and nothing else.

**The lookback was widened and the reproduction survived it.** M0260 runs at `lookback = 454`, not
M0072's 253, because a twelve-month anchor sits up to 253 sessions behind the data date and still
needs its 200-bar average — at 253 three of the four slow rungs fail `assert_p4_identity`'s lookback
cut outright. Widening does not move the window: `dev.candidate_window` (`dev.py:292-306`) checks
only the candidate's **fixed** symbols, and `ZJUMP.symbols(BOOK)` is `("SPY",)` while index members
are floored separately at `MEMBERSHIP_START` (1996-01-02). SPY's 739th dev-store bar is 1996-01-02,
so any `lookback <= 739` leaves the first scored session at **1996-01-03** — the same session M0072
and M0258 recorded. `02-probe.txt` and `02-probe-w.txt` show `1996-01-03..2015-10-16` before the run
and every trial's `start` shows it after. **The standing rule worth carrying forward is "never cross
739", not "never widen"** — M0258's file forbids widening because its own proposed `+SCAN` reached
757, which genuinely would have moved its start. The operative ceiling from the other side is the
473-session smoke fixture, which 454 clears with 19 sessions to spare.

### The decomposition: M0258's +7.01 points, split

With A = `M0260-M-NATIVE` (monthly re-pick, monthly gate), C = `M0260-W-G1` (weekly re-pick, monthly
gate) and B = `M0260-W-NATIVE` (weekly re-pick, weekly gate):

| term | what moves | money | worst fall |
|---|---|---|---|
| **A − C** | re-pick frequency, gate held monthly | **+1.05 pts/yr** | 2.27 shallower |
| **C − B** | gate reading cadence, re-pick held weekly | **+5.96 pts/yr** | 9.42 shallower |
| **A − B** = the sum | both, as M0258 measured it | **+7.01 pts/yr** | 11.69 shallower |

The arithmetic, in full, so it can be checked: money `12.3314 − 11.2825 = +1.0489` and
`11.2825 − 5.3178 = +5.9647`, which sum to `+7.0136`; worst fall `35.4908 − 23.8026 = 11.6882`
splits as `26.0738 − 23.8026 = 2.2712` and `35.4908 − 26.0738 = 9.4170`. `06-decomp.txt` reports the
sum residual as **exactly 0** on both axes.

M0258 measured A − B at **+7.01 pts/yr and 11.69 points of worst fall** on this same book and could
name neither half. This run re-measures it identically and attributes **85% of the money
(+5.96 of +7.01) and 81% of the fall (9.42 of 11.69) to how often the gate is read**, leaving only
+1.05 pts/yr and 2.27 points to how often the book re-picks stocks. The pre-registered prediction
was "(C − B) at least half of the +7.01, point estimate 4 to 6, leaving (A − C) at 1 to 3" — both
brackets landed inside their stated ranges. The unfunded SPY-alone prior had already pointed the
same way (84% of its +3.58 was the gate), on an instrument with no stock picking in it at all.

**Why C − B is clean.** At a weekly rank session in month *M*, arm C's anchor is the newest month end
on or before its `data_date` — the same month-end session arm A read at its own rank session that
month. Arm C does not approximate arm A's reading; it **reuses** it, so A − C moves re-pick frequency
and nothing else. `test_lab_m0260_cadence.py` asserts that session by session rather than in prose.

**What the decomposition does not reach.** The cadence axis is separable **only on the slow side**.
A monthly book cannot act on a gate reading taken between its rank sessions — a reading it never acts
on changes no target and no trade — so making the book read the gate *faster* than it re-picks **is**
a rule-set change, which re-picks faster too. The sub-monthly rung is inseparably confounded on this
chassis. That is a property of the simulator, not a gap in the design, and it is why the ladder is
built upward from monthly rather than downward from weekly.

### What can be promoted, and what never can

The facts, which do not depend on the result:

- Every **monthly** arm — `M-NATIVE`, `M-G3`, `M-G6`, `M-G12` — runs on `monthly-hold-frac-gotrade`,
  which **is** in `sim.rules.PRESETS` (`sim/rules.py:261`, registered at `:308`). **All four are
  promotable.**
- Both **weekly** arms — `W-NATIVE` and `W-G1` — run on `weekly-hold-frac-gotrade`, which is defined
  in `m0063_earnings_day_jump.py:64` and is **not** in `PRESETS`. `lab promote` requires membership,
  so **no weekly result of this run can ever become a book the owner runs**, whatever it shows. They
  are diagnostic forever, by design, and the method file says so in its own words.
- There is no quarterly or yearly **rule set** either, and there cannot be one without a schema move:
  `sim.rules.Cadence` is `Literal["daily", "weekly", "monthly"]`, and adding a member would move
  `_CADENCE_ORDER`, `_first_of`, `is_rank_session`, every `TradeRules` canonical text and the web
  mirror. **This is precisely why the slow rungs were built as allocator params and not as rule
  sets** — the params route leaves `TradeRules` untouched, so a quarterly or yearly *gate* stays
  promotable even though a quarterly or yearly *cadence* does not exist.

**And the result: the rung that won is `M0260-M-NATIVE`, which is promotable today and needs nothing
built for it — because it is the cadence the lab is already running.** Two arms cleared the dev
screen, `M-NATIVE` (DSR 0.928) and `M-G6` (DSR 0.915); the other four failed, `W-NATIVE` on all three
of beats-SPY, PF and DSR, and the rest on DSR alone. `M-G6` is promotable and should **not** be
promoted: it earns 0.24 pts/yr less and falls 6.53 points deeper, and the paragraph above says why
its near-tie is a draw rather than a speed. No weekly arm won, so the missing
`weekly-hold-frac-gotrade` preset stays an academic gap for this book and **no `feature-wish` was
owed or journalled** — leftover item 7 stays where it was.

### The walk-forward folds, arm by arm

`lab walkforward M0260` did **not** print `*** BUY SIGNAL ***` — the verdict line reads
*"fails the folds: 2 of 4 folds, pick changed"*, and `0 of 1 methods beat the benchmark in a majority
of folds` (`07-walkforward.txt`). The fold-by-fold table below comes from `08-folds.txt`, which is
the only place the arm each fold picked is printed at all. Read it arm by arm before acting on it,
because the folds select each fold's variant **by MAR**, which structurally favours whichever arm
trades least — and this ladder's slowest rungs trade least by construction:

| fold | evaluate | arm selected | won? |
|---|---|---|---|
| 1 | 2003-01-31..2005-12-30 | `M0260-M-G12` | lost |
| 2 | 2006-01-31..2008-12-31 | `M0260-M-G6` | **WON** |
| 3 | 2009-01-30..2011-12-30 | `M0260-M-G6` | lost |
| 4 | 2012-01-31..2014-12-31 | `M0260-M-NATIVE` | **WON** |

**Won or lost, never a percentage.** `08-folds.txt`'s `its return` and `bench` columns are
`total_return` over a fold slice, and its whole-arm block prints `cagr` and `MAR` — curve-shape
figures on a deposit-matched curve, not the owner's money. This table carries the arm and the verdict
and nothing else; every percentage anywhere else in this handover is `trial_funding.mwr`.

**The folds drifted toward the slowest-trading arms, exactly as the pre-registration warned — and
three of four picks is the loudest version of that warning the lab has recorded.** `picks by arm:
{M-G12: 1, M-G6: 2, M-NATIVE: 1}`. Three of four folds handed the stretch to a slow rung, **two of
those three lost**, and the single fold that picked `M-NATIVE` won. So the fold headline here is a
reading on the *selection rule*, not on the cadence: MAR picked the arm that trades least and the
arm that trades least then underperformed. **This is the third data point and they disagree** —
M0245's folds drifted to its braked arm, M0258's did not (two of four chose no band at all), M0260's
drifted hard. The MAR rule is a bias to *check*, never a bias to assume. 2009-2015 edge: **+2.3 pts**
(`07-walkforward.txt`). No kin figure was printed: the headline gate failed at the fold majority
before kin was reached.

### D17 and the control shape

`lab control M0260` reports **six** `dose-response` rows, verdict `not-checked`, no ratio, **no
refuse**, and closes with *"every control arm shown matches the shape of the arm it controls"*
(`09-control.txt`). The ladder with `M-NATIVE` as its zero rung is its own control; no drawn arm
exists by design, which is the shape D17 was built to require. All six arms carry the literal phrase
`dose-response` in their rationale, which is how `control_shape.kind_of` classifies them
(`lab/control_shape.py:191-200`) — a classification that reads an arm's **prose**, so it was checked
through the real classifier before the pre-registration commit froze the file, never after.
`09-control.txt` also confirms the read cost nothing: `recorded dev trials 836 -> 836; test-window
looks 4 -> 4`.

---

## What is now dead, and must not be bought with another method id

- **Slowing the gate past monthly.** The ladder is flat-to-falling and **non-monotone**: 12.33 →
  8.78 → 12.10 → 8.64 on money, with every slow rung falling deeper than monthly's 23.80%. No rung
  beats the cadence the lab already runs on either axis, and the one near-tie (`M-G6`) pays 6.5
  points of extra fall for it. Past monthly the interval stops being a speed and becomes an accident
  of which calendar dates get read. **Do not spend an id on a slower reading, and do not promote
  `M-G6` on its near-tie.**
- **The price band.** Measured three times — on SPY alone read monthly (−0.40 pts/yr), on M0101's
  calm-raisers stock book (−0.18 at 3%, −0.52 at 5%), and on M0072's earnings-jump book across a
  four-rung ladder (−0.57 at 3%, −3.21 at 6%). It is only ever worth something when the gate is read
  faster than monthly, and no promotable rule set reads it faster than monthly. Do not spend another
  id widening, narrowing or asymmetrising it.
- **Turning the gate off.** Helped 22 of 22 variants whole-window, 0 of 22 after 2009, and every
  gate-off arm was worse on return *and* drawdown at once.
- **A time lock on the switch.** Costs return and deepens the worst fall from 20% to 32%: the flips
  it suppressed included the 2008 exit. The standing rule is "stop hunting hysteresis here".
- **An account-reading drawdown brake.** Pays about 10 points a year of 2009-2015 to save 40 of 2008.
  A volatility dial beats a drawdown dial on every axis.
- **A learned fall-sizing brake** (M0132). Beaten by the plain gate on both axes.
- **VIX-level confirmation of the exit.** Worse on both axes at 20, 25 and 30, and VIX3M only begins
  2006-07-17, so it cannot be checked against the dot-com fall at all.
- **Exit-buffer-only, confirm-N-days, partial exposure, fast re-entry on the 50-day.** All in the
  committed variant grid, all worse than the symmetric band.

**What replaced "how often should the gate be read" as the open question:** whether monthly is the
right speed *on this book's calendar* or *in general*. The zig-zag above is consistent with either,
and one book cannot tell them apart — which is what the queued M0261 is for.

## Leftovers, in priority order

1. **The nine D17-blocked dev-eligible methods** — M0047, M0201, M0202, M0208, M0215, M0221, M0225,
   M0227, M0243 — each carrying a control arm whose trade count or turnover does not match the arm it
   controls. The remedy costs **no method id**: re-draw each control at the book's own shape and
   record it as an amendment under the existing id. This is still the cheapest information left in
   the lab and it re-tests nine standing verdicts.
2. **M0261, already queued** — *"Does the safety gate's best reading speed hold on a second book, or
   was the zig-zag luck about calendar dates?"* The zig-zag is this run's one unresolved shape, and a
   second host is the only way to tell a calendar artifact from a real interval effect. **Check first
   that the second book's event hold is counted in sessions**: M0197's chooser keys its re-pick on
   `data_date.month` and cannot host this axis at all. M0072 qualified because it keeps the newest
   event with `i - hold < t <= i - 1` for 60 sessions, so the same event is live for the same 60
   sessions whether the book looks four times or sixty.
3. **The two-month rung (`k = 2`), deferred to an `Amendment` under M0260 — free in method ids.**
   `MAX_VARIANTS = 6` is why it was not an arm. On the unfunded SPY-alone prior it reads 8.56%/yr and
   a 19.7% fall, between `k = 1`'s 9.08%/19.0% and `k = 3`'s 6.71%/24.5%. Given the measured zig-zag,
   this is now worth more than it looked when it was dropped: it is the one untested rung between the
   winner and the ladder's first trough.
4. **Applying the cadence reading to the rest of the roster is NOT worth doing on this evidence.**
   Every other book still reads its gate at whatever cadence it happens to re-pick, but the finding
   here is that monthly — which most of them already are — is the best rung. The amendment arms are
   free, but there is nothing to move them toward until M0261 says whether the shape generalises.
   Recorded here so the next session does not re-derive it as a new idea.
5. **The buyback holdability problem.** The cheap-buyback book led by 11.4 points a year in 2009-2015
   on honest prices and won all four out-of-sample stretches, but falls 55-85%, so it cannot be held.
   A containment problem, not a gate problem.
6. **Insight 457's practical conclusion still stands on the site** ("weight by company size"),
   withdrawn by 462 but, `insights` being append-only, still visible to the owner. Another correction
   row — same shape as the one M0258's run queued, different subject.
7. **P2-ENG-N3LB** — `name_count.py`'s docstring still calls the dev trial count "the lab's N", which
   the 2026-10-08 policy move made wrong.
8. **P3-ENG-V2KQ** — append a dated §7.3 revision to the lab design doc recording the N policy move
   to methods.
9. **`sim.rules.PRESETS` has no weekly fractional Gotrade preset**, so M0260's two weekly arms can
   never be promoted whatever they showed. **No weekly arm won here, so the question is now academic
   for this book** and no `feature-wish` was journalled. It stays on the list only because the next
   method to put a weekly arm on the board will meet it again.

## Environment notes that save an hour

- **The worktree has no venv and no research store.** Use the main checkout's:
  `PY=/home/miftah/seer/engine/.venv/bin/python`,
  `SEER_RESEARCH_STORE=/home/miftah/seer/engine/.research`. Never rebuild a store — it is 30 minutes
  for nothing.
- **`PYTHONPATH=<worktree>/engine/src` or pytest silently tests the main checkout**, not the branch.
- **`SEER_LAB_DB=/home/miftah/seer/lab/lab.sqlite`.** A worktree copy must never be written, and
  **even a pure read migrates the file on connect** — so a read-only `lab show` after the run dirties
  the committed database. Hash it before (`git hash-object`), restore it by path after, and check the
  hash matches. A `sqlite3 "file:…?mode=ro"` query never migrates and needs no restore; that is what
  this handover's lab-state table was re-derived with.
- **`lab stage` targets the MAIN checkout** — it regenerates and `git add`s `/home/miftah/seer`'s
  `lab/lab.sqlite` and `web/data/lab.json`. Commit them with `git -C /home/miftah/seer commit` and
  **no pathspec**: a pathspec re-reads the working tree and defeats the staging.
- **Never `pull --rebase` over a lab commit.** A rebase replays a stale `lab.sqlite` and overwrites
  the live shared database other sessions are writing. If a push is rejected, re-run `lab stage`,
  re-commit with no pathspec, and check trial `n` is contiguous.
- **Never judge a `lab` command by a piped exit code.** Redirect to a file and echo `$?`; a
  `grep`/`head` owns the pipeline's status, and this shell prints a spurious
  `setValueForKeyFakeAssocArray:27: command not found: _encode` line at startup that appears at the
  head of every captured file.
- **One core.** Run pytest with `-n0`; never override `addopts`.
- **The DB tests need Postgres**: `docker start seer-pg`, and
  `PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres`. CI fails if they skip.
- **This set's cadence study takes an ABSOLUTE `--store`, unlike M0258's**, so it runs from the
  worktree: `PYTHONPATH=<worktree>/engine/src /home/miftah/seer/engine/.venv/bin/python
  docs/backtests/2026-10-19-gate-reading-cadence.py --store /home/miftah/seer/engine/.research`.
  That is a deliberate correction of the M0258 precedent (whose
  `docs/backtests/2026-10-19-gate-band-cadence.py` hard-codes a relative `engine/.research`); the
  older file is a committed record of a finished study and **must not be edited** to match.
- **A lab allocator on an index-member book may widen its lookback up to 739 bars without moving the
  dev window's first scored session.** `dev.candidate_window` checks only the candidate's fixed
  symbols and floors index members at `MEMBERSHIP_START` (1996-01-02); SPY's 739th dev-store bar is
  1996-01-02. The real operative ceiling from the other side is the 473-session smoke fixture. M0260
  runs at 454. The rule is **"never cross 739"**, not "never widen" — M0258's file says the latter
  because its own proposed widening reached 757.
- **Phase 3's captures live in `/tmp/m0260`**, copied to `/home/miftah/.cache/seer-captures-m0260`
  because `/tmp` does not survive a reboot. **`08-folds.txt` is the only place the arm each
  walk-forward fold picked is printed** — `lab walkforward` prints the per-method headline and never
  names the arm, so that file cannot be re-derived by any `lab` command. There is no `16-final.txt`
  in the set despite the plan naming one; the closing counts were re-read instead.
- **Six arms on this store cost about 40 seconds of simulation plus one 12-second store load.** The
  probe measured one monthly arm at 5.0s and one weekly arm at 8.8s against a 11.7s store load that
  happens once per `lab run`; `lab costs` is ~19s per arm, store load included. Budget a `lab run` of
  a six-arm method at a minute, not an hour.
