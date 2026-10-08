-- Seer schema v19: the plan's opening deposit, in dollars (owner, 2026-10-08).
--
-- sean_link's wallet is DERIVED (web/lib/sean/cash.ts): deposits through today, less what the
-- plan's own orders spent. The deposits come from a schedule whose opening is a round
-- 10,000,000 IDR converted at the newest fx_rates row -- a MARKET mid. The rate the owner's
-- transfer actually got includes Gotrade's spread, so the wallet carries that spread as a
-- standing error.
--
-- Measured 2026-10-08, against his own Gotrade balance:
--     derived   10,000,000 / 17,871        = $559.57  ->  wallet $71.24
--     real      opening cash               = $555.69  ->  wallet $67.36   (Gotrade: $67.36)
-- a $3.88 overstatement, an implied effective rate of ~17,996 against the market's 17,871
-- (0.7%, which is what a broker FX spread looks like).
--
-- The opening deposit is the ONE deposit the owner can read straight off his balance, so it is
-- the one worth storing exactly. NULL keeps the pure-rupiah behaviour, so a plan that has not
-- recorded one converts exactly as it did before and no existing number moves.
--
-- Not budget_usd. That override replaces the whole PLAN SIZE (holdings + wallet), so using it to
-- correct the wallet would pin the plan to a figure that goes stale the next time a holding's
-- price moves. This corrects the wallet at its source and leaves the plan size derived.
ALTER TABLE sean_link ADD COLUMN IF NOT EXISTS opening_usd numeric(14,2);

COMMENT ON COLUMN sean_link.opening_usd IS
  'The plan''s opening deposit in USD, read off the broker balance. NULL = convert initialIdr at the latest fx rate.';
