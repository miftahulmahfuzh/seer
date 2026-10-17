"""Point-in-time shares outstanding before XBRL: SEC EDGAR cover pages, 1996-2010.

Why this exists. Company size (market value = shares outstanding x the *unadjusted* close) is
what a market-shaped, size-weighted book ranks on, and the lab could not compute it before
2009: XBRL's ``dei:EntityCommonStockSharesOutstanding`` starts with the large accelerated
filers' fiscal 2009 reports, and EODHD's fundamentals endpoint is not on the owner's plan
(it answers 403). Every 10-K and 10-Q filed since EDGAR began carries the number on its cover
page instead -- "As of March 2, 1997, 1,640,183,273 shares of common stock were outstanding" --
so it is rebuilt here from the free filings, the way ``sectors`` rebuilt industry labels.

* ``edgar_index`` -- EDGAR's quarterly ``master.idx`` as filing references, and which filings
  are wanted for which filer over which window (pure).
* ``fetch`` -- the downloader: index files and the head of each filing's primary document into
  a gitignored on-disk cache, rate limited under SEC's ceiling, resumable (network edge).
* ``cover`` -- the cover-page parser: ``(as_of, shares, class)`` out of free text (pure).
* ``history`` -- the vendored result (``engine/data/shares_outstanding_pre2009.csv``), the
  point-in-time lookup, the join to 2009+ XBRL facts and the market-value helper (pure).
* ``checks`` -- the validation that makes the numbers usable: XBRL overlap, split
  consistency, implied market value bounds (pure).
* ``splits`` -- the vendor split lists behind the research stores' adjusted closes, cached from
  yfinance (network edge).
* ``store`` -- the research store's ``shares.csv`` (resolved point-in-time change points) and
  ``splits.csv``, writers and strict readers; the lab reads them as ``Market.shares_on`` and
  ``Market.market_value`` (pure).
* ``integrate`` -- ``shares fetch-splits`` / ``store`` / ``store-report``: put the two files into a
  store without moving its price fingerprint, and report what the size accessor gives.
"""
