# Handover — 2026-10-18: company size for firms with more than one share class

**Session:** `sera-20261018-0517` (Sera batch, owner theme "books shaped like the market")
**Branch:** `main` @ `51a5cba` — clean, pushed, nothing in flight
**Lab:** 732 trials · 240 methods · N = 146 · **test-window looks 4, unchanged**
**Nothing was promoted. No test look was spent.**

---

## What the batch found (synthesis = insight 401)

Four size-weighted methods, each beside a size-weighted random control, both stores:

| Method | Verdict | Owner money vs SPY 7.2% | 2009-15 vs SPY |
|---|---|---|---|
| M0047 momentum picks by market value (10% cap) | rejected direction; gate refused (1/4 folds + test-failed kin) | 11.2% (equal slots 13.7%) | −2 to −3 |
| M0201 bond-like picks by market value, switched | gate refused (2/4 folds) | 9.2% | ≈ −8 |
| M0221 top-N by market value, the yardstick | rejected as strategy, kept as ruler; gate refused (1/4) | 7.8% (C50-SW) | ≈ −8 |
| M0222 top-50 cap core tilted toward dividend raisers | rejected | 7.1% (TILT2-T) | −8.2 |

No buy signal. Answer to the owner: market-shaped weighting does not close the post-2009 gap in
our data, and pickers add little once size-weighted (their edge lives in mid-sized names).

**The key finding is about the data, not the market (insight 398).** The plainest market copy
(M0221) trailed SPY ~2 pts/yr, 5-6 in 2009-2015, even fee-free, because the store has no size for
several of that decade's biggest winners. So the ruler is bent, and every member book starts
2009-2015 behind SPY before it picks anything.

## The task for this session: fix multi-class share counts (insight 399, unblocks M0225)

**No purchase needed.** The source is free SEC EDGAR. The owner asked; the answer was no.

Evidence from the stores (rows in `shares.csv`, same in `.research` and `.research-sv`):

```
META 0   FB 0   V 6   MA 12   BRK.B 8   (a normal member has dozens)
CMCSA 62  UPS 36  (present but the batch saw gaps around 2012)
```

Prices are NOT the problem for the check store: CELG, ESRX, WBA, TWX have full bars in
`engine/.research-sv` (EODHD, key valid to **2026-11-10** — finish before then in case any name
needs a refetch). They are missing only from the dev store, which is by design.

What is wrong, per the size-accessor notes in
`.claude/skills/explore-and-experiment-new-method/SKILL.md` and insight 399:
1. Companies that tag `dei:EntityCommonStockSharesOutstanding` **per class** (class-axis
   dimension) in XBRL go unknown — Alphabet from 2014, Meta, Visa, Mastercard, Ford, ~20 more in
   2012. Sum the classes (or use the cover total), point in time, from the filing date.
2. **BRK.B 2010-11** counts class A only. Convert: 1 A = 1,500 B (1 A = 30 B before the 2010
   50:1 B split). Value the company once.
3. Two listed classes (GOOG/GOOGL, FOX/FOXA, NWS/NWSA) each answer whole-company count × that
   class's price. Better: each listed class valued at its own count × its own price, so a
   method can weight the company once without a hand-kept list.

Code lives in `engine/src/seer_engine/shares/` (`cover.py` already sums classes on pre-2010 cover
pages; `checks.py` drops class fragments; `integrate.py` joins XBRL facts; `store.py`/`build.py`
write `shares.csv`). `Market.shares_on` / `market_value` are in `backtest/market.py`.

Rules that bind (CLAUDE.md):
- `research.refresh_shares` must keep every other store file byte for byte: the **price
  fingerprint must not move**, so recorded trials still compare. Only `shares.csv` changes, and
  the store fingerprint will move from `b683da41` — say so in the commit.
- No look-ahead: a figure is usable only from its filing date.
- Refresh all three stores (`.research`, `.research-sv`, and the test-window store) and push via
  the `sync-research-store` skill.
- Tests must not reach production; DB tests need Postgres (`PG_TEST_URL`).

**Done means:** META/V/MA/GOOGL/BRK.B have continuous point-in-time counts 2009-2015 with the
right magnitude (spot-check Apple ≈ $560B and Meta ≈ $200B on 2014-06-30, Visa ≈ $130B,
Berkshire ≈ $310B); `shares store-report` coverage of 2009-2015 member-days rises; then
`lab unblock M0225` and record a `lab note` with the new coverage. Running M0225 itself is a
lab run (pre-register first) and can go to the next Sera batch.

## Other leftovers

- **Queued ideas from this batch:** M0223 (momentum inside each size band), M0224 (bond-like tilt
  on a cap core — child expects it to close the family; low priority), M0226 (dividend-raise
  tilt on every member at real size). Next-batch slate in insight 401: rebuilt ruler (M0225),
  M0226, M0223, and SPY core + best equal-weight picker as a small side bet (backlog M0031/M0049).
- **Feature wish (insights 391, 397):** a standing size-weighted random twin of the same shape
  for every method, so children stop hand-building the control.
- Not this session's: an older idle `sera-20261017-1625` tmux window and four
  `.claude/worktrees/agent-*` worktrees. Leave them unless their owners are confirmed gone.

---

## Close-out — 2026-10-18 (branch `feature/multi-class-company-size`)

Done. Per-class share counts come from each filing's own XBRL instance (free SEC EDGAR), point in
time from the filing date; Berkshire A is counted as 1,500 B (30 before 2010-01-21); each listed
class answers its own count (GOOG/GOOGL, FOX/FOXA, NWS/NWSA sum to the company).

