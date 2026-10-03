-- Seer schema v1. Shared by web/ (reads) and engine/ (writes).

CREATE TABLE IF NOT EXISTS strategies (
  id            text PRIMARY KEY,               -- 'A', 'B', 'C', 'SPY'
  name          text NOT NULL,                  -- 'A · Quant'
  sub           text NOT NULL,                  -- 'Mean Reversion'
  icon          text NOT NULL,                  -- lucide icon name
  is_champion   boolean NOT NULL DEFAULT false,
  is_benchmark  boolean NOT NULL DEFAULT false,
  params        jsonb NOT NULL DEFAULT '{}',
  sort          int NOT NULL DEFAULT 0
);

-- One row per nightly pipeline run.
CREATE TABLE IF NOT EXISTS runs (
  id            bigserial PRIMARY KEY,
  started_at    timestamptz NOT NULL DEFAULT now(),
  finished_at   timestamptz,
  status        text NOT NULL CHECK (status IN ('running', 'success', 'failed')),
  data_date     date,          -- last US session whose prices were used
  session_date  date,          -- US session the new picks are for
  is_demo       boolean NOT NULL DEFAULT false,
  error         text
);

-- One row per pick, through its whole lifecycle:
-- pending (bracket placed) -> open (limit filled) -> closed (tp/sl/time/gap)
-- pending -> expired (limit never filled)
CREATE TABLE IF NOT EXISTS orders (
  id            bigserial PRIMARY KEY,
  strategy_id   text NOT NULL REFERENCES strategies(id),
  session_date  date NOT NULL,
  slot          int NOT NULL CHECK (slot BETWEEN 1 AND 4),
  symbol        text NOT NULL,
  company       text NOT NULL,
  last_price    numeric(12,4) NOT NULL,
  limit_price   numeric(12,4) NOT NULL,
  tp_price      numeric(12,4) NOT NULL,
  sl_price      numeric(12,4) NOT NULL,
  shares        int NOT NULL CHECK (shares > 0),
  explanation   text,
  status        text NOT NULL CHECK (status IN ('pending', 'open', 'closed', 'expired')),
  fill_date     date,
  fill_price    numeric(12,4),
  days_held     int NOT NULL DEFAULT 0,
  exit_date     date,
  exit_price    numeric(12,4),
  exit_reason   text CHECK (exit_reason IN ('tp', 'sl', 'time', 'gap')),
  pnl_usd       numeric(12,4),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (strategy_id, session_date, symbol)
);
CREATE INDEX IF NOT EXISTS orders_status_idx ON orders (strategy_id, status);

-- Split-adjusted daily bars.
CREATE TABLE IF NOT EXISTS bars (
  symbol  text NOT NULL,
  date    date NOT NULL,
  open    numeric(12,4) NOT NULL,
  high    numeric(12,4) NOT NULL,
  low     numeric(12,4) NOT NULL,
  close   numeric(12,4) NOT NULL,
  volume  bigint NOT NULL,
  PRIMARY KEY (symbol, date)
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
  strategy_id  text NOT NULL REFERENCES strategies(id),
  date         date NOT NULL,
  cash_usd     numeric(14,4) NOT NULL,
  equity_usd   numeric(14,4) NOT NULL,
  PRIMARY KEY (strategy_id, date)
);

CREATE TABLE IF NOT EXISTS fx_rates (
  date     date PRIMARY KEY,
  usd_idr  numeric(12,4) NOT NULL
);

-- "Mark as done" on day-5 action items, shared across devices.
CREATE TABLE IF NOT EXISTS action_dismissals (
  order_id      bigint PRIMARY KEY REFERENCES orders(id) ON DELETE CASCADE,
  dismissed_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  name        text PRIMARY KEY,
  applied_at  timestamptz NOT NULL DEFAULT now()
);
