-- Seer schema v3: nightly paper trading (plan paper-trading-ship, contract C1; handover D2, D4, D6, D8).
-- Additive only: nullable or defaulted columns, new tables and one index, plus two data
-- statements (the roster's display rows, and dropping the unreferenced B/C rows).
-- Written by engine/ (Python); web/ reads the strategies columns and the paper/book tables.

ALTER TABLE strategies ADD COLUMN IF NOT EXISTS engine text CHECK (engine IN ('bracket', 'book', 'benchmark'));
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS rules_id text;         -- 'design-v0', 'monthly-hold', NULL for SPY
ALTER TABLE strategies ADD COLUMN IF NOT EXISTS paper_start date;      -- first paper session; NULL until `paper` starts it

ALTER TABLE orders ADD COLUMN IF NOT EXISTS mark numeric(12,4);        -- open order's last close, in the order's own (pre-split) units

ALTER TABLE runs ADD COLUMN IF NOT EXISTS paper_status text CHECK (paper_status IN ('running', 'success', 'failed'));
ALTER TABLE runs ADD COLUMN IF NOT EXISTS paper_error text;
ALTER TABLE runs ADD COLUMN IF NOT EXISTS paper_finished_at timestamptz;

-- One row per paper strategy (every engine): the state between nights.
CREATE TABLE IF NOT EXISTS paper_state (
  strategy_id       text PRIMARY KEY REFERENCES strategies(id),
  last_session      date NOT NULL,            -- last session stepped; prev_session(paper_start) right after init
  cash_usd          numeric(14,4) NOT NULL,
  equity_usd        numeric(14,4) NOT NULL,   -- equity at last_session's snapshot
  initial_cash_usd  numeric(14,4) NOT NULL,
  usd_idr           numeric(12,4) NOT NULL,   -- the rate initial cash was converted at
  pending_session   date,                     -- session the stored decision is for (next_session(last_session))
  pending_decision  boolean NOT NULL DEFAULT false, -- book: pending_session is a decision session (book_targets may be empty)
  updated_at        timestamptz NOT NULL DEFAULT now()
);

-- Open book positions (book strategies and the SPY benchmark holding). sim.book.Position fields.
CREATE TABLE IF NOT EXISTS book_positions (
  strategy_id   text NOT NULL REFERENCES strategies(id),
  symbol        text NOT NULL,
  shares        numeric(16,4) NOT NULL CHECK (shares > 0),
  mark          numeric(12,4) NOT NULL,
  entry_date    date NOT NULL,
  entry_price   numeric(12,4) NOT NULL,
  days_held     int NOT NULL CHECK (days_held >= 1),
  cost_usd      numeric(14,4) NOT NULL,
  income_usd    numeric(14,4) NOT NULL,
  stop_price    numeric(12,4),
  take_price    numeric(12,4),
  exit_pending  boolean NOT NULL DEFAULT false,
  PRIMARY KEY (strategy_id, symbol)
);

-- A book strategy's decision for one session, ranked (kept after execution as the decision record).
CREATE TABLE IF NOT EXISTS book_targets (
  strategy_id   text NOT NULL REFERENCES strategies(id),
  session_date  date NOT NULL,
  rank          int NOT NULL CHECK (rank >= 1),
  symbol        text NOT NULL,
  weight        numeric(8,6) NOT NULL CHECK (weight > 0 AND weight <= 1),
  last_price    numeric(12,4) NOT NULL,
  limit_price   numeric(12,4),
  stop_price    numeric(12,4),
  take_price    numeric(12,4),
  explanation   text,
  PRIMARY KEY (strategy_id, session_date, symbol),
  UNIQUE (strategy_id, session_date, rank)
);

CREATE TABLE IF NOT EXISTS book_fills (
  id            bigserial PRIMARY KEY,
  strategy_id   text NOT NULL REFERENCES strategies(id),
  session_date  date NOT NULL,
  seq           int NOT NULL,                 -- order within the session, from 1 (sim order: splits, open, trim, buy, intraday, forced)
  symbol        text NOT NULL,
  side          text NOT NULL CHECK (side IN ('buy', 'sell')),
  shares        numeric(16,4) NOT NULL CHECK (shares > 0),
  price         numeric(12,4) NOT NULL,
  cash_usd      numeric(14,4) NOT NULL,
  cost_usd      numeric(14,4) NOT NULL,
  reason        text NOT NULL CHECK (reason IN ('entry', 'add', 'trim', 'signal', 'time', 'gap', 'tp', 'sl', 'forced')),
  UNIQUE (strategy_id, session_date, seq)
);

CREATE TABLE IF NOT EXISTS book_trades (
  id            bigserial PRIMARY KEY,
  strategy_id   text NOT NULL REFERENCES strategies(id),
  symbol        text NOT NULL,
  entry_date    date NOT NULL,
  exit_date     date NOT NULL,
  entry_price   numeric(12,4) NOT NULL,
  exit_price    numeric(12,4) NOT NULL,
  days_held     int NOT NULL,
  cost_usd      numeric(14,4) NOT NULL,
  income_usd    numeric(14,4) NOT NULL,
  pnl_usd       numeric(14,4) NOT NULL,
  exit_reason   text NOT NULL CHECK (exit_reason IN ('signal', 'time', 'gap', 'tp', 'sl', 'forced')),
  idle          boolean NOT NULL DEFAULT false,
  UNIQUE (strategy_id, symbol, entry_date)
);
CREATE INDEX IF NOT EXISTS book_trades_exit_idx ON book_trades (strategy_id, exit_date);

-- Cash dividends by ex-date (Massive types CD + SC, summed per symbol and ex-date).
-- Same units as bars: splits.apply_splits rewrites earlier rows with the bars.
CREATE TABLE IF NOT EXISTS dividends (
  symbol       text NOT NULL,
  ex_date      date NOT NULL,
  amount       numeric(14,6) NOT NULL CHECK (amount > 0),
  recorded_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, ex_date)
);

-- Roster display rows (the frozen spec and paper_start are written by `paper`, phase 7).
-- SPY is the champion; nothing else is (D2).
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id) VALUES
  ('SPY', 'SPY', 'S&P 500, buy and hold', 'landmark', true, true, 1, 'benchmark', NULL),
  ('A', 'A · Quant', 'Mean reversion, 5-day brackets', 'sigma', false, false, 2, 'bracket', 'design-v0'),
  ('F4-MOM12-N20-TREND', 'F4 · Momentum', 'Top 20 by 12-1 momentum, monthly', 'trending-up', false, false, 3, 'book', 'monthly-hold'),
  ('F1-SPY-SMA200-M', 'F1 · Trend', 'SPY above its 200-day average, monthly', 'shield', false, false, 4, 'book', 'monthly-hold')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, sub = EXCLUDED.sub, icon = EXCLUDED.icon,
  is_champion = EXCLUDED.is_champion, is_benchmark = EXCLUDED.is_benchmark, sort = EXCLUDED.sort,
  engine = EXCLUDED.engine, rules_id = EXCLUDED.rules_id;
-- B and C are not on the roster; drop their rows only when nothing references them.
DELETE FROM strategies s WHERE s.id IN ('B', 'C')
  AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.strategy_id = s.id)
  AND NOT EXISTS (SELECT 1 FROM equity_snapshots e WHERE e.strategy_id = s.id);
