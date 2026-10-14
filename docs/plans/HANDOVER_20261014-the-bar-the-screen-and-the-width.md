# Handover — 2026-10-14: the bar, the screen, and the width

**Session:** `sera-20261014-1435` (began as `orch-split-screen-from-bar`)
**Branch:** `main` @ `2bf73fe` — clean, pushed, nothing in flight
**Lab:** 473 trials · 170 methods · **test-window looks 4, unchanged all day**
**Nothing was promoted. No test look was spent.**

---

## The one decision waiting for the owner

**Hold 35 names, not 20.** M0152 measured the roster's own picking rule at seven widths on both
price histories. On the history that includes the companies that went bankrupt or were bought:

| | worst fall | yearly |
|---|---|---|
| **20 names (the roster today)** | **25.05%** — outside the owner's 25% bar | 11.98% |
| **35 names** | **20.11%** | **12.11%** |

The return cost is **0.6 pt/yr on the dev store and negative on the check store** — the wider book
earns more there. MAR peaks at 35 on *both* stores. The curve is a **staircase, not a slope**: 25
and 30 are indistinguishable (22.0 / 22.1), so 30 is the one rung that buys nothing.

Full curve, trough dates and era columns: `docs/lab/survivorship/roster-width-curve-2026-10-14.csv`.

**This is a real-money decision, not a research result.** The owner mirrors the paper roster with
his own money, and `RAW-FR-GT` *is* M0007-N20-RAW, a top-20 book. Per
`owner-mirrors-the-paper-roster-with-real-money`, the decision *date* moves the names.

### The honest bound — state this before the recommendation, as M0152 did

**The width effect rests on ONE episode.** Every width's worst fall on both stores is
1998-06 → 1998-08, with exactly one exception: the roster's 20-name book on the check store,
which troughs **2006-03 → 2006-07**. SPY went 3.71 → 3.62 in that window — a 2% dip that made a
new high by September — while the 20-name book lost 21.8%.

Worst fall by era, check store, 20 → 70 names:

```
1998      21.6 19.2 19.9 19.7 19.4 18.7 18.0   3.6 pts — the floor, width barely helps
dot-com    9.4  6.7  4.3  5.0  6.5  6.6  5.1
2006      21.8 18.9 18.8 16.2 15.1 14.8 12.9   8.9 pts — the ONLY width-sensitive episode
2008-09    9.1  9.3  9.5 10.1 10.0  9.7  8.2   the gate's best work is the famous crashes
2010-15    9.9 10.2 10.1 10.4 11.1 10.7 10.6
```

What makes it more than a coin flip: the one episode is the **ordinary** kind — a company failing
in a rising market — not a crisis that may not repeat, and the two actual crises show no width
effect at all.

**The mechanism, now dated rather than inferred.** The SPY 200-day gate handles *market* falls and
handles them well (dot-com and the GFC are its mildest episodes). 1998 is too fast for it and is
nearly width-insensitive. Width handles the *single holding that collapses while the market is
fine*, and in twenty years that happened once. For a narrow book that blow-up is now the larger of
the two risks — and most of this lab's method ids have gone to timing.

---

## What landed today (48 commits)

1. **The drawdown bar split in two** (design §18, merge `e93fa85`). `MAX_DRAWDOWN` = **0.25** is the
   real-money bar; a separate `DEV_MAX_DRAWDOWN` = **0.50** is the dev screen. Four decision sites:
   `dev.FAILURE_LABELS`, `dev.make_row`, `store.owner_failures`, `store._blocking`. Do not conflate
   them. 15 methods moved `rejected → dev-eligible` as a consequence.
