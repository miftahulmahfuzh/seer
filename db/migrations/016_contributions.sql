-- Seer schema v16: the owner's monthly contribution reaches paper (plan gotrade-fee-rebuild,
-- R3, phase 6; the owner's decision, relayed 2026-10-08).
--
-- WHAT WAS MISSING. Until this file paper had exactly one record of capital,
-- paper_state.initial_cash_usd, and exactly one writer for it (paper/store.py init_paper_state's
-- INSERT). The only later UPDATE writes cash_usd, equity_usd and last_session. There was no
-- column, and no table, in which money arriving after day 0 could be written down. The owner
-- adds 5,000,000 IDR to a 10,000,000 IDR start on the 25th of every month, so every paper book
-- -- the four quant books, C and SPY alike -- was modelling a strategy the owner is not running.
-- The gap is BELOW every engine, so it is closed once, here, and not per method.
--
-- WHY A TABLE AND NOT A COLUMN. A running total (initial_cash_usd += deposit) would let paper
-- hold the money but would destroy the thing the measurement needs. A deposit raises ending
-- equity WITHOUT being a return, so every return measure has to be able to tell "the book grew"
-- from "the owner added money". That needs the DATED cashflows, one row per deposit, which is
-- what a money-weighted return integrates over. A total cannot be un-summed.
--
-- WHY ALL THREE OF IDR, THE RATE AND USD. The owner thinks and deposits in IDR; the book trades
-- in USD; and the rate moves between deposits, which is real -- the same 5,000,000 IDR buys
-- fewer dollars when the rupiah is weaker.
--   amount_idr   what he actually sends. The schedule is an IDR fact; a USD-only row would
--                silently re-fix the deposit at one rate and be unreproducible.
--   usd_idr      the fx_rates rate on session_date: the latest rate dated on or before it, which
--                is exactly what paper already converts the day-0 start at
--                (commands/paper.py's view.usd_idr_on, backtest.market.usd_idr_on).
--   amount_usd   the dollars credited, computed as sim.model.initial_cash_usd(amount_idr,
--                usd_idr) -- the SAME conversion day 0 uses, so a deposit and a start never
--                round differently.
-- All three are frozen the night the row is written, because fx_rates is backfilled and a
-- stepped book's history must not move when an old rate is corrected. paper_state.usd_idr
-- ("the rate initial cash was converted at", 003_paper.sql) is this same convention.
--
-- WHY TWO DATES. due_date is the owner's calendar date, the 25th. session_date is the first NYSE
-- session on or after it; the exchange calendar produces the lag and no lag is baked in.
-- Measured 2026-10-08 over the twelve months from 2026-10-25: five of the twelve 25ths are not
-- sessions, and after landing the money sits as idle cash for 2 to 5 sessions before the next
-- month's first session deploys it (mean 7.0 calendar days from the 25th to that session, range
-- 4 to 10). Reproducing that idle cash is the point; depositing at the rotation would overstate
-- returns.
--
-- ONE ROW PER (STRATEGY, DUE DATE). Every roster entry runs its own 10,000,000 IDR paper book
-- (paper/capital.py PAPER_INITIAL_IDR), so each receives its own copy of the same schedule.
--
-- applied_at is NULL until the paper night that steps session_date credits the money to that
-- strategy's state. Crediting a session already stepped is refused in the store, not here
-- (docs/runbooks/paper-trading.md:60-68: settled history is never rewritten).
--
-- ADDITIVE AND INERT. One new table and one index; nothing existing is altered and no
-- paper_state row is read or rewritten. PAPER_PAUSED is 'true' and zero sessions have been
-- stepped, and .github/workflows/nightly.yml:48 confirms Migrate still runs while paused -- so
-- this lands empty and stays empty until the owner resumes. Nothing outside paper reads it yet.
CREATE TABLE IF NOT EXISTS paper_contributions (
  strategy_id   text NOT NULL REFERENCES strategies(id),
  due_date      date NOT NULL,                         -- the owner's calendar date (the 25th)
  session_date  date NOT NULL,                         -- first NYSE session on or after due_date
  amount_idr    numeric(18,2) NOT NULL CHECK (amount_idr > 0),
  usd_idr       numeric(12,4) NOT NULL CHECK (usd_idr > 0),   -- the rate on session_date
  amount_usd    numeric(14,4) NOT NULL CHECK (amount_usd > 0),-- frozen when the row is written
  applied_at    timestamptz,                           -- NULL until session_date's night credits it
  recorded_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (strategy_id, due_date),
  CHECK (session_date >= due_date)
);
CREATE INDEX IF NOT EXISTS paper_contributions_session
  ON paper_contributions (strategy_id, session_date);
