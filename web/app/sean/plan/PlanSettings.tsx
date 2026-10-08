'use client';

import { Check, LoaderCircle } from 'lucide-react';
import { useActionState } from 'react';
import { linkMethod } from './actions';
import { IDLE } from './view';
import s from './plan.module.css';

/**
 * Change the followed plan's start date, the cash it opened with, and its plan size.
 *
 * An empty plan size means "what it holds plus the wallet". An empty opening means "convert the
 * 10,000,000 IDR at the latest rate" -- which carries the broker's FX spread, so typing the figure
 * off the Gotrade balance is what makes the wallet match the app to the cent.
 */
export function PlanSettings(
  { since, budget, opening }: { since: string; budget: number | null; opening: number | null },
) {
  const [state, action, pending] = useActionState(linkMethod, IDLE);
  return (
    <form action={action} className={s.settingsForm}>
      <input type="hidden" name="op" value="edit" />
      <div className={s.settings}>
        <label className={s.field}>
          <span className={s.fieldLabel}>Counting your orders from</span>
          <input type="date" name="since" defaultValue={since} required className={s.input} disabled={pending} />
        </label>
        <label className={s.field}>
          <span className={s.fieldLabel}>Cash you started with</span>
          <input name="opening" inputMode="decimal" defaultValue={opening === null ? '' : opening.toFixed(2)}
            placeholder="Work it out" className={s.input} autoComplete="off" disabled={pending} />
        </label>
        <label className={s.field}>
          <span className={s.fieldLabel}>Plan size in dollars</span>
          <input name="budget" inputMode="decimal" defaultValue={budget === null ? '' : budget.toFixed(2)}
            placeholder="What it holds" className={s.input} autoComplete="off" disabled={pending} />
        </label>
        <button type="submit" className={`icon-btn ${s.go}`} disabled={pending}
          aria-label="Save the plan settings" data-tip="Save the plan settings">
          {pending
            ? <LoaderCircle size={22} strokeWidth={1.75} style={{ animation: 'spin 0.9s linear infinite' }} />
            : <Check size={22} strokeWidth={1.75} />}
        </button>
      </div>
      <p className={state.tone === 'error' ? s.error : s.status} aria-live="polite" role="status">
        {state.message}
      </p>
    </form>
  );
}
