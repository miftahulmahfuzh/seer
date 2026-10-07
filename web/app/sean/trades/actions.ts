'use server';

import { revalidatePath } from 'next/cache';
import { removeOrder } from '@/lib/sean/data';
import { dispatchSeanMarks } from '@/lib/sean/dispatch';
import { isSeanCaller } from '@/lib/sean/gate';
import { DELETE_FAILED, DELETED, NOT_ALLOWED, NOT_THERE, parseOrderId, type FormState } from './view';

/** Deletes one order (a misread or a mistaken upload), then asks the engine to redo the P&L. */
export async function deleteOrder(_prev: FormState, formData: FormData): Promise<FormState> {
  if (!(await isSeanCaller())) return NOT_ALLOWED;
  const id = parseOrderId(formData.get('id'));
  if (id === null) return NOT_THERE;

  let removed: boolean;
  try {
    removed = await removeOrder(id);
  } catch (e) {
    console.error('sean_orders delete failed', e);
    return DELETE_FAILED;
  }
  if (removed) await dispatchSeanMarks();
  revalidatePath('/sean', 'layout');
  return removed ? DELETED : NOT_THERE;
}

/**
 * Called by the uploader once a batch saved at least one order: asks the engine to fetch prices
 * and redo the daily P&L now instead of tonight. Best effort; returns whether it was asked.
 */
export async function refreshPnl(): Promise<boolean> {
  if (!(await isSeanCaller())) return false;
  const sent = await dispatchSeanMarks();
  revalidatePath('/sean', 'layout');
  return sent;
}
