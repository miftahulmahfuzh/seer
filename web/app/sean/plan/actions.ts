'use server';

import { revalidatePath } from 'next/cache';
import { sql } from '@/lib/db';
import { isSeanCaller } from '@/lib/sean/gate';
import { shortLabel } from '@/lib/strategy';
import {
  BAD_BUDGET, BAD_DATE, BAD_METHOD, BAD_OPENING, linkedState, NOT_ALLOWED, NOT_LINKED, parseBudget,
  parseSide, parseSince, parseSymbol, SAVED, WRITE_FAILED, type FormState,
} from './view';

/** The Plan page and the Plan tab badge read these rows: refresh the whole /sean section. */
function refresh(): void {
  revalidatePath('/sean', 'layout');
}

/**
 * The picker and the settings form both post here. `op` 'link' (strategyId, since, budget) follows
 * a method, replacing any other; 'edit' (since, budget, opening) changes the followed one.
 *
 * `opening_usd` is deliberately NOT touched by 'link': it is a fact about the owner's own account
 * -- the cash the plan opened with, read off his broker balance -- not about which method he
 * follows, so switching methods must not silently drop it. Only the settings form sets it.
 */
export async function linkMethod(_prev: FormState, formData: FormData): Promise<FormState> {
  if (!(await isSeanCaller())) return NOT_ALLOWED;
  const since = parseSince(formData.get('since'));
  if (!since) return BAD_DATE;
  const budget = parseBudget(formData.get('budget'));
  if (!budget.ok) return BAD_BUDGET;
  // Same shape as a plan size: a positive amount of dollars, or empty for "work it out".
  const opening = parseBudget(formData.get('opening'));
  if (!opening.ok) return BAD_OPENING;
  const op = formData.get('op');

  try {
    if (op === 'link') {
      const id = formData.get('strategyId');
      if (typeof id !== 'string' || id === '') return BAD_METHOD;
      const [m] = await sql`SELECT id, name FROM strategies
        WHERE id = ${id} AND status = 'active' AND engine = 'book' AND NOT is_benchmark`;
      if (!m) return BAD_METHOD;
      await sql`INSERT INTO sean_link (id, strategy_id, since, budget_usd)
        VALUES (1, ${id}, ${since}::date, ${budget.value}::numeric)
        ON CONFLICT (id) DO UPDATE SET strategy_id = EXCLUDED.strategy_id, since = EXCLUDED.since,
          budget_usd = EXCLUDED.budget_usd, linked_at = now()`;  // opening_usd kept: see above
      refresh();
      return linkedState(shortLabel(m.name, m.id));
    }
    if (op === 'edit') {
      const rows = await sql`UPDATE sean_link SET since = ${since}::date,
          budget_usd = ${budget.value}::numeric, opening_usd = ${opening.value}::numeric
        WHERE id = 1 RETURNING id`;
      if (rows.length === 0) return NOT_LINKED;
      refresh();
      return SAVED;
    }
  } catch (e) {
    console.error('sean_link write failed', e);
    return WRITE_FAILED;
  }
  return BAD_METHOD;
}

/** Stop following. Done marks stay (keyed by method and decision), harmless if it is followed again. */
export async function unlinkMethod(): Promise<void> {
  if (!(await isSeanCaller())) return;
  try {
    await sql`DELETE FROM sean_link WHERE id = 1`;
  } catch (e) {
    console.error('sean_link delete failed', e);
    return;
  }
  refresh();
}

/** Mark one reminder of the followed method's decision as done by hand. */
export async function markDone(formData: FormData): Promise<void> {
  if (!(await isSeanCaller())) return;
  const sessionDate = parseSince(formData.get('sessionDate'));
  const symbol = parseSymbol(formData.get('symbol'));
  const side = parseSide(formData.get('side'));
  if (!sessionDate || !symbol || !side) return;
  try {
    await sql`INSERT INTO sean_reminder_marks (strategy_id, session_date, symbol, action)
      SELECT strategy_id, ${sessionDate}::date, ${symbol}::text, ${side}::text FROM sean_link WHERE id = 1
      ON CONFLICT DO NOTHING`;
  } catch (e) {
    console.error('sean_reminder_marks insert failed', e);
    return;
  }
  refresh();
}

/**
 * Claim the plan's shares of one stock as the owner's own (migration 020).
 *
 * Marks every plan-window BUY of `symbol` that is not already claimed. Their shares stop being
 * plan holdings and fall into `outside` -- never sold by Sean, never counted in plan value --
 * exactly as a pre-plan holding is. The money is untouched: it moved through the account whoever
 * the shares were for, so the derived wallet does not change.
 *
 * Per order, not per symbol, and that is the point: the method may legitimately pick this stock in
 * some later month, and those shares WOULD be the plan's. Only the orders claimed here are yours.
 * It cannot recur as a reminder either, because these shares were never plan shares.
 */
export async function claimAsOwn(formData: FormData): Promise<void> {
  if (!(await isSeanCaller())) return;
  const symbol = parseSymbol(formData.get('symbol'));
  if (!symbol) return;
  try {
    await sql`INSERT INTO sean_own_orders (order_id, note)
      SELECT o.id, ${'claimed on the plan page'}
        FROM sean_orders o, sean_link l
       WHERE l.id = 1
         AND o.symbol = ${symbol}
         AND o.side = 'buy'
         AND (o.executed_at AT TIME ZONE 'America/New_York')::date >= l.since
      ON CONFLICT (order_id) DO NOTHING`;
  } catch (e) {
    console.error('sean_own_orders insert failed', e);
    return;
  }
  refresh();
}

/** Give one stock's claimed buys back to the plan. */
export async function unclaimAsOwn(formData: FormData): Promise<void> {
  if (!(await isSeanCaller())) return;
  const symbol = parseSymbol(formData.get('symbol'));
  if (!symbol) return;
  try {
    await sql`DELETE FROM sean_own_orders WHERE order_id IN (
      SELECT o.id FROM sean_orders o WHERE o.symbol = ${symbol} AND o.side = 'buy')`;
  } catch (e) {
    console.error('sean_own_orders delete failed', e);
    return;
  }
  refresh();
}

/** Take a hand-made done mark back. */
export async function undoDone(formData: FormData): Promise<void> {
  if (!(await isSeanCaller())) return;
  const sessionDate = parseSince(formData.get('sessionDate'));
  const symbol = parseSymbol(formData.get('symbol'));
  const side = parseSide(formData.get('side'));
  if (!sessionDate || !symbol || !side) return;
  try {
    await sql`DELETE FROM sean_reminder_marks
      WHERE strategy_id = (SELECT strategy_id FROM sean_link WHERE id = 1)
        AND session_date = ${sessionDate}::date AND symbol = ${symbol} AND action = ${side}`;
  } catch (e) {
    console.error('sean_reminder_marks delete failed', e);
    return;
  }
  refresh();
}
