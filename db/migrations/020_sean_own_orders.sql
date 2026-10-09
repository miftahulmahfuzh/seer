-- Seer schema v20: orders that were the owner's own, not the plan's (owner, 2026-10-09).
--
-- Sean classifies an order by DATE alone: on or after sean_link.since it belongs to the plan.
-- Two rules follow from that, each right on its own and wrong together:
--
--   * a sale of a pre-plan holding FUNDS the plan (web/lib/sean/cash.ts says so deliberately --
--     on 2026-10-07 the owner really did sell PLTR to help buy the twenty picks);
--   * a purchase dated after `since` is a PLAN purchase.
--
-- A swap between two personal holdings straddles that line. Measured, 2026-10-08:
--
--   20:31  SELL PLTR  +$99.94   counted as funding the plan (PLTR was bought 2025-06-10)
--   20:33  BUY  NVDA  -$99.94   counted as a plan purchase
--
-- Net to the plan: $0.00 -- and yet the plan was left "holding" 0.425 NVDA it never paid for, so
-- the next decision told the owner to sell it. That is not a policy gap wanting a whitelist; it is
-- a classification bug. The model had no way to say "this was an outside-to-outside rotation".
--
-- A row here marks ONE order as the owner's. The shares it created stop being plan holdings and
-- fall into `outside`, which already means "never sold by Sean, never counted in plan value" and
-- is how every pre-plan holding is protected. CASH IS NOT TOUCHED: the money really did move
-- through the account, so the derived wallet is unchanged and still matches the broker.
--
-- WHY PER ORDER AND NOT PER SYMBOL. A symbol list would blacklist NVDA for ever, so a month when
-- the method genuinely picks it could not be followed. These particular shares were the owner's;
-- the next ones need not be. It also cannot recur as a reminder, because the shares were never
-- plan shares -- nothing to re-click each month.
--
-- Append-only in spirit: a row is deleted only by un-claiming the order on the page, and the
-- order itself is never edited.
CREATE TABLE IF NOT EXISTS sean_own_orders (
  order_id  bigint PRIMARY KEY REFERENCES sean_orders (id) ON DELETE CASCADE,
  note      text,
  marked_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE sean_own_orders IS
  'Orders the owner claimed as personal: their shares are outside the plan. Cash is unaffected.';
