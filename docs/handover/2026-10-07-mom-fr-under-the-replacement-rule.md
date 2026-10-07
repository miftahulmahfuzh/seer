# Handover: MOM-FR, judged under the roster replacement rule

Written 2026-10-07 on `feature/delisting-stress-roster-rules` (base `3683d7b`), before the first
paper session has ever run. This settles **Q3** of
`docs/handover/2026-10-07-roster-first-night-and-survivorship.md` §5 — *"is `MOM-FR` the weakest of
the five?"* — under the rule written in `docs/plans/2026-10-04-method-lab-design.md` §8,
*The roster replacement rule (2026-10-07)*.

Q3 said the question was *"worth asking… **but not before** reading the warning in Q4."* That
ordering is honoured: the rule was written first, by a separate session that could not see this
answer, and this document applies it. It does not amend it and it does not add to it.

Read-only against the method lab: no trial recorded, N unmoved at 110, no test-window look spent,
no `config_digest` changed, no roster row edited.

---

## 0. In plain words

Five strategies are paper-trading. One of them, **MOM**, was flagged as the likely weakest and
worth replacing with a better one from the method lab. It was checked properly. The answer is
**keep it**, and the three reasons were measured rather than argued:

- **It is not the weakest.** Of the four non-benchmark quant strategies, **MVW scores lower than
  MOM on both of the measures the lab uses** — the luck test and the return-per-unit-of-worst-fall
  ratio. The premise of the question does not survive the data.
- **One of the three complaints against it has stopped being true.** It was said to need the
  longest wait before anyone could judge it — 20.7 months, against about 15 for two others. That
  was a consequence of a rule the owner has since replaced. Every strategy now reaches its verdict
  at 18 months, flat, whatever its trading rate. The complaint is void.
- **Every better-scoring replacement is a near relative of strategies already on the board.**
  Eleven lab candidates outscore MOM on the luck test. All eleven come from the same family of
  methods — the one RMW and RAW already occupy, two of the five slots. Swapping MOM for the best of
  them would raise the roster's average score and leave it holding three settings of one idea.

And one fact that points the other way, written down because a document that only lists reasons for
its own conclusion is an argument, not evidence: **nothing has traded yet**, so a swap will never
again be as cheap as it is today. That was weighed and did not win. §6 says why.

---

## 1. The verdict

**Keep `MOM-FR`. No roster change, no new paper clock, no code change.**

Decided under the rule in `docs/plans/2026-10-04-method-lab-design.md` §8. The rule's trigger
conditions are checked one by one in §2; none of them is met. The rule's refusals are listed there
too, and the argument that was actually on the table — *a lab candidate now scores higher* — is one
of the things it refuses.

This verdict is about **MOM-FR only**, because Q3 asked about MOM-FR only. §7 records the one
question it opened and deliberately did not answer.

---

## 2. The rule, condition by condition

Phase 3's rule names five triggers (§8.3) — the circumstances under which an entry *may* be
replaced — and three refusals (§8.2) — the arguments it rules out on their own. All eight, in the
rule's own words and in the rule's own order:

| §8 condition | kind | met for `MOM-FR`? | evidence |
|---|---|---|---|
| **T1** — the book is broken, or is not the book that was admitted | trigger | **no** | No defect has been found in the strategy, the allocator, the trade rules or the evidence code. Its pinned `spec_digest` is unmoved and it has traded nothing that could have diverged from what was described (§8 of this document). |
| **T2** — the forward record fails on its own terms | trigger | **no — and cannot be yet** | There is no forward record. Zero paper sessions have run for any entry (§6, point 1). The rule's earliest honest date for T2 is the entry's own 18-month mark, and its one carve-out — a realised drawdown past 20% on paper — needs a paper drawdown that does not exist. |
| **T3** — the entry can never satisfy design §1 at all | trigger | **no** | Its dev-window worst fall is **18.37%**, inside the owner's 20% limit — unlike `F4-MOM12-N20-TREND-FR` at 22.2%, which that bar refuses permanently (§3). The other recorded T3 retirement turned on the ≥ 100 closed trades clause, which the owner deleted on 2026-10-07 (§4.1); `MOM-FR` closed 1,148 dev-window trades regardless. |
| **T4** — the forward record is not a record of the strategy | trigger | **no — and cannot be yet** | Same reason as T2: no paper night has run, so there is no record to be corrupt, no missed session and no stale input (§6, point 1). |
| **T5** — the owner decides | trigger | **not fired** | The owner asked, in Q3, for `MOM-FR` to be *checked*; no instruction to remove it has been given. T5 sits above this rule and this document, and nothing here constrains it — if it fires later, §8.3 T5 asks only that the reason be written on the entry. |
| **R1** — "its DSR fell below the bar" | refusal | **applies** | `MOM-FR`'s luck score is 0.8278 against the 0.90 bar, and it fell from 0.854 at N = 80 to 0.828 at N = 110 (§3). The rule refuses this by name: lab design §7.3 measures `RMW-FR` itself crossing the same bar downward at N = 143 with no book changing a line (§6). |
| **R2** — "another candidate now scores higher" | refusal | **applies — this is the argument that prompted the question** | Eleven candidates outscore `MOM-FR` on the luck test and two of them clear every owner condition as well (§5). That is the entire case for a swap (§6, points 2 and 3), and §8.2 R2 refuses it on its own: 26 of 110 trials clear all five conditions today and that number only grows. |
| **R3** — "it is behind SPY" / "it had a bad run" | refusal | **applies** | Q3's second complaint is `MOM-FR`'s −2.3 points in 2009–2015 (§4.2) — one losing stretch on the dev window, with T2 unable to fire for 18 months. The rule's measurement: these books beat SPY in only 50–59% of quarters even when working. |

