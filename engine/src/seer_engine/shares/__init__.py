"""Point-in-time shares outstanding from SEC EDGAR: cover pages 1996-2010, XBRL per class 2009+.

Why this exists. Company size (market value = shares outstanding x the *unadjusted* close) is
what a market-shaped, size-weighted book ranks on, and the lab could not compute it before
2009: XBRL's ``dei:EntityCommonStockSharesOutstanding`` starts with the large accelerated
filers' fiscal 2009 reports, and EODHD's fundamentals endpoint is not on the owner's plan
(it answers 403). Every 10-K and 10-Q filed since EDGAR began carries the number on its cover
page instead -- "As of March 2, 1997, 1,640,183,273 shares of common stock were outstanding" --
so it is rebuilt here from the free filings, the way ``sectors`` rebuilt industry labels.

Why 2009+ is read from the filings too. SEC's ``companyfacts`` API, which fills a store's
``fundamentals.csv``, drops every dimensional fact, and a company with more than one share class
tags its cover count once per class on the class axis with no total. Meta, Visa, Mastercard,
Comcast, UPS, Ford and Alphabet from 2014 therefore had no 2009+ size at all, and Berkshire
counted its class A only, so every market-shaped book started 2009-2015 behind SPY before it
picked anything. Each filing's own XBRL instance carries the per-class facts; they are read
point in time from the filing date, summed or attributed per listed class by a small class
table, and vendored like the cover-page csv.

* ``edgar_index`` -- EDGAR's quarterly ``master.idx`` as filing references, and which filings
  are wanted for which filer over which window (pure).
* ``fetch`` -- the downloader: index files, the head of each filing's primary document and the
  dei share facts of each XBRL instance into a gitignored on-disk cache, rate limited under
  SEC's ceiling, resumable (network edge).
* ``cover`` -- the cover-page parser: ``(as_of, shares, class)`` out of free text (pure).
* ``instance`` -- the dei share facts and their class-axis contexts out of an XBRL instance:
  one reading per filing, the tagged total if any and the count per class (pure).
* ``classes`` -- which filings need an instance read, ``shares download-classes`` /
  ``build-classes`` and the vendored ``engine/data/shares_xbrl_classes.csv`` (network edge for
  the download, pure for the build and the reader).
* ``class_table`` -- the hand-kept ``engine/data/share_classes.csv``: which listed symbol each
  class of a multi-class filer trades as, at what ratio, keyed on the count's date; classes
  matched by their words, so cover text and XBRL member names share one row (pure).
* ``history`` -- the vendored results (``shares_outstanding_pre2009.csv``,
  ``shares_xbrl_classes.csv``) read through the class table, the point-in-time lookup, the join
  to 2009+ XBRL facts, the per-class attribution and the market-value helper (pure).
* ``checks`` -- the validation that makes the cover numbers usable: XBRL overlap, split
  consistency, implied market value bounds (pure).
* ``splits`` -- the vendor split lists behind the research stores' adjusted closes, cached from
  yfinance (network edge).
* ``store`` -- the research store's ``shares.csv`` (resolved point-in-time change points; source
  ``edgar-cover``, ``xbrl`` or ``xbrl-class``) and ``splits.csv``, writers and strict readers;
  the lab reads them as ``Market.shares_on`` and ``Market.market_value`` (pure).
* ``integrate`` -- ``shares fetch-splits`` / ``store`` / ``store-report``: put the two files into a
  store without moving its price fingerprint, and report what the size accessor gives.
"""
