'use client';

import { Check, LoaderCircle, Trash2, X } from 'lucide-react';
import { useActionState, useState } from 'react';
import { deleteOrder } from './actions';
import { IDLE } from './view';
import s from './trades.module.css';

/** Trash, then a coral check to confirm (or X to keep it). Labels name the order in plain words. */
export function DeleteOrder({ id, label, confirmLabel }: { id: number; label: string; confirmLabel: string }) {
  const [state, action, pending] = useActionState(deleteOrder, IDLE);
  const [asking, setAsking] = useState(false);

  return (
    <div className={s.del}>
      {asking ? (
        <form action={action} className={s.delForm}>
          <input type="hidden" name="id" value={id} />
          <button type="button" className="icon-btn sm" disabled={pending} onClick={() => setAsking(false)}
            aria-label="Keep it" data-tip="Keep it">
            <X size={18} strokeWidth={1.5} />
          </button>
          <button type="submit" className={`icon-btn sm ${s.confirm}`} disabled={pending}
            aria-label={confirmLabel} data-tip={confirmLabel}>
            {pending
              ? <LoaderCircle size={18} strokeWidth={1.75} className={s.spin} />
              : <Check size={18} strokeWidth={1.75} />}
          </button>
        </form>
      ) : (
        <button type="button" className="icon-btn sm" onClick={() => setAsking(true)} aria-label={label} data-tip={label}>
          <Trash2 size={18} strokeWidth={1.5} />
        </button>
      )}
      {state.tone === 'error' && <span className={s.rowError} role="status">{state.message}</span>}
    </div>
  );
}
