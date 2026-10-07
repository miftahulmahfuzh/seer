'use server';

import { revalidatePath } from 'next/cache';
import { auth } from '@/auth';
import { isAllowed } from '@/lib/allow';
import { isSeraUser } from '@/lib/sera/access';
import {
  addUnavailable, dispatchRepick, normalizeNote, normalizeSymbol, removeUnavailable,
} from '@/lib/sera/gotrade';
import { addedState, BAD_SYMBOL, NOT_ALLOWED, removedState, WRITE_FAILED, type FormState } from './view';

/** The /sera gate, as a yes/no: the same two predicates requireSera and the journal route use. */
async function isSeraCaller(): Promise<boolean> {
  const session = await auth();
  const email = session?.user?.email;
  return isAllowed(email, process.env.ALLOWED_EMAIL) && isSeraUser(email);
}

/** Puts a stock on the "Not on Gotrade" list, then asks the engine to re-pick. */
async function addStock(formData: FormData): Promise<FormState> {
  const symbol = normalizeSymbol(formData.get('symbol'));
  if (!symbol) return BAD_SYMBOL;
  const note = normalizeNote(formData.get('note'));

  let result: 'added' | 'already';
  try {
    result = await addUnavailable(symbol, note);
  } catch (e) {
    console.error('unavailable_symbols add failed', e);
    return WRITE_FAILED;
  }
  const live = result === 'added' ? await dispatchRepick() : false;
  revalidatePath('/sera/gotrade');
  return addedState(symbol, result, live);
}

/** Takes a stock off the list (it is on Gotrade again), then asks the engine to re-pick. */
async function removeStock(formData: FormData): Promise<FormState> {
  const symbol = normalizeSymbol(formData.get('symbol'));
  if (!symbol) return BAD_SYMBOL;

  let removed: boolean;
  try {
    removed = await removeUnavailable(symbol);
  } catch (e) {
    console.error('unavailable_symbols remove failed', e);
    return WRITE_FAILED;
  }
  const live = removed ? await dispatchRepick() : false;
  revalidatePath('/sera/gotrade');
  return removedState(symbol, removed, live);
}

/**
 * The one action both forms on /sera/gotrade post to: `op` is 'add' (with symbol and note) or
 * 'remove' (with symbol). One action, so the page has one status line whichever form was used,
 * and it survives the removed row unmounting.
 */
export async function changeList(_prev: FormState, formData: FormData): Promise<FormState> {
  if (!(await isSeraCaller())) return NOT_ALLOWED;
  const op = formData.get('op');
  if (op === 'add') return addStock(formData);
  if (op === 'remove') return removeStock(formData);
  return BAD_SYMBOL;
}
