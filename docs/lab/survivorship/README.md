# Survivorship check: how much the missing dead companies flattered the lab

*Measured 2026-10-10. Report only: no trial was recorded, the lab's trial count (276) and its
test-window looks (4) did not move. The grid behind every number here is `grid.csv` in this folder.*

## What was measured

Every lab result was measured on a price history that holds about 59% of the days a company sat
in the S&P 500 or the Nasdaq-100 between 1996 and 2015. Most of what is missing are the companies
that later died: bankruptcies, buyouts and renamed tickers. In October 2026 we bought one month of
EODHD's US price history, cleaned it (split-adjusted; tickers that a different company later reused
were cut to the right company's years; absurd data errors repaired or dropped; real collapses kept),
and built a second copy of the 1996-2015 history with those companies added back. Then every
method below was re-run, variant by variant, on both copies, on the same money and the same
monthly top-ups as its recorded run. All 102 dev re-runs reproduced their recorded result exactly,
so every difference below comes from the added companies and nothing else.

The second copy (the "check" history) lives only on the PC, at `engine/.research-sv`. It is built
offline from the EODHD cache with
`python -m seer_engine survivorship_store --build --out <abs>/engine/.research-sv --source <abs>/engine/.research`.
The raw vendor data is under a personal licence and is never committed.

## How much of the index each history can price

Share of index-member days with a price, by year (from the check store's `coverage_report.txt`):

| year | member-days | dev store covered | check store covered |
|---|---|---|---|
| 1996 | 123,539 | 39.9% | 47.0% |
| 1997 | 123,372 | 42.1% | 49.1% |
| 1998 | 123,485 | 45.5% | 84.4% |
| 1999 | 123,695 | 47.4% | 86.9% |
| 2000 | 124,001 | 48.8% | 87.8% |
| 2001 | 122,786 | 50.6% | 87.6% |
| 2002 | 124,665 | 52.2% | 88.6% |
| 2003 | 124,487 | 53.9% | 90.0% |
| 2004 | 124,677 | 54.8% | 92.7% |
| 2005 | 124,961 | 55.7% | 93.0% |
| 2006 | 124,746 | 58.4% | 93.9% |
| 2007 | 136,484 | 60.1% | 94.5% |
| 2008 | 137,747 | 62.5% | 95.7% |
| 2009 | 135,625 | 65.4% | 96.8% |
| 2010 | 133,940 | 67.8% | 97.5% |
| 2011 | 133,361 | 68.9% | 97.7% |
| 2012 | 131,629 | 70.7% | 97.9% |
| 2013 | 132,197 | 72.9% | 98.1% |
| 2014 | 131,966 | 74.5% | 98.7% |
| 2015 | 104,913 | 76.2% | 98.8% |
| all | 2,542,276 | 58.6% | 89.0% |

- Still missing after the fill: 111 members, worth 123,635 member-days (4.9% of all member-days).
- The alias fill found another code for 128 of the 200 members the first build could not use
  (`alias_report.csv`, `accepted = yes`); 43 had no candidate code in EODHD's symbol lists at all,
  and 29 had candidates that did not fit (no bar on a member day, or two equally good fits).
- 39 members the dev store does serve have no price on any of their index days (the code now
  names a later company); they are not repaired here and count as missing.
- Cleaning of the 522 symbols the dev store could not serve: 291 series kept as they were, 92
  repaired, 67 trimmed to the right company's years, 72 dropped (each with its reason in
  `cleaning_report.csv` inside the store). 128 of the 450 that were used came through the alias
  fill.
- 1996 and 1997 stay thin (47.0% and 49.1% covered): EODHD's histories for dead companies mostly
  start on 1997-12-31. From 1998 on the check history prices 84-99% of member-days.

## What changed, by kind of method

Change = check history minus dev history, in percentage points a year of funded growth on the
owner's money. The drawdown bar is the lab's 20%.