No trigger fires. At least one refusal applies directly to the argument that prompted the question.
That is the whole decision; §§3–6 are the evidence behind the cells.

---

## 3. What the method lab actually says today (measured)

Every one of the 110 recorded dev-window trials was re-judged **at today's bars** — not at the bars
written on the row, which are stale. All 110 rows record the old `DSR >= 0.95` label and the old
15% drawdown limit; the owner moved both on 2026-10-07. The four threshold conditions are
recomputed from each row's recorded numbers against the constants in force now, which is exactly
what `lab.store.owner_failures` and `lab.store.verdict` are for.

Reproduce (read-only, writes nothing, records no trial, does not move N):

```
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules
PYTHONPATH=$PWD/engine/src /home/miftah/seer/engine/.venv/bin/python - <<'PY'
import sqlite3
from seer_engine import config
from seer_engine.lab import store

LAB = config.REPO_ROOT / "lab" / "lab.sqlite"
conn = sqlite3.connect(f"file:{LAB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
g = store.gate(conn)
rows = conn.execute("SELECT * FROM trials WHERE window='dev'").fetchall()
clear = [(r, store.verdict(conn, r, at=g)) for r in rows if not store.owner_failures(r)]
print(f"N={g.n} policy={g.policy} dev_trials={len(rows)} clear_all_five={len(clear)}")

def key(pair):           # a luck test that could not be evaluated is not a high one: NULL last
    v = pair[1]
    return (v.dsr is None, -(v.dsr or 0.0))

bydsr = sorted(clear, key=key)
bymar = sorted(clear, key=lambda p: -float(p[0]["mar"]))
ids = [r["candidate_id"] for r, _ in bydsr]
mids = [r["candidate_id"] for r, _ in bymar]
print(f"MOM-FR (M0002-REL-85): DSR rank {ids.index('M0002-REL-85')+1} of {len(ids)}, "
      f"MAR rank {mids.index('M0002-REL-85')+1} of {len(mids)}")
for name, cid in (("RMW-FR","M0022-W-TV16"),("RAW-FR","M0007-N20-RAW"),
                  ("MOM-FR","M0002-REL-85"),("MVW-FR","M0008-N30-C07")):
    r, v = next(p for p in clear if p[0]["candidate_id"] == cid)
    print(f"  {name:7s} {cid:22s} dsr={v.dsr:.4f} mar={float(r['mar']):.3f} "
          f"cagr={float(r['cagr'])*100:.2f}% dd={float(r['max_drawdown'])*100:.2f}% "
          f"trades={r['trades']} pf={float(r['profit_factor']):.3f} eligible={v.eligible}")
print("above MOM-FR by the luck test, with the lab method each came from:")
for r, v in bydsr[:ids.index("M0002-REL-85")]:
    print(f"  {r['candidate_id']:22s} {r['method_id']:6s} dsr={v.dsr:.4f} "
          f"mar={float(r['mar']):.3f} eligible={v.eligible}")
PY
```

**Twenty-six of the 110 clear all five owner conditions today.** Of those 26, `MOM-FR` is **12th on
the luck test** and **8th on MAR** — return per unit of worst fall, the lab's one risk-adjusted
ranking.

