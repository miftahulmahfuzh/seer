-- Strategy C (handover D1, D7). 003 deleted the unreferenced 'C' row; this puts the roster row back.
INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id) VALUES
  ('C', 'C · News veto', 'A''s picks, LLM can veto on news', 'gavel', false, false, 5, 'bracket', 'design-v0')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, sub = EXCLUDED.sub, icon = EXCLUDED.icon,
  is_champion = EXCLUDED.is_champion, is_benchmark = EXCLUDED.is_benchmark, sort = EXCLUDED.sort,
  engine = EXCLUDED.engine, rules_id = EXCLUDED.rules_id;

-- One row per (strategy, session, candidate): the news check `veto` ran the night before the session.
-- Replay (paper_check) reads these; the LLM is never re-asked (handover §2, D8).
CREATE TABLE IF NOT EXISTS news_vetoes (
  strategy_id     text NOT NULL REFERENCES strategies(id),
  session_date    date NOT NULL,                 -- the session the candidate would be bought for
  rank            int NOT NULL CHECK (rank >= 1),-- rank in A's list (1..max_candidates)
  symbol          text NOT NULL,
  verdict         text NOT NULL CHECK (verdict IN ('allow', 'veto', 'failed')),
  reason          text NOT NULL,                 -- the LLM's sentence, or why the check failed (redacted)
  model           text,                          -- LLM_MODEL as configured that night; NULL when unset
  prompt_version  text NOT NULL,                 -- 'c-veto-v1'
  headlines       jsonb NOT NULL DEFAULT '[]',   -- [{id, datetime (ISO UTC), source, headline}], newest first
  earnings_date   date,                          -- earnings found inside the holding window, if any
  decided_at      timestamptz NOT NULL,          -- the veto run's start: the news cutoff
  PRIMARY KEY (strategy_id, session_date, symbol),
  UNIQUE (strategy_id, session_date, rank)
);
