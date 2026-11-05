-- Seer schema v27: Seer Adversarial -- Claude reviews the roster's picks, and plain A comes back
-- (owner, 2026-11-05).
--
-- WHAT IT IS. Before a roster method's pick is bought, Claude -- running in the owner's notes daemon
-- (mcp-notes), not in this repo -- researches it on the web and says agree, object or can't tell, with
-- a link for every claim. Each eligible method then gets a "Claude twin": a separate paper book that
-- runs the same method but drops what Claude objected to, simulated by Seer's one simulator with the
-- same fees and deposits, so the leaderboard, the go-live checklist and paper_check judge it like any
-- other entry. Over about eighteen months the owner sees whether the twins beat the originals on
-- Seer's own order of cause: beat SPY, make the most money, fall less. The design brief is
-- docs/plans/2026-11-05-seer-adversarial-design.md in the mcp-notes repo.
--
-- WHAT THIS FILE ADDS, AND WHO WRITES EACH PART.
--   strategies.twin_of       set on a twin row, naming its original. At most one ACTIVE twin per
--                            original (strategies_one_active_twin). This file inserts NO twin: the
--                            paper night creates and retires them (paper.store.ensure_twins, a later
--                            change), so a method Sera admits next month gets its twin with no
--                            migration and no manual step.
--   strategy_candidates      written by `paper`, inside the night's one transaction: for each active,
--                            non-twin, non-benchmark bracket method, its OWN ranked top 10 for the
--                            session being decided, BEFORE any news veto (C-GT's list is A's ranking,
--                            exactly what `veto` checks, never only what C let through); for each
--                            book, the targets of a rank or kickoff decision, never of a resize-only
--                            one. This is what Claude reviews, so it never has to re-run Seer's methods.
--   book_previews.next_decision_session
--                            the next RANK session after the preview's data date, so the reviewer can
--                            look early at a monthly book without porting Seer's cadence rules.
--   adversary_verdicts       written ONLY by mcp-notes. One row per review of (ORIGINAL strategy,
--                            decision session, symbol). Append-only, enforced by a trigger: a row is
--                            never deleted and never edited; the one update allowed links it to the
--                            later re-review that supersedes it (superseded_by), so the history stays.
--   adversary_marks          written ONLY by mcp-notes: 'paused' when the owner's ON/OFF toggle was off
--                            for that decision. No verdict and no mark means absent.
--   adversary_leases         written ONLY by mcp-notes: which of the owner's two machines is reviewing
--                            a (strategy, session), expiring by this database's clock.
--
-- THE HONESTY RULE THE TABLES ARE BUILT FOR. A verdict counts only if decided_at is before 09:30 New
-- York on its session (seer_engine.dates.session_open_utc: 14:30 UTC in US winter, 13:30 in summer).
-- Missing, failed or late means the twin copies its original. The engine takes the latest verdict
-- decided before the open and never reads superseded_by, which is history for people, not an input.
-- Claude cannot be backtested -- it already knows how the past went -- so no twin ever gets a backtest.
--
-- A-GT: PLAIN A COMES BACK. No plain A has traded since 013 retired it; C-GT is A's only descendant on
-- the roster. The owner wants A, C and A-with-Claude compared three ways, so A-GT is admitted: Strategy
-- A's own rule (STRATEGY_A, unchanged since it was frozen) under design-v0-gotrade, the rule set C-GT
-- trades -- 4 slots, 5-day brackets, whole shares, Gotrade's measured fees -- on the same 10,000,000
-- IDR start and the same 5,000,000 IDR on the 25th of each month. It is NOT a candidate for real money:
-- its gate failed out of sample (2022-01-03..2026-10-02: -15.0% vs SPY TR +71.9%, PF 0.92, max DD
-- 33.3%), and its row says so. It is here as the baseline.
--
-- WHY A NEW ID AND NOT REVIVING A. A is frozen under design-v0 (a flat 0.1% a side) with its own pinned
-- digest; moving it to Gotrade's fees would change that digest and store.check_digest would refuse its
-- next night. The rule (docs/runbooks/paper-trading.md) is a new entry with a new id and its own clock,
-- as 010, 013, 017, 021 and 022 did. A stays retired and keeps every row it wrote.
--
-- NOT TOUCHED. The section 1 real-money bar. C-GT, its veto and its prompt. Every started entry's spec
-- digest (sort, status and paper_end are outside the spec, and nothing else of theirs moves). The
-- mcp-notes connector's read-only guard: mcp-notes writes the three adversary tables through a separate,
-- narrow writer.
--
-- The A-GT row below is byte for byte paper/roster.py's SEED_ROWS (the migration-equality test,
-- tests/test_paper_roster.py::test_the_migration_rows_equal_the_seed_rows). paper_start, the frozen spec
-- and the paper clock are written by the entry's first night, as for every new entry.