The four quant roster entries, as the lab reads them now:

| roster entry | lab candidate | luck test (DSR) | MAR | return/yr | worst fall | trades | profit factor |
|---|---|---|---|---|---|---|---|
| `RMW-FR` | `M0022-W-TV16` | **0.9156** | 0.816 | 11.68% | 14.31% | 1,589 | 2.065 |
| `RAW-FR` | `M0007-N20-RAW` | 0.8985 | 0.768 | 15.05% | 19.59% | 1,596 | 2.163 |
| `MOM-FR` | `M0002-REL-85` | 0.8278 | 0.684 | 12.56% | 18.37% | 1,148 | **2.332** |
| `MVW-FR` | `M0008-N30-C07` | **0.7802** | **0.564** | 11.27% | 19.97% | 1,223 | 2.143 |

Three plain readings of that table:

1. **`MVW-FR` is below `MOM-FR` on both measures** — 0.780 against 0.828 on the luck test, 0.564
   against 0.684 on MAR. Whatever "weakest of the five" means, the lab's own numbers do not point
   at MOM.
2. **`MOM-FR` has the highest profit factor of the four** (2.332 — it makes $2.33 on winners for
   every $1 lost on losers), and it does it on the fewest trades, which is what a selective book
   looks like rather than what a weak one looks like.
3. **Three of the four are not dev-eligible today, including `RAW-FR` at 0.8985** — 0.0015 below
   the bar. The roster was never admitted on the lab's gate; it was admitted on the owner's
   judgement, with the lab's reading recorded alongside (`paper/roster.py`, `LAB_PROVENANCE`, and
   `docs/plans/2026-10-04-method-lab-design.md` §7.4). That is the standing policy, not an
   exception made for MOM.

> **One correction to the record.** The first drafts of
> `20261007-170515-0CU0_code_analyzer.md` §M3 and of the plan index both said `MOM-FR` ranks
> *7th by MAR*; both were corrected on 2026-10-07 and this note records why. Re-measured by the
> command above, seven candidates have a
> strictly higher MAR (0.8567, 0.8161, 0.7927, 0.7911, 0.7684, 0.7631, 0.7500) against MOM-FR's
> 0.6840, so it ranks **8th of 26**. The luck-test rank, 12th of 26, is confirmed exactly. The
> conclusion is unchanged; the number is.

---

## 4. Q3's three complaints, checked one at a time

### 4.1 "The slowest path to a verdict (20.7 months)" — **void**

This was the strongest-sounding of the three and it no longer exists.

It came from the old go-live item 1, which asked for ≥ 3 months of paper trading **and** ≥ 100
closed trades. The trade count bound, not the months, so each strategy's real wait was set by how
often it trades: about 15 months for RMW and RAW at ~80 trades a year, 19.4 for MVW, and **20.7 for
MOM** at ~58. MOM was being charged for trading less.

**On 2026-10-07 the owner replaced item 1 with "≥ 18 months of forward paper trading" and deleted
the trade-count clause** (`docs/plans/2026-10-03-seer-design.md` §1 item 1, with the revision note
in §13). Every entry now reaches its verdict at the same 18 months regardless of how often it
trades. MOM's wait fell from 20.7 months to 18; RMW's and RAW's *rose* from ~15 to 18.

So the gap this complaint described is gone, and the direction has partly reversed. **Anyone
reading the earlier handover will still believe it, which is why it is stated here in full rather
than quietly dropped.**

### 4.2 "The least stable of the four quant entries" — **true only on the narrowest reading, and it reverses on the obvious one**

The complaint is about the era table in
`docs/handover/2026-10-07-roster-first-night-and-survivorship.md` §3 — how far each strategy was
ahead of SPY in each of three stretches of the backtest. Those published numbers, subtracted:

| | 1996–2001 | 2002–2008 | 2009–2015 | average | spread (best − worst) |
|---|---|---|---|---|---|
| `RMW-FR` | +0.9 | +9.8 | −2.1 | +2.87 | **11.9** |
| `RAW-FR` | +5.9 | +10.8 | +2.6 | **+6.43** | 8.2 |
| `MOM-FR` | +6.2 | +8.2 | **−2.3** | +4.03 | 10.5 |
| `MVW-FR` | +0.7 | +8.8 | −2.1 | +2.47 | 10.9 |

(points per year ahead of SPY's total return; derived by subtraction from §3's published table.)

