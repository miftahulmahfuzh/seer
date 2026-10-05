-- Seer schema v5: SEC EDGAR point-in-time fundamentals (plan edgar-fundamentals, phase 2).
-- Written by engine/ (Python) over DATABASE_URL_UNPOOLED; web/ does not read these.
-- Additive only: three new tables and one index. Nothing existing is altered or dropped.

-- The dated ticker -> CIK bridge, vendored as engine/data/ticker_cik.csv and loaded by
-- `python -m seer_engine fundamentals` (seer_engine.cik). A BARE TICKER NEVER IDENTIFIES A
-- COMPANY: CA, MON, PLL, ALTR, LLL and DTV were all reissued to unrelated filers after their
-- S&P/NDX membership ended, so every resolution is scoped by date.
-- Symbol resolves to cik on date D when start_date <= D AND (end_date IS NULL OR end_date > D),
-- exactly the half-open convention `universe` uses.
-- Non-overlap of a symbol's intervals is enforced by the loader, not by the database, for the
-- same reason `universe` does it there: an EXCLUDE constraint would need the btree_gist
-- extension, and 002_engine.sql declined to add one.
CREATE TABLE IF NOT EXISTS ticker_cik (
  symbol      text NOT NULL,                 -- canonical dot form, same string as bars.symbol ('BRK.B')
  cik         bigint NOT NULL CHECK (cik > 0 AND cik <= 9999999999),
                                             -- SEC's ten-digit filer id, stored unpadded; the
                                             -- 'CIK0000320193' URL form is built by the client
  start_date  date NOT NULL,                 -- first day this ticker meant this filer (inclusive)
  end_date    date,                          -- first day it no longer did (EXCLUSIVE); NULL = still current
  company     text NOT NULL,                 -- the filer's name as vendored, for human audit of recycled tickers
  source      text NOT NULL CHECK (source IN ('current', 'edgar', 'exact', 'fuzzy', 'manual')),
                                             -- phase 1's resolution tier; see engine/data/SOURCES.md
                                             -- ('current' = SEC company_tickers.json, 'edgar' = a
                                             --  submissions probe, 'exact'/'fuzzy' = cik-lookup-data.txt,
                                             --  'manual' = hand-audited)
  note        text,                          -- free text, like ticker_aliases.csv's note column
  PRIMARY KEY (symbol, start_date),
  CHECK (end_date IS NULL OR end_date > start_date)
);
CREATE INDEX IF NOT EXISTS ticker_cik_cik_idx ON ticker_cik (cik);

