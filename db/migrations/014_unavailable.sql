-- Seer schema v14: stocks the owner's broker (Gotrade) does not offer (owner, 2026-10-07).
--
-- The first paper night picked SNDK, RVTY and TPL, and none of the three can be bought on
-- Gotrade. A pick the owner cannot buy is a pick paper must not take either, or the paper
-- record stops being the record of what the owner could have done. So every paper method skips a
-- listed stock and takes its next-best pick instead.
--
-- HOW THE ENGINE READS IT. A row takes the symbol out of the index membership from `since` up to
-- `until` (exclusive; NULL = still not offered), exactly as if it had left the index on `since`
-- (paper/unavailable.py, applied in paper/store.load_market_window). That one place feeds the
-- paper night, its replay check and Strategy C's news check alike, so all three agree. The lab
-- and the backtests never read it: availability at one broker today says nothing about 1996.
--
-- `since` is the data date of the first decision the exclusion binds: the website writes the
-- newest paper_state.last_session, so the decision still waiting to trade is re-picked (`repick`,
-- and the paper night before it settles anything). A removal sets `until` to the day after that
-- date, so a decision already re-picked without the stock still replays without it.
--
-- Rows are never deleted: the replay check reads every decision back against them.
CREATE TABLE IF NOT EXISTS unavailable_symbols (
  id         bigserial PRIMARY KEY,
  symbol     text NOT NULL,
  since      date NOT NULL,
  until      date,
  note       text,
  added_at   timestamptz NOT NULL DEFAULT now(),
  removed_at timestamptz,
  CHECK (until IS NULL OR until >= since)
);

CREATE UNIQUE INDEX IF NOT EXISTS unavailable_symbols_open ON unavailable_symbols (symbol) WHERE until IS NULL;
