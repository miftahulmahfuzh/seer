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
