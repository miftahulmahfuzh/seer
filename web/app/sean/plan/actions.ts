'use server';

import { revalidatePath } from 'next/cache';
import { sql } from '@/lib/db';
import { isSeanCaller } from '@/lib/sean/gate';
import { shortLabel } from '@/lib/strategy';
import {
  BAD_BUDGET, BAD_DATE, BAD_METHOD, linkedState, NOT_ALLOWED, NOT_LINKED, parseBudget, parseSide, parseSince,
  parseSymbol, SAVED, WRITE_FAILED, type FormState,
} from './view';

/** The Plan page and the Plan tab badge read these rows: refresh the whole /sean section. */
function refresh(): void {
  revalidatePath('/sean', 'layout');
}

/**
 * The picker and the settings form both post here. `op` 'link' (strategyId, since, budget) follows
 * a method, replacing any other; 'edit' (since, budget) changes the followed one.
 */
export async function linkMethod(_prev: FormState, formData: FormData): Promise<FormState> {
  if (!(await isSeanCaller())) return NOT_ALLOWED;
  const since = parseSince(formData.get('since'));
  if (!since) return BAD_DATE;
  const budget = parseBudget(formData.get('budget'));
  if (!budget.ok) return BAD_BUDGET;
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
          budget_usd = EXCLUDED.budget_usd, linked_at = now()`;
      refresh();
      return linkedState(shortLabel(m.name, m.id));
    }
    if (op === 'edit') {
      const rows = await sql`UPDATE sean_link SET since = ${since}::date, budget_usd = ${budget.value}::numeric
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