-- ---- twins ------------------------------------------------------------------------------------------

ALTER TABLE strategies ADD COLUMN IF NOT EXISTS twin_of text NULL REFERENCES strategies(id);
ALTER TABLE strategies DROP CONSTRAINT IF EXISTS strategies_twin_of_not_self;
ALTER TABLE strategies ADD CONSTRAINT strategies_twin_of_not_self CHECK (twin_of IS NULL OR twin_of <> id);
CREATE UNIQUE INDEX IF NOT EXISTS strategies_one_active_twin
    ON strategies (twin_of) WHERE twin_of IS NOT NULL AND status = 'active';

-- ---- what Claude reviews ------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS strategy_candidates (
  strategy_id  text NOT NULL REFERENCES strategies(id),
  session_date date NOT NULL,                     -- the decision session
  data_date    date NOT NULL,                     -- the night that decided it: prev_session(session_date)
  kind         text NOT NULL CHECK (kind IN ('bracket', 'book')),
  rank         integer NOT NULL CHECK (rank >= 1),
  symbol       text NOT NULL CHECK (symbol <> ''),
  weight       numeric NULL,                      -- a book target's weight; NULL for a bracket candidate
  evidence     jsonb NULL CHECK (evidence IS NULL OR jsonb_typeof(evidence) = 'array'),
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (strategy_id, session_date, symbol),
  UNIQUE (strategy_id, session_date, rank),
  CHECK (data_date < session_date),
  -- weight IS NOT NULL is spelled out: a bare `weight > 0` is NULL for a NULL weight, and a CHECK
  -- that is NULL passes, so a book row with no weight would be admitted.
  CHECK ((kind = 'bracket' AND weight IS NULL) OR (kind = 'book' AND weight IS NOT NULL AND weight > 0 AND weight <= 1))
);
CREATE INDEX IF NOT EXISTS strategy_candidates_session ON strategy_candidates (session_date, strategy_id);

-- The reviewer's early look at a book's next rank decision.
ALTER TABLE book_previews ADD COLUMN IF NOT EXISTS next_decision_session date NULL;
ALTER TABLE book_previews DROP CONSTRAINT IF EXISTS book_previews_next_after_data;
ALTER TABLE book_previews ADD CONSTRAINT book_previews_next_after_data
    CHECK (next_decision_session IS NULL OR next_decision_session > data_date);