| Store | Fingerprint before → after | Price fingerprint |
|---|---|---|
| `.research` (dev) | `b683da41…` → `704a21fc…` | `5451195f…` unchanged |
| `.research-sv` (check) | `7017e311…` → `1f816759…` | `60adae1b…` unchanged |
| `.research-test` (test) | `b9269bfa…` → `45d0b04d…` | `56e83810…` unchanged |

The new stores were built and verified in `/home/miftah/seer-stage/mcs/` and are moved into
`engine/` and pushed to Blob (`sync_store.py push --store dev|sv|test`) only after this branch is
on `origin/main` (the cutover, phase 3 Step 11, run by whichever session lands it). **Other
machines must pull all three and update to main at or after that merge** — older code refuses the
new `xbrl-class` rows. Sera worktrees branched before the merge must rebase onto main before their
next `lab run`.

Dev store, index member-days 2009-2015:

| Year | Share count before → after | Market value before → after |
|---|---|---|
| 2009 | 93.4% → 93.5% | 61.7% → 61.8% |
| 2010 | 95.7% → 95.9% | 65.1% → 65.1% |
| 2011 | 96.1% → 97.0% | 66.2% → 66.9% |
| 2012 | 91.0% → 97.2% | 64.7% → 69.0% |
| 2013 | 91.0% → 97.8% | 66.4% → 71.4% |
| 2014 | 90.8% → 97.9% | 67.7% → 72.8% |
| 2015 | 89.8% → 97.8% | 68.7% → 74.5% |

Member-days with a close but no count, 2009-2015: 45,339 (138 symbols) → 19,407
(62 symbols). META, V, MA, GOOGL, GOOG and BRK.B: none.

Spot checks 2014-06-30 ($B): Apple 560.3 (was 560.3), Meta 172.7, Visa 132.4, Berkshire 312.2,
GOOGL+GOOG 391.2 (197.2 + 194.0); Mastercard 85.8, Comcast 139.6, UPS 94.0, Ford 68.2.

Still without a count (by design or by the filings): foreign 20-F/40-F filers (BIDU, CHKP, VOD,
INFY, TEVA, …), successor tickers (PSKY, VTRS, DXC), and:
- NWSA 2013-07-01 .. 2013-11-11 (94 days): the new News Corp was spun off 2013-06-28 and its first
  count is its 10-Q of 2013-11-12.
- LBTYA 2009-2013 (235 days): the ticker map names no filer for LBTYA between 2009-12-21 and
  2012-12-24, and Liberty Global plc's first count is its 10-Q of 2013-08-01; plus the weeks before
  the old Liberty Global's first instance count of 2009-05-05.
- Test window: FOX/FOXA 2019-03-18 .. 2019-05-09 (38 days): Fox Corp's first 10-Q tags a figure
  without its classes, which the class table cannot split.

Readings the class table could not attribute: LiLAC (LILA/LILAK) on Liberty Global's 10-Q of
2015-05-07 and the Braves (BATRA/BATRK) on Liberty Media's first 2016 10-Q. Both counts are dated
before the tracking stock existed, so those lines stay unknown until the next count names them.
Multi-class filers summed one for one: 103 (list in the staged `logs/store-dev.txt`); each was read
once, and all convert share for share except Kinder Morgan's, now in the table.

Known limits, accepted:
- For about three weeks after each class C stock dividend (Alphabet 2014-04-03, Under Armour
  2016-04-07) both lines answer the whole company until the first count that lists class C, so the
  company counts twice across GOOGL+GOOG (UAA+UA) in those weeks.
- Before 2014-04-03 the index lists Google's one listed class under both GOOG and GOOGL, and both
  answer the identical whole-company count (2009-01-02 .. 2014-03-26 in the dev store; the old store
  did the same to 2015-04-24). Older methods' "identical share count" dedupe collapses exactly this.
- Perrigo 2013-11-04 .. 2014-02-05: the ticker map hands PRGO to the new Irish parent at its first
  10-Q, filed before the Elan merger made it the listed company, so PRGO reads 23.0M shares (the
  shell's) for three months instead of ~94M. A ticker-map matter, left alone here.

Lab: M0225 back to `idea` with a plain-words note (`lab unblock`). Running it is a lab run for the
next Sera batch (pre-register first). Existing methods are untouched.

Engine fixes the real run needed:
- `share_classes.csv`: Visa's (2009-11, 2010-01) and Discovery's (2010-02) class A tagged without
  the axis, and Kinder Morgan's 2011-12 sponsor classes B/C at ratio 0 (summed one for one they
  made KMI ~14% too large).
- `store.usable_class_rows`: seven filers' tagging errors left out (Marriott, Sprint, Viacom x2,
  Perrigo x2 at a thousand or a million times their count; TripAdvisor's class B alone).
- `history.ONE_FOR_ONE_SUCCESSORS`: GOOG/GOOGL answer Google's last count across the 2015-10-02
  Alphabet reorganisation until Alphabet's first 10-Q (11 dev-window sessions were unknown).
- One extra `download-classes --cik 0001316631` (the old Liberty Global), whose 2009-11 10-Q had a
  class-A-only companyfacts figure and so was not selected.

Cleanup: `/home/miftah/seer-stage/mcs/old/` (the three previous stores, written at cutover) can go
a week after the cutover if nothing was rolled back.
