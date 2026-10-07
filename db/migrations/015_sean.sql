-- Seer schema v15: Sean, the owner's real Gotrade trades (owner, 2026-10-07).
--
-- Everything Seer stored before this was simulated: paper fills priced at an assumed 0.1% cost.
-- The owner trades for real on Gotrade, following RAW, and every order leaves an "Order Summary"
-- receipt. Sean reads those screenshots (glm-4.6v, web/lib/sean/readOrder.ts), keeps one row per
-- order here, marks the holdings to market every night (engine, `seer_engine sean marks`) and
-- shows the profit and loss; it can also follow one roster method and remind the owner what to
-- buy or sell.
--
-- sean_orders     one row per receipt. The screenshot itself is never stored: image_sha256 only
--                 dedupes a re-upload of the same file, and UNIQUE (symbol, side, executed_at,
--                 shares) dedupes the same order from two different screenshots. Fee columns hold
--                 magnitudes; the receipt's +/- sign only restates the side. executed_at is the
--                 receipt's Date + Time read as WIB. raw keeps the model's JSON for audit.
-- sean_link       the one roster method Sean follows, if any (singleton row, id = 1).
-- sean_reminder_marks  reminders the owner ticked off by hand.
-- sean_marks      daily closes for every symbol the owner has held (engine-written).
-- sean_equity     the owner's daily P&L series (engine-written, replaced whole on each run).
--
-- The ledger math behind sean_equity lives in two places that must agree:
-- web/lib/sean/ledger.ts and engine/src/seer_engine/sean/ledger.py, both tested against
-- web/lib/sean/fixtures/ledger.json. Additive only: nothing outside Sean reads these tables.
CREATE TABLE IF NOT EXISTS sean_orders (
  id                  bigserial PRIMARY KEY,
  image_sha256        text UNIQUE,                    -- hex SHA-256 of the uploaded bytes; NULL never written by the app today
  side                text NOT NULL CHECK (side IN ('buy', 'sell')),
  order_type          text NOT NULL,                  -- as printed: 'Market Buy', 'Limit Sell', ...
  status              text NOT NULL,                  -- as printed: 'Filled'
  symbol              text NOT NULL,
  executed_at         timestamptz NOT NULL,           -- receipt Date + Time, read as WIB (+07:00)
  price               numeric(18,6) NOT NULL,         -- 'Average price' or 'Execution price'
  shares              numeric(24,9) NOT NULL,
  amount_usd          numeric(14,2) NOT NULL,         -- 'Trade amount'
  trading_fee_usd     numeric(10,2) NOT NULL CHECK (trading_fee_usd >= 0),     -- magnitudes; the receipt's +/- sign is the side
  regulatory_fee_usd  numeric(10,2) NOT NULL CHECK (regulatory_fee_usd >= 0),
  ppn_usd             numeric(10,2) NOT NULL CHECK (ppn_usd >= 0),
  total_usd           numeric(14,2) NOT NULL,         -- buy: amount + fees; sell: amount - fees
  net_profit_usd      numeric(14,2),                  -- the sell receipt's 'Net Profit', NULL on buys
  fills               jsonb NOT NULL DEFAULT '[]',    -- [{shares, price}] partial-fill lines, [] when none printed
  raw                 jsonb,                          -- the model's JSON, kept for audit
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (symbol, side, executed_at, shares)          -- same order from two different screenshots
);
CREATE INDEX IF NOT EXISTS sean_orders_executed_at ON sean_orders (executed_at);

-- One followed roster method at most (singleton row).
CREATE TABLE IF NOT EXISTS sean_link (
  id           smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  strategy_id  text NOT NULL REFERENCES strategies(id),
  since        date NOT NULL,                         -- orders whose New York trade date is on/after this belong to the plan
  budget_usd   numeric(14,2),                         -- owner's intended plan size; NULL = the plan's current value
  linked_at    timestamptz NOT NULL DEFAULT now()
);

-- A reminder the owner marked done by hand (uploaded orders clear reminders on their own).
CREATE TABLE IF NOT EXISTS sean_reminder_marks (
  strategy_id   text NOT NULL,
  session_date  date NOT NULL,                        -- the method's decision session
  symbol        text NOT NULL,
  action        text NOT NULL CHECK (action IN ('buy', 'sell')),
  marked_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (strategy_id, session_date, symbol, action)
);

-- Daily closes for every symbol the owner has held (written by the engine, Phase 4).
CREATE TABLE IF NOT EXISTS sean_marks (
  symbol  text NOT NULL,
  date    date NOT NULL,
  close   numeric(18,4) NOT NULL,
  PRIMARY KEY (symbol, date)
);

-- The owner's daily P&L series (written by the engine, Phase 4; read by the Overview, Phase 3).
CREATE TABLE IF NOT EXISTS sean_equity (
  date            date PRIMARY KEY,                   -- NYSE session
  value_usd       numeric(14,2) NOT NULL,             -- holdings marked at that session's close
  cost_usd        numeric(14,2) NOT NULL,             -- open cost basis (fees included)
  realized_usd    numeric(14,2) NOT NULL,             -- cumulative
  unrealized_usd  numeric(14,2) NOT NULL,             -- value - cost
  pnl_usd         numeric(14,2) NOT NULL,             -- realized + unrealized
  fees_usd        numeric(14,2) NOT NULL,             -- cumulative trading + regulatory + PPN
  computed_at     timestamptz NOT NULL DEFAULT now()
);