2. **M0122 — the market-shape theory is dead** for the dev window. Weighting picks by trading value
   cost return on all three parents (−0.4, −1.2, −0.8 pt/yr) and cost DSR on all three. It *is* a
   drawdown tool (cut one book's fall 27.0% → 21.2%) that charges about a point a year.
3. **Three Sera batches, twelve methods, zero promotions.** Syntheses are insights **237, 254, 271**.
4. **`lab kin`** (`ad49cf0`) — read any variant's own resemblance without spending a method id.

---

## The four findings a new session should not re-derive

- **The audit key is TURNOVER, not name count.** The resize band under `resize_basis="equity"` can
  never fire in a many-name book, so deposits reach it only through turnover. M0123 measured 51% vs
  96% invested (3.1 pt/yr); M0139 measured the same fix worth only 0.1–0.3 pt/yr on a fast, gated
  book. Fast or gated books leak ≤1 point and can be read as recorded; slow always-invested wide
  baskets leak tens. **The roster's 20 names were NOT chosen on a broken measurement** — M0139
  re-ran the sweep on a tape that invests and 20 still won there.
- **The dev store is structurally blind to what width is for.** A book falls because the market
  drops (the gate removes this) or because one name collapses alone (the dev store removes this, by
  missing ~4 in 10 of the days companies sat in the index). Behind the gate on dev, both are
  invisible, so width reads as pure cost. This is why M0139 concluded "width buys no safety" and was
  wrong by a factor of six.
- **The learned ranker is finished.** Four levers turned — capacity (M0130), target horizon (M0131),
  memory (M0137), information (M0144). Only the horizon helped (+4–6 pt/yr). Fold record was 1 or 2
  of 4 *every single time* while twenty-year averages looked respectable. Do not give it another
  knob; M0153 (accounts-only, judged where the accounts exist) is new information, not a new setting.
- **The switch's two halves want opposite things.** Quick to come back, slow to leave. Re-entering
  on a realised positive quarter beats a price cross — replicated on **four** books (M0113, M0135,
  M0133, M0143), including one with no momentum in it. 63 sessions is an *interior peak* (21 and 126
  are both worse). The sell side is already optimal: M0143 found longer and smoother monotonically
  better, because a 200-day average is sticky while a quarterly test flips in a chop.

---

## The structural problem, stated plainly

Of twelve methods across three batches, **nearly every promising one was refused because it is
behaviourally the book already tested and lost with.** Three separate routes — re-weighting,
sheltering, asymmetry — arrived back at the same family. The best book the lab has ever built
(M0133-G20-UP63: 16.7%/yr vs SPY 7.2%, 22.7% fall, 4 of 4 folds alone) reads **0.8964** against
test-failed M0002 at a 0.85 bar.

M0146 established *why*, and it is sharper than "it is momentum in disguise": the asymmetry rank
holds **different companies** (18.7% overlap vs 15.3% by chance) and still lives the same
month-to-month life. **It selects temperament, not names.**

**The kin rule was calibrated for the first time** and it holds up: 24 random 40-name books, 96
comparisons against real books, range 0.48–0.78, **zero** over the bar, where the real book reads
0.896. It is discriminating, not indiscriminate. That matters because it is currently refusing
nearly everything.

---

## Open work, highest value first

| id | what | why now |
|---|---|---|
| **M0155** | A single-name brake: trim a holding falling apart while the market is fine | The 2006 episode is the one hole BOTH existing defences leave open. Width only dilutes it. Now a measured hole, not a speculative one. |
| **M0156** | Survivorship-check M0002-REL-85 | **`MOM-FR-GT` has no survivorship row at all.** One of the three books the owner mirrors has never been checked against honest prices. Step one (`lab survivorship M0002`) is free. |
| **M0149** | The asymmetry book braked by its OWN falling account, not the market's trend | The one door the kin finding leaves open: every *market*-reading brake puts every book in cash in the same months, which is exactly what D14 refuses. A book-reading brake does not. The ungated arm is behaviourally free at 0.57. |
| **M0148** | A time-lock on the switch (stay settled K months after a flip) | Differs from the banded fix that already lost: a band delays the first exit of a real crash, a time lock does not. |
| **M0151** | Regress the survivorship drawdown penalty on width/turnover/gate | If width explains the spread, a width decision can be corrected without owning the check store. |
| **M0153** | The accounts-only picker, judged 2009–2015 only | The only genuinely new information the ranker direction has left. |

Also queued, lower: M0134, M0136, M0138, M0140, M0141, M0142, M0145, M0150, M0154.

---

## Decisions made this session that a successor should not silently reverse

- **The width grids are NOT merged into `docs/lab/survivorship/grid.csv`.**
  `survivorship_record.GRID_PATH` points D16 at that exact file, so appending would change which
  promotions the hard gate refuses *as a side effect of a research run*. The new measurements live
  as their own dated files. **There is a real hole** — M0128 is absent from the grid, so D16 cannot
  see that the roster's book breaches the bar — but it is not urgent, because M0128 is already
  blocked on folds *and* kin. Closing it deserves its own argued commit with the gate's tests run.
- **M0146 did not spend a method id**, and that was endorsed. `config_text` digests rules, allocator
  id and params but never the candidate id, so a solo registration would be a byte-identical book
  returning the identical number — at the cost of +1 N applied retroactively to every recorded
  verdict. `lab kin` now reads it for free.
- **Design §18 is not amended** for the trades-bar set growing 12 → 18. That growth has a different
  cause (new SPY-only switch books that trade 11–43 times in 22 years) from the 5 → 12 the screen
  change caused. §18's statement about what the screen did stays true as written.

---

## Traps that cost time today

- **`lab stage` from a worktree stages the MAIN checkout.** The main venv's editable install
  resolves `seer_engine` and `COMMITTED_DB` to `/home/miftah/seer`. Pass `PYTHONPATH=engine/src`.
- **A rejected push then `git pull --rebase` replays a stale `lab.sqlite`** over whatever children
  wrote in the interim. Compare the committed blob against the live file first; if children's
  commits touch no `lab/` files, `git reset` (mixed) + `git merge --ff-only` avoids the replay
  entirely with no stash.
- **Backticks inside a double-quoted `git commit -m` are command substitution.** Commit `fca1704`
  lost two words that way; it carries a `git note` with the correction rather than a force-push.
- **Re-subscribing to an already-idle session fires the notice instantly** and tells you nothing.
  Watch the lab for the state change instead.
- **A child going idle with a background `lab run` shell is normal, not a stall.** Check the pane
  for "N shells still running" before intervening.

---

## How to pick this up

```bash
cd /home/miftah/seer && git pull --rebase --autostash
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab status
PYTHONPATH=engine/src engine/.venv/bin/python -m seer_engine lab kin M0133   # the new tool
```

The width recommendation is the owner's to accept or decline; everything else is research. If a
batch is wanted, **M0155 + M0156 + M0149 + M0148** are four different families and each closes a
question this session opened.