-- ---- what Claude said -----------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS adversary_verdicts (
  id              bigserial PRIMARY KEY,
  strategy_id     text NOT NULL REFERENCES strategies(id),   -- the ORIGINAL, never the twin
  session_date    date NOT NULL,                             -- the decision session
  symbol          text NOT NULL,
  verdict         text NOT NULL CHECK (verdict IN ('agree', 'object', 'unsure')),
  reason          text NOT NULL CHECK (char_length(reason) BETWEEN 1 AND 600),
  sources         jsonb NOT NULL DEFAULT '[]'::jsonb,        -- [{url,title,publisher,published_at,fetched_at}]
  lens            text NOT NULL,                             -- method brief id@version
  model           text NOT NULL,                             -- exact verdict model id
  prompt_version  text NOT NULL,                             -- hash of lens + system prompt + models
  host            text NOT NULL,
  started_at      timestamptz NOT NULL,
  decided_at      timestamptz NOT NULL,
  superseded_by   bigint NULL REFERENCES adversary_verdicts(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  -- agree and object cite at least one fetched source; a non-array is refused, never an error
  CHECK (CASE
           WHEN jsonb_typeof(sources) <> 'array' THEN false
           WHEN verdict = 'unsure' THEN true
           ELSE jsonb_array_length(sources) >= 1
         END),
  CHECK (decided_at >= started_at)
);
CREATE INDEX IF NOT EXISTS adversary_verdicts_key
    ON adversary_verdicts (strategy_id, session_date, symbol, decided_at);

-- Append-only. A verdict is never deleted and never edited; the one update allowed links it to the
-- later verdict on the same (strategy, session, symbol) that supersedes it, and only once.
CREATE OR REPLACE FUNCTION adversary_verdicts_append_only() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'adversary_verdicts is append-only: verdict % cannot be deleted', OLD.id;
  END IF;
  IF OLD.superseded_by IS NOT NULL THEN
    RAISE EXCEPTION 'adversary_verdicts is append-only: verdict % is already superseded by %',
      OLD.id, OLD.superseded_by;
  END IF;
  IF NEW.superseded_by IS NULL
     OR (to_jsonb(NEW) - 'superseded_by') IS DISTINCT FROM (to_jsonb(OLD) - 'superseded_by') THEN
    RAISE EXCEPTION 'adversary_verdicts is append-only: the only update allowed sets superseded_by on verdict %',
      OLD.id;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM adversary_verdicts n
    WHERE n.id = NEW.superseded_by
      AND n.id > OLD.id
      AND n.strategy_id = OLD.strategy_id
      AND n.session_date = OLD.session_date
      AND n.symbol = OLD.symbol
  ) THEN
    RAISE EXCEPTION 'adversary_verdicts: verdict % can only be superseded by a later verdict on the same strategy, session and symbol',
      OLD.id;
  END IF;
  RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS adversary_verdicts_append_only ON adversary_verdicts;
CREATE TRIGGER adversary_verdicts_append_only
  BEFORE UPDATE OR DELETE ON adversary_verdicts
  FOR EACH ROW EXECUTE FUNCTION adversary_verdicts_append_only();

CREATE TABLE IF NOT EXISTS adversary_marks (
  strategy_id  text NOT NULL REFERENCES strategies(id),   -- the ORIGINAL
  session_date date NOT NULL,
  mark         text NOT NULL CHECK (mark IN ('paused')),
  host         text NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (strategy_id, session_date)
);

CREATE TABLE IF NOT EXISTS adversary_leases (
  strategy_id  text NOT NULL REFERENCES strategies(id),
  session_date date NOT NULL,
  host         text NOT NULL,
  claimed_at   timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL,
  PRIMARY KEY (strategy_id, session_date)
);

-- ---- A-GT ---------------------------------------------------------------------------------------------

INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id,
                        object_name, registry_id, gate_note, gate_applicable, promoted_from) VALUES
  ('A-GT', 'A · Dip buy', 'Buys a sharp short drop in a stock above its 200-day average, sells within 5 days, daily, real Gotrade fees', 'sigma', false, false, 5, 'bracket', 'design-v0-gotrade', 'STRATEGY_A', NULL, 'Plain Strategy A, back on paper (owner, 2026-11-05) as the baseline that C-GT and the Claude twins are compared against: the same rule, the same 4 slots and 5-day brackets, and the same starting capital, monthly deposits and Gotrade fees as C-GT, with no news check. It is not a candidate for real money: its backtest gate failed out of sample (2022-01-03..2026-10-02), -15.0% vs SPY TR +71.9%, PF 0.92, max DD 33.3%, which is why 013 retired the whole-share A', true, NULL)
ON CONFLICT (id) DO NOTHING;