`MOM-FR` does own the single worst era number, −2.3. But it is worst **by 0.2 points**, over two
entries that are also behind SPY in that stretch for the same stated reason — §3's own finding that
these strategies earn their advantage in crashes and give some back in calm markets, and 2009–2015
was a bull run with no crash.

On spread — the ordinary meaning of "least stable" — `MOM-FR` is **third of four**, steadier than
both `RMW-FR` (11.9) and `MVW-FR` (10.9). And its average era edge, **+4.03 points a year**, is
higher than either of theirs. The complaint survives only if "least stable" is read as "has the
single lowest number in one of three cells", and under that reading it wins by a rounding margin.

### 4.3 "It was admitted as F4's bet inside the drawdown bar" — **true, and not a complaint**

This one is accurate. `MOM-FR` replaced `F4-FR`, which carried the same total-return-momentum bet
(measured at 0.99 correlation with F4's own variant) at a 22.2% worst fall that the owner's revised
20% limit refuses permanently. `MOM-FR` carries that bet at 18.37%.

That is a description of why it is on the roster, not an argument against it. The roster was
assembled as a **set of independent forward experiments**, not as a ranked list — migration
`db/migrations/013_roster_first_night.sql`'s own note says so: *"the slots are not bought for
ensemble performance, which is not on offer; they are bought as independent forward experiments
that could each reach real money."* A slot held for a particular bet is doing its job by holding
that bet.

**Two of the three complaints do not survive measurement, and the third is a description.**

---

## 5. What a swap would cost, which no column in §3 prices

Eleven lab candidates outscore `MOM-FR` on the luck test. Here they are with the method each came
from:

| candidate | lab method | luck test | MAR | dev-eligible today |
|---|---|---|---|---|
| `M0022-W-TV16` *(this is `RMW-FR`, already on the roster)* | M0022 | 0.9156 | 0.816 | yes |
| `M0020-W-NOSTOP` | M0020 | 0.9127 | 0.793 | **yes** |
| `M0022-W-TV14` | M0022 | 0.9122 | 0.857 | **yes** |
| `M0007-N20-RAW` *(this is `RAW-FR`, already on the roster)* | M0007 | 0.8985 | 0.768 | no |
| `M0011-RAW20-TV14-N21` | M0011 | 0.8844 | 0.763 | no |
| `M0020-W-S20` | M0020 | 0.8764 | 0.750 | no |
| `M0019-TV14N21-S20` | M0019 | 0.8684 | 0.791 | no |
| `M0019-RAW20-S15` | M0019 | 0.8540 | 0.680 | no |
| `M0020-W-TV14N21-S20` | M0020 | 0.8492 | 0.614 | no |
| `M0011-RAW20-TV16` | M0011 | 0.8387 | 0.658 | no |
| `M0007-N30` | M0007 | 0.8349 | 0.628 | no |

**All eleven are the same family.** M0007 is residual momentum — ranking stocks on how far they
rose *beyond what the market explains*, rather than on how far they rose. M0011, M0019, M0020 and
M0022 are each a descendant of it: M0011 adds a volatility brake, M0019 adds per-stock stops, M0020
lets a stopped stock come back at the next weekly check, M0022 re-reads M0011's brake every week.
Two of them are already on the roster — `RMW-FR` is M0022 and `RAW-FR` is M0007, held against each
other as the deliberate controlled test of whether the brake pays for itself.

Not one candidate from outside that family scores above `MOM-FR`.

So the two best-scoring alternatives are:

- **`M0022-W-TV14`** — literally `RMW-FR`'s own method with the brake set at 14% instead of 16%.
  Putting it on the board means paper-trading two settings of one dial for 18 months.
- **`M0020-W-NOSTOP`** — the weekly-check branch of the same residual-momentum line, with the stops
  removed. 15.27% a year at a 19.27% worst fall: a genuinely attractive book, and still the same
  underlying bet as two of the four slots.

`MOM-FR` is the roster's **only** strategy that ranks on plain total return *and* varies its
exposure by its own volatility regime — it holds less when it is jumpier than its own normal, and
stays fully invested otherwise. `MVW-FR` also ranks on total return but changes the *weights*
rather than the exposure, and was admitted precisely as the one portfolio-construction bet. Remove
`MOM-FR` and that reading disappears from the board entirely.

The lab can rank books. It cannot price the diversity of a set, because no candidate is scored
against the other four slots. **The swap on offer raises the roster's average lab score and
collapses what the roster was built to measure.**

---

## 6. The case for swapping, stated fairly

This document would be an argument rather than evidence if it listed only reasons for its own
conclusion. The strongest case against the verdict:

1. **A swap will never be cheaper than today.** No roster entry has traded a single paper session.
   There is no track record to discard and no clock to restart — the 18 months has not begun for
   anyone. Once the first session runs, replacing `MOM-FR` costs its accumulated record and resets
   its clock to zero, and that cost only grows. **The cheapest moment to be wrong about this is
   now.**
2. **Two of the alternatives are fully dev-eligible and `MOM-FR` is not.** `M0020-W-NOSTOP` and
   `M0022-W-TV14` clear every owner condition *and* the luck test. `MOM-FR` clears the five owner
   conditions and misses the luck test at 0.828 against 0.90. That is a real difference in what the
   lab is willing to say about them, not a technicality.
3. **`M0020-W-NOSTOP` is better on the numbers that matter most for a real-money decision**:
   15.27% a year against `MOM-FR`'s 12.56%, at a 19.27% worst fall against 18.37% — about 2.7 more
   points of annual return for about 0.9 more points of fall.

**Why it did not win.** The swap argument is, at bottom, *a lab candidate now scores higher than a
roster entry* — which is the exact argument §8 was written to refuse, by a session that wrote
it before seeing these numbers and specifically so that it would not be written to justify a swap
somebody already wanted. §7.3 of the same document is why the refusal exists: the luck test falls
for everything as the lab keeps searching, with no book changing at all. `RMW-FR` itself scores
0.9156 today and drops below 0.90 at **N = 143** — roughly a day and a half of exploration. In a
few nights the same spreadsheet will say `RMW-FR` should be replaced too, and then its replacement,
and nothing in any book will have changed.

The cheapness argument in (1) is real and it cuts the right way, but it argues for *acting now*; it
does not supply a reason to act. The reasons on offer are (2) and (3), and both are lab scores.

---

## 7. What would change this verdict

The named triggers in §8 are the list; this is only where to look for them in `MOM-FR`'s case.
What is **not** on the list: a lab candidate scoring higher, `MOM-FR`'s own luck score falling as
the lab keeps searching, or a better-looking book turning up in the same family.

**One question this document deliberately did not answer.** §3 shows `MVW-FR` scoring below
`MOM-FR` on both measures — 0.780 against 0.828 on the luck test, 0.564 against 0.684 on MAR. That
makes `MVW-FR` the lowest-scoring quant entry on the board, and it was not examined here, because
Q3 asked about `MOM-FR`. It should not be examined on these numbers alone either: `MVW-FR` was
admitted as the roster's only bet on *how much of each stock to hold* rather than on which stocks,
and as the least correlated with `RMW-FR` of anything that passed the five conditions. Whoever picks
this up: start from §8, not from the ranking.

---

## 8. What this phase did not touch

- **The rule itself** — `docs/plans/2026-10-04-method-lab-design.md` §8 was read and applied,
  never amended.
- **`lab/lab.sqlite`** — opened read-only by URI. No trial, no insight. N is 110 before and after,
  and 0 test-window looks are spent before and after.
- **`engine/src/seer_engine/paper/roster.py`** — unchanged. No entry's `spec_digest` moved and no
  paper clock started or reset.
- **`engine/.research`** — unchanged; no `config_digest` moved.
- **Design §1 and §5**, and every file session `seer-fc` claimed.
- **The leaderboard hero figure** — §4 of the first-night handover says no work may be opened on it
  without re-checking the page first. None was.

## 9. Verification

```
cd /home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine
PYTHONPATH=/home/miftah/.worktrees/seer/delisting-stress-roster-rules/engine/src \
PG_TEST_URL=postgresql://postgres:pg@localhost:55432/postgres \
  /home/miftah/seer/engine/.venv/bin/python -m pytest -q      # 0 failed, 0 skipped
```

`pytest` **without** `PG_TEST_URL` reports `2812 passed, 385 skipped` — a confident green missing a
third of the suite, including every test that reads the `strategies` table. Always export it. And
without `PYTHONPATH` pointing at this worktree's `engine/src`, pytest silently tests the main
checkout instead of this branch.

The number that matters is **0 failed and 0 skipped**, not a total: this branch's baseline is 3197
and sibling work adds to it.

The lab, before and after this document: **N = 110 dev trials, 0 test-window looks used.**
`python -m seer_engine lab status` confirms it.