| kind | methods | variants | not reproduced | CAGR change, mean (pt/yr) | median | worst | best | beat SPY: dev -> check (lost / gained) | worst fall within 20%: lost / gained | 2009-15 edge sign flips (+->- / -->+) | worst fall change, mean (pt) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| buying long-term losers | 1 | 5 | 0 | -1.4 | -1.3 | -2.6 | +0.1 | 5 -> 3 (2 / 0) | 0 / 0 | 0 / 0 | -0.4 |
| momentum book | 7 | 26 | 0 | -1.1 | -1.1 | -1.8 | +0.2 | 26 -> 24 (2 / 0) | 9 / 0 | 1 / 0 | +2.6 |
| momentum + calm-stock blend | 2 | 4 | 0 | -1.0 | -1.0 | -1.1 | -0.9 | 4 -> 3 (1 / 0) | 0 / 0 | 1 / 0 | +1.2 |
| earnings-jump book | 1 | 5 | 0 | -0.6 | -1.1 | -2.1 | +1.2 | 2 -> 2 (0 / 0) | 0 / 0 | 1 / 0 | +4.3 |
| dividend-date methods | 11 | 62 | 0 | -0.1 | -0.2 | -1.6 | +1.5 | 40 -> 40 (1 / 1) | 2 / 0 | 3 / 2 | +0.9 |
| ALL | 22 | 102 | 0 | -0.5 | -0.5 | -2.6 | +1.5 | 77 -> 72 (6 / 1) | 11 / 0 | 6 / 2 | +1.4 |

Headline: across all 102 variants funded growth fell by 0.5 points a year on average. The
stock-picking books (momentum, the blends, long-term losers, earnings jumps) lost about 1 to 1.4
points a year; the dividend-date methods barely moved (-0.1). Worst falls got deeper by 1.4 points
on average (2.6 for the momentum books), and 11 variants that stayed inside the 20% worst-fall line
on the dev history crossed it on the check history. None came back inside. Profit factor fell from
1.98 to 1.80 on average; the DSR from 0.70 to 0.68.

Verdicts that changed:

- **Crossed the 20% worst-fall line:** M0007-N10 (19.7% → 21.4%), M0007-N20-RAW (19.6% → 23.5%),
  M0019-RAW20-S15 (18.6% → 24.5%), M0020-W-NOSTOP (19.3% → 23.4%), M0020-W-S20 (18.9% → 23.4%),
  M0033-TV14-N63, -TV18-N21, -TV20-N21, -TV22-N21 (19.4-20.0% → 20.1-22.4%), M0083-A-UP
  (19.9% → 22.2%), M0083-X-UP-D (19.9% → 20.1%). M0032-N20-RAW-FRAC-GT, already over, went
  20.6% → 25.0%.
- **Stopped beating SPY:** M0011-RAW20-TV12, M0021-B50-TV14, M0022-W-TV14-SW, M0069-L60-N20,
  M0069-W60-N20, M0082-X-N20 (all were less than 2 points a year ahead of SPY on dev). **Started:** M0051-Y20-T.
- **Walk-forward folds won (of 4) fell:** M0019 3 → 2, M0029 3 → 2, M0033 3 → 2, M0063 3 → 1,
  M0069 2 → 1, M0077 3 → 1. **Rose:** M0081 1 → 2.
- **2009-2015 lead over SPY changed sign:** turned negative for M0020-W-S20, M0029, M0063-M-N20-TREND
  and M0077's three EDJ variants; turned positive for M0070-R10-H6 and M0086-HOST.

The roster's best momentum book (M0007-N20-RAW) still beats SPY by a wide margin on the check
history (13.6% a year against 7.9%), but its worst fall is no longer inside the 20% bar.

## Method by method