-- Raw SEC XBRL facts, as reported. One row per (filer, taxonomy, tag, unit, period, filing),
-- straight from companyfacts/CIK##########.json -> facts.<taxonomy>.<tag>.units.<unit>[].
--
-- accn IS PART OF THE PRIMARY KEY. A company restates: the same concept for the same period
-- appears again in a later filing with a different value and a different accession number.
-- Keying without accn would overwrite the original and make as-reported unrecoverable.
--
-- filed IS THE ONLY NO-LOOK-AHEAD BOUNDARY. period_end is not: a figure for the period ending
-- 2015-12-31 is typically filed in February 2016. Every read path must take the latest fact
-- with filed <= t. There is deliberately no CHECK (filed >= period_end): dei cover-page facts
-- and SEC data quirks violate it, and a tripped CHECK would abort a whole ingest batch.
--
-- period_start = period_end MEANS INSTANTANEOUS. SEC omits `start` for point-in-time concepts
-- (Assets, StockholdersEquity, dei:EntityCommonStockSharesOutstanding); the loader writes
-- period_end into both columns. No us-gaap or dei duration fact has a one-day period, so the
-- convention is unambiguous. period_start must stay in the key: one 10-K reports Revenues for
-- both the fiscal year and its fourth quarter under the same accn, tag, unit and period_end.
--
-- val is unconstrained numeric on purpose: Assets exceeds 1e12 (numeric(12,4) tops out at
-- 99,999,999.9999), NetIncomeLoss and StockholdersEquity go negative, and EPS in USD/shares
-- carries decimals. Exactness matters because a restatement is read as a diff.
--
-- Derived metrics are NOT materialised here. The concept ladder, point-in-time selection and
-- SUE live in pure Python (seer_engine.fundamentals), the way indicators derive from raw bars.
--
-- No index beyond the primary key. Its leading columns (cik, taxonomy, tag) are exactly the
-- dominant read prefix, so "every fact for this CIK and this tag with filed <= t" is one range
-- scan over the 10-140 rows a filer has for a concept; the backtest's panel load is a full-table
-- COPY, which wants no index. Row budget: ~795 filers x ~11 ladder tags x ~100 facts ~= 0.9 M
-- rows, ~130 MB heap + ~80 MB primary key, against a 0.5 GB Neon free tier already holding
-- 177 MB of bars. THAT BUDGET ASSUMES ONLY THE LADDER'S TAGS ARE INGESTED: one 10-K carries
-- 500-2,000 distinct tags, which would be a 50-100x table.
CREATE TABLE IF NOT EXISTS fundamental_facts (
  cik           bigint NOT NULL CHECK (cik > 0 AND cik <= 9999999999),
  taxonomy      text NOT NULL CHECK (taxonomy IN ('us-gaap', 'dei')),
  tag           text NOT NULL,                -- XBRL concept ('Assets', 'NetIncomeLoss', 'EntityCommonStockSharesOutstanding')
  unit          text NOT NULL,                -- 'USD', 'USD/shares', 'shares'; open domain, no CHECK
  period_start  date NOT NULL,                -- SEC's `start`; = period_end when SEC omits it (instantaneous)
  period_end    date NOT NULL,                -- SEC's `end`
  accn          text NOT NULL,                -- accession number ('0001193125-15-356351'); the restatement axis
  val           numeric NOT NULL,             -- as reported; negative and > 1e12 both occur
  fy            int,                          -- filer's fiscal year label; absent on some facts
  fp            text,                         -- 'FY', 'Q1'..'Q4'; filer-declared, open domain, no CHECK
  form          text NOT NULL,                -- '10-K', '10-Q', '10-K/A', '8-K', '20-F'; open domain, no CHECK
  filed         date NOT NULL,                -- the availability date; the no-look-ahead boundary
  PRIMARY KEY (cik, taxonomy, tag, unit, period_start, period_end, accn),
  CHECK (period_start <= period_end)
);

-- One row per CIK the fundamentals ingest attempted; lets the ingest resume and records which
-- filers could not be fetched. backfill_log's shape (status CHECK, first/last markers, a row
-- count, an error, updated_at), with first_date/last_date read on the `filed` axis.
--
-- KEYED BY cik, NOT BY symbol, and that is the one deliberate difference from backfill_log.
-- The unit of work is one companyfacts/CIK##########.json fetch, which is one CIK. Keying by
-- symbol would break both ways: one CIK backs several tickers (GOOG/GOOGL, LMCA/LMCK, CMCSK),
-- so the same JSON would be fetched and the same facts written once per ticker and `rows` would
-- double-count; and one ticker maps to several CIKs over time (CA, MON, PLL, ALTR, LLL, DTV),
-- so a single row would have to stand for two unrelated companies' outcomes at once. A symbol's
-- ingest status is read by joining ticker_cik.
CREATE TABLE IF NOT EXISTS fundamentals_log (
  cik          bigint PRIMARY KEY CHECK (cik > 0 AND cik <= 9999999999),
  status       text NOT NULL CHECK (status IN ('ok', 'empty', 'failed')),
  first_filed  date,                          -- earliest `filed` among the facts written
  last_filed   date,                          -- latest `filed` among the facts written
  rows         int,                           -- facts written for this CIK
  error        text,
  updated_at   timestamptz NOT NULL DEFAULT now()
);