| method | kind | variant | CAGR dev | CAGR check | SPY | worst fall dev | worst fall check | 2009-15 edge dev | check | folds dev | folds check | reproduced |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M0007 | momentum book | M0007-N10 | +10.1 | +9.9 | +7.9 | +19.7 | +21.4 | -3.6 | -4.5 | 3/4 | 3/4 | yes |
| M0007 | momentum book | M0007-N20 | +10.7 | +10.9 | +7.9 | +16.9 | +16.0 | -4.9 | -2.9 | 3/4 | 3/4 | yes |
| M0007 | momentum book | M0007-N20-NOTREND | +9.9 | +9.3 | +7.9 | +51.0 | +55.9 | -1.2 | -0.2 | 3/4 | 3/4 | yes |
| M0007 | momentum book | M0007-N20-RAW | +15.0 | +13.6 | +7.9 | +19.6 | +23.5 | +2.7 | +1.5 | 3/4 | 3/4 | yes |
| M0007 | momentum book | M0007-N30 | +10.8 | +10.6 | +7.9 | +17.3 | +17.7 | -3.2 | -4.4 | 3/4 | 3/4 | yes |
| M0011 | momentum book | M0011-RAW20-TV12 | +8.0 | +7.2 | +7.9 | +13.3 | +14.2 | -6.3 | -7.4 | 2/4 | 2/4 | yes |
| M0011 | momentum book | M0011-RAW20-TV14 | +9.3 | +8.4 | +7.9 | +15.4 | +16.9 | -4.6 | -5.3 | 2/4 | 2/4 | yes |
| M0011 | momentum book | M0011-RAW20-TV14-N21 | +10.8 | +9.8 | +7.9 | +14.1 | +16.7 | -3.3 | -3.9 | 2/4 | 2/4 | yes |
| M0011 | momentum book | M0011-RAW20-TV16 | +10.7 | +9.6 | +7.9 | +16.3 | +19.4 | -2.5 | -3.5 | 2/4 | 2/4 | yes |
| M0011 | momentum book | M0011-RAW30-TV14 | +8.8 | +8.4 | +7.9 | +16.2 | +16.6 | -5.2 | -5.7 | 2/4 | 2/4 | yes |
| M0019 | momentum book | M0019-RAW20-S15 | +12.6 | +10.8 | +7.9 | +18.6 | +24.5 | -1.2 | -2.4 | 3/4 | 2/4 | yes |
| M0019 | momentum book | M0019-RAW20-S20 | +13.5 | +12.0 | +7.9 | +20.3 | +24.4 | +0.6 | +0.2 | 3/4 | 2/4 | yes |
| M0019 | momentum book | M0019-RAW20-S25 | +14.3 | +12.5 | +7.9 | +20.7 | +24.9 | +1.6 | +0.9 | 3/4 | 2/4 | yes |
| M0019 | momentum book | M0019-TV14N21-S20 | +9.9 | +8.9 | +7.9 | +12.5 | +16.8 | -4.9 | -5.2 | 3/4 | 2/4 | yes |
| M0020 | momentum book | M0020-W-NOSTOP | +15.3 | +14.1 | +7.9 | +19.3 | +23.4 | +2.4 | +0.8 | 3/4 | 3/4 | yes |
| M0020 | momentum book | M0020-W-S20 | +14.2 | +13.0 | +7.9 | +18.9 | +23.4 | +1.4 | -0.1 | 3/4 | 3/4 | yes |
| M0020 | momentum book | M0020-W-TV14N21-S20 | +9.9 | +9.2 | +7.9 | +16.2 | +16.8 | -5.3 | -6.1 | 3/4 | 3/4 | yes |
| M0021 | momentum + calm-stock blend | M0021-B50-RAW | +10.9 | +10.0 | +7.9 | +13.7 | +14.6 | -2.2 | -2.8 | 2/4 | 2/4 | yes |
| M0021 | momentum + calm-stock blend | M0021-B50-TV14 | +8.8 | +7.8 | +7.9 | +12.6 | +12.9 | -5.1 | -5.6 | 2/4 | 2/4 | yes |
| M0021 | momentum + calm-stock blend | M0021-B70-RAW | +12.6 | +11.5 | +7.9 | +14.0 | +16.1 | -0.2 | -0.9 | 2/4 | 2/4 | yes |
| M0022 | momentum book | M0022-W-TV14 | +10.6 | +9.2 | +7.9 | +12.4 | +16.2 | -3.0 | -4.4 | 2/4 | 2/4 | yes |
| M0022 | momentum book | M0022-W-TV14-SW | +8.3 | +7.5 | +7.9 | +15.6 | +16.9 | -7.6 | -9.0 | 2/4 | 2/4 | yes |
| M0022 | momentum book | M0022-W-TV16 | +11.7 | +10.1 | +7.9 | +14.3 | +17.5 | -2.0 | -3.2 | 2/4 | 2/4 | yes |
| M0029 | momentum + calm-stock blend | M0029-B70-RAW-FRAC | +13.5 | +12.4 | +7.9 | +18.2 | +19.8 | +0.2 | -0.2 | 3/4 | 2/4 | yes |
| M0032 | momentum book | M0032-N20-RAW-FRAC-GT | +13.7 | +12.1 | +7.2 | +20.6 | +25.0 | +1.1 | +0.0 | 3/4 | 3/4 | yes |
| M0033 | momentum book | M0033-TV14-N21 | +9.8 | +8.6 | +7.2 | +16.4 | +18.4 | -4.4 | -5.1 | 3/4 | 2/4 | yes |
| M0033 | momentum book | M0033-TV14-N63 | +8.8 | +7.6 | +7.2 | +19.4 | +20.1 | -5.5 | -6.3 | 3/4 | 2/4 | yes |
| M0033 | momentum book | M0033-TV18-N21 | +11.6 | +10.0 | +7.2 | +19.9 | +21.1 | -2.1 | -3.1 | 3/4 | 2/4 | yes |
| M0033 | momentum book | M0033-TV20-N21 | +12.2 | +10.6 | +7.2 | +20.0 | +21.9 | -1.3 | -2.3 | 3/4 | 2/4 | yes |
| M0033 | momentum book | M0033-TV22-N21 | +12.5 | +10.9 | +7.2 | +20.0 | +22.4 | -0.9 | -2.0 | 3/4 | 2/4 | yes |
| M0051 | dividend-date methods | M0051-ALL | +5.2 | +4.7 | +7.2 | +58.4 | +60.4 | -3.3 | -4.0 | 1/4 | 1/4 | yes |
| M0051 | dividend-date methods | M0051-ALL-T | +6.5 | +6.6 | +7.2 | +29.2 | +29.7 | -8.3 | -8.4 | 1/4 | 1/4 | yes |
| M0051 | dividend-date methods | M0051-LV20-T | +5.3 | +5.3 | +7.2 | +37.5 | +39.4 | -10.4 | -9.9 | 1/4 | 1/4 | yes |
| M0051 | dividend-date methods | M0051-OFF20-T | +8.3 | +8.1 | +7.2 | +32.9 | +36.3 | -3.2 | -4.0 | 1/4 | 1/4 | yes |
| M0051 | dividend-date methods | M0051-Y20-T | +6.8 | +7.6 | +7.2 | +38.3 | +38.6 | -7.5 | -7.3 | 1/4 | 1/4 | yes |
| M0063 | earnings-jump book | M0063-M-N20-TREND | +11.6 | +10.3 | +7.2 | +25.2 | +27.2 | +1.5 | -1.2 | 3/4 | 1/4 | yes |
| M0063 | earnings-jump book | M0063-N20-ALWAYS | +9.2 | +8.2 | +7.2 | +72.7 | +80.1 | +6.8 | +7.8 | 3/4 | 1/4 | yes |
| M0063 | earnings-jump book | M0063-N20-TREND | +5.0 | +6.1 | +7.2 | +35.4 | +32.6 | -6.5 | -6.2 | 3/4 | 1/4 | yes |
| M0063 | earnings-jump book | M0063-N30-TREND | +4.1 | +4.3 | +7.2 | +32.6 | +33.1 | -8.8 | -9.0 | 3/4 | 1/4 | yes |
| M0063 | earnings-jump book | M0063-QUIET-N20-TREND | +2.9 | +0.8 | +7.2 | +32.2 | +46.7 | -12.3 | -13.7 | 3/4 | 1/4 | yes |
| M0069 | buying long-term losers | M0069-L36-N20 | +9.8 | +7.3 | +7.2 | +72.5 | +73.4 | +6.2 | +5.4 | 2/4 | 1/4 | yes |
| M0069 | buying long-term losers | M0069-L60-N20 | +9.0 | +7.0 | +7.2 | +71.4 | +68.9 | +5.2 | +0.1 | 2/4 | 1/4 | yes |
| M0069 | buying long-term losers | M0069-L60-N20-T | +9.8 | +8.5 | +7.2 | +33.8 | +39.1 | -2.3 | -4.3 | 2/4 | 1/4 | yes |
| M0069 | buying long-term losers | M0069-L60-N30 | +7.4 | +7.5 | +7.2 | +71.5 | +69.8 | +2.8 | +2.3 | 2/4 | 1/4 | yes |
| M0069 | buying long-term losers | M0069-W60-N20 | +7.3 | +6.2 | +7.2 | +73.9 | +69.8 | +4.4 | +0.7 | 2/4 | 1/4 | yes |
| M0070 | dividend-date methods | M0070-FLAT-H6-T | +9.5 | +9.2 | +7.2 | +27.2 | +25.6 | -4.9 | -4.3 | 2/4 | 2/4 | yes |
| M0070 | dividend-date methods | M0070-R10-H12-T | +8.2 | +7.6 | +7.2 | +29.2 | +26.7 | -5.4 | -6.0 | 2/4 | 2/4 | yes |
| M0070 | dividend-date methods | M0070-R10-H6 | +8.1 | +9.5 | +7.2 | +55.5 | +53.2 | -1.1 | +2.1 | 2/4 | 2/4 | yes |
| M0070 | dividend-date methods | M0070-R10-H6-T | +8.1 | +7.8 | +7.2 | +29.2 | +26.7 | -5.4 | -5.8 | 2/4 | 2/4 | yes |
| M0070 | dividend-date methods | M0070-R25-H6-T | +10.9 | +10.4 | +7.2 | +21.9 | +22.4 | -3.0 | -3.4 | 2/4 | 2/4 | yes |
| M0076 | dividend-date methods | M0076-A-M | +10.3 | +9.3 | +7.2 | +21.3 | +23.6 | -3.9 | -5.4 | 2/4 | 2/4 | yes |
| M0076 | dividend-date methods | M0076-A-M-D | +10.5 | +10.5 | +7.2 | +21.2 | +21.7 | -3.5 | -3.4 | 2/4 | 2/4 | yes |
| M0076 | dividend-date methods | M0076-A-W | +5.0 | +4.8 | +7.2 | +32.0 | +24.0 | -10.4 | -10.8 | 2/4 | 2/4 | yes |
| M0076 | dividend-date methods | M0076-X-M | +10.9 | +10.4 | +7.2 | +21.9 | +22.4 | -3.0 | -3.4 | 2/4 | 2/4 | yes |
| M0076 | dividend-date methods | M0076-X-M-D | +10.8 | +10.2 | +7.2 | +21.1 | +22.0 | -2.7 | -4.0 | 2/4 | 2/4 | yes |
| M0076 | dividend-date methods | M0076-X-W | +6.1 | +6.0 | +7.2 | +32.7 | +23.7 | -7.8 | -8.8 | 2/4 | 2/4 | yes |
| M0077 | dividend-date methods | M0077-EDJ-ANN | +11.4 | +9.8 | +7.2 | +25.6 | +28.2 | +0.5 | -3.4 | 3/4 | 1/4 | yes |
| M0077 | dividend-date methods | M0077-EDJ-EX | +11.4 | +10.0 | +7.2 | +25.6 | +28.2 | +0.4 | -3.3 | 3/4 | 1/4 | yes |
| M0077 | dividend-date methods | M0077-EDJ-HOST | +11.6 | +10.3 | +7.2 | +25.2 | +27.2 | +1.5 | -1.2 | 3/4 | 1/4 | yes |
| M0077 | dividend-date methods | M0077-REV-ANN | +7.6 | +7.3 | +7.2 | +27.6 | +24.3 | -7.8 | -7.7 | 3/4 | 1/4 | yes |
| M0077 | dividend-date methods | M0077-REV-EX | +7.5 | +7.3 | +7.2 | +27.9 | +24.3 | -7.8 | -7.7 | 3/4 | 1/4 | yes |
| M0077 | dividend-date methods | M0077-REV-HOST | +7.5 | +7.2 | +7.2 | +27.2 | +24.0 | -7.8 | -8.0 | 3/4 | 1/4 | yes |
| M0078 | dividend-date methods | M0078-JOINT-ANN | +3.8 | +3.8 | +7.2 | +32.2 | +33.7 | -11.9 | -11.6 | 1/4 | 1/4 | yes |
| M0078 | dividend-date methods | M0078-JOINT-EX | +3.9 | +3.8 | +7.2 | +32.7 | +33.7 | -11.1 | -10.9 | 1/4 | 1/4 | yes |
| M0078 | dividend-date methods | M0078-RAISE-ANN | +4.1 | +4.2 | +7.2 | +28.8 | +30.5 | -11.4 | -11.1 | 1/4 | 1/4 | yes |
| M0078 | dividend-date methods | M0078-RAISE-EX | +4.2 | +4.4 | +7.2 | +32.2 | +33.6 | -11.3 | -10.4 | 1/4 | 1/4 | yes |
| M0078 | dividend-date methods | M0078-WIN-ANN | +3.3 | +2.7 | +7.2 | +31.7 | +31.0 | -12.6 | -13.1 | 1/4 | 1/4 | yes |
| M0078 | dividend-date methods | M0078-WIN-EX | +2.9 | +2.5 | +7.2 | +30.3 | +28.9 | -12.9 | -13.1 | 1/4 | 1/4 | yes |
| M0079 | dividend-date methods | M0079-ANN-H14 | -0.1 | -1.0 | +7.2 | +50.6 | +49.9 | -14.5 | -17.2 | 1/4 | 1/4 | yes |
| M0079 | dividend-date methods | M0079-ANN-H14-DEC | -0.3 | -0.5 | +7.2 | +49.6 | +53.2 | -15.4 | -15.7 | 1/4 | 1/4 | yes |
| M0079 | dividend-date methods | M0079-ANN-THRU | +1.9 | +1.8 | +7.2 | +34.7 | +36.3 | -13.3 | -13.0 | 1/4 | 1/4 | yes |
| M0079 | dividend-date methods | M0079-ANN-TOEX | +2.0 | +2.6 | +7.2 | +33.1 | +33.5 | -13.1 | -12.2 | 1/4 | 1/4 | yes |
| M0079 | dividend-date methods | M0079-EX-H14 | +0.5 | +0.1 | +7.2 | +62.6 | +58.1 | -12.7 | -14.1 | 1/4 | 1/4 | yes |
| M0079 | dividend-date methods | M0079-EX-H14-DEC | +0.4 | -0.0 | +7.2 | +61.6 | +61.3 | -13.2 | -13.5 | 1/4 | 1/4 | yes |
| M0081 | dividend-date methods | M0081-A-M12 | +8.1 | +9.3 | +7.2 | +27.8 | +32.1 | -7.5 | -7.3 | 1/4 | 2/4 | yes |
| M0081 | dividend-date methods | M0081-A-W12 | +3.8 | +4.6 | +7.2 | +31.1 | +35.5 | -12.2 | -12.5 | 1/4 | 2/4 | yes |
| M0081 | dividend-date methods | M0081-A-W6 | +3.4 | +4.8 | +7.2 | +29.7 | +32.1 | -12.8 | -12.1 | 1/4 | 2/4 | yes |
| M0081 | dividend-date methods | M0081-X-M12 | +8.0 | +9.1 | +7.2 | +29.0 | +34.8 | -7.3 | -6.8 | 1/4 | 2/4 | yes |
| M0081 | dividend-date methods | M0081-X-W12 | +4.0 | +5.0 | +7.2 | +30.9 | +32.3 | -11.7 | -11.6 | 1/4 | 2/4 | yes |
| M0081 | dividend-date methods | M0081-X-W6 | +3.2 | +4.5 | +7.2 | +32.8 | +36.1 | -13.3 | -12.9 | 1/4 | 2/4 | yes |
| M0082 | dividend-date methods | M0082-D-EARLY-N20 | +8.0 | +7.9 | +7.2 | +24.2 | +24.5 | -6.1 | -6.2 | 1/4 | 1/4 | yes |
| M0082 | dividend-date methods | M0082-D-N20 | +7.7 | +7.3 | +7.2 | +29.7 | +29.5 | -6.2 | -7.4 | 1/4 | 1/4 | yes |
| M0082 | dividend-date methods | M0082-D-N40 | +8.9 | +8.6 | +7.2 | +23.1 | +22.1 | -5.5 | -6.0 | 1/4 | 1/4 | yes |
| M0082 | dividend-date methods | M0082-X-N20 | +8.1 | +7.1 | +7.2 | +35.6 | +35.5 | -7.4 | -8.3 | 1/4 | 1/4 | yes |
| M0082 | dividend-date methods | M0082-X-N40 | +9.1 | +8.0 | +7.2 | +27.0 | +28.9 | -4.9 | -6.3 | 1/4 | 1/4 | yes |
| M0083 | dividend-date methods | M0083-A-DN | +8.8 | +8.3 | +7.2 | +21.0 | +24.2 | -6.5 | -6.4 | 2/4 | 2/4 | yes |
| M0083 | dividend-date methods | M0083-A-UP | +9.8 | +10.3 | +7.2 | +19.9 | +22.2 | -3.7 | -4.9 | 2/4 | 2/4 | yes |
| M0083 | dividend-date methods | M0083-A-UP-D | +9.8 | +9.6 | +7.2 | +21.3 | +20.8 | -3.7 | -4.1 | 2/4 | 2/4 | yes |
| M0083 | dividend-date methods | M0083-X-DN | +8.8 | +8.0 | +7.2 | +25.5 | +28.1 | -5.3 | -6.1 | 2/4 | 2/4 | yes |
| M0083 | dividend-date methods | M0083-X-UP | +10.6 | +10.9 | +7.2 | +21.1 | +23.0 | -3.8 | -4.6 | 2/4 | 2/4 | yes |
| M0083 | dividend-date methods | M0083-X-UP-D | +10.8 | +10.7 | +7.2 | +19.9 | +20.1 | -3.4 | -3.3 | 2/4 | 2/4 | yes |
| M0085 | dividend-date methods | M0085-DECL-M | +10.4 | +9.7 | +7.2 | +21.3 | +25.1 | -3.9 | -4.3 | 2/4 | 2/4 | yes |
| M0085 | dividend-date methods | M0085-DECL-W | +9.9 | +9.1 | +7.2 | +26.0 | +27.7 | -3.8 | -5.7 | 2/4 | 2/4 | yes |
| M0085 | dividend-date methods | M0085-EX-M | +11.1 | +10.1 | +7.2 | +22.0 | +23.2 | -2.7 | -4.0 | 2/4 | 2/4 | yes |
| M0085 | dividend-date methods | M0085-EX-W | +10.1 | +8.5 | +7.2 | +25.5 | +26.1 | -3.6 | -5.8 | 2/4 | 2/4 | yes |
| M0085 | dividend-date methods | M0085-HOST-M | +10.9 | +10.4 | +7.2 | +21.9 | +22.4 | -3.0 | -3.4 | 2/4 | 2/4 | yes |
| M0085 | dividend-date methods | M0085-HOST-W | +10.3 | +9.1 | +7.2 | +25.7 | +25.7 | -3.2 | -4.9 | 2/4 | 2/4 | yes |
| M0086 | dividend-date methods | M0086-HOST | +13.8 | +15.2 | +7.2 | +23.3 | +28.7 | -1.9 | +0.1 | 3/4 | 3/4 | yes |
| M0086 | dividend-date methods | M0086-TILT-ANN | +13.1 | +14.6 | +7.2 | +23.6 | +28.6 | -1.9 | -1.1 | 3/4 | 3/4 | yes |
| M0086 | dividend-date methods | M0086-TILT-ANN-D | +13.4 | +14.6 | +7.2 | +23.6 | +28.6 | -1.5 | -1.1 | 3/4 | 3/4 | yes |
| M0086 | dividend-date methods | M0086-TILT-EX | +13.8 | +13.3 | +7.2 | +23.2 | +28.5 | -1.5 | -2.3 | 3/4 | 3/4 | yes |
| M0086 | dividend-date methods | M0086-TILT-EX-D | +13.8 | +14.0 | +7.2 | +23.2 | +28.5 | -1.4 | -1.3 | 3/4 | 3/4 | yes |

## The gate

The check history stays a **cross-check, not a gate** (Decision D1 of
`EODHD_SURVIVORSHIP_MARKET_PLAN.md`). `lab run`, `lab test` and `lab remeasure` refuse it, and the
hard gate in `lab/hardgate.py` never reads it. Making it part of promotion would be a separate,
argued change to the gate, made after reading these numbers. It is not part of this measurement.

## What remains uncertain

- 111 index members still have no usable price history. The largest by member-days are STI,
  HWM, BEAM, HSH, JAVA, UST, WB and ABI: mostly tickers that a different company now uses, whose
  original company EODHD lists under no code we could match, plus 39 symbols the dev store serves
  only for a later company.
- 1996-1997 is still thin, so any edge that lives in those two years is not checked by this.
- Every variant's dev re-run reproduced its recorded result; none is excluded.
