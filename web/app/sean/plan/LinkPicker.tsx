'use client';

import { Link2, LoaderCircle } from 'lucide-react';
import { useActionState, useState } from 'react';
import { strategyIcon } from '@/components/roster';
import { shortDate } from '@/lib/format';
import type { LinkableMethod } from '@/lib/sean/planData';
import { linkMethod } from './actions';
import { IDLE, methodTitle } from './view';
import s from './plan.module.css';

/**
 * Pick one roster method to follow. The start date defaults to the method's newest pick, so orders
 * placed to follow that pick count and everything bought before stays out of the plan.
 */
export function LinkPicker({ methods, today }: { methods: LinkableMethod[]; today: string }) {
  const [state, action, pending] = useActionState(linkMethod, IDLE);
  const [chosen, setChosen] = useState<string>(methods[0]?.id ?? '');
  const [since, setSince] = useState<string>(methods[0]?.lastPick ?? today);

  if (methods.length === 0) {
    return <p className={s.empty}>No method on Seer&apos;s roster can be followed right now.</p>;
  }

  const choose = (m: LinkableMethod) => {
    setChosen(m.id);
    setSince(m.lastPick ?? today);
  };

  return (
    <form action={action} className={s.picker}>
      <input type="hidden" name="op" value="link" />
      <fieldset className={s.choices} disabled={pending}>
        <legend className={s.sr}>Method to follow</legend>
        {methods.map(m => {
          const Icon = strategyIcon(m.icon);
          return (
            <label key={m.id} className={s.choice}>
              <input type="radio" name="strategyId" value={m.id} checked={chosen === m.id}
                onChange={() => choose(m)} className={s.sr} />
              <span className={s.choiceIcon} aria-hidden="true"><Icon size={22} strokeWidth={1.5} /></span>
              <span className={s.choiceText}>
                <span className={s.choiceName}><b>{m.short}</b> {methodTitle(m.name)}</span>
                <span className={s.choiceSub}>{m.sub}</span>
                <span className={s.choiceWhen}>
                  {m.lastPick ? `Last picked for ${shortDate(m.lastPick)}` : 'Has not picked yet'}
                </span>
              </span>
            </label>
          );
        })}
      </fieldset>

      <div className={s.settings}>
        <label className={s.field}>
          <span className={s.fieldLabel}>Counting your orders from</span>
          <input type="date" name="since" value={since} onChange={e => setSince(e.target.value)} required
            className={s.input} disabled={pending} />
        </label>
        <label className={s.field}>
          <span className={s.fieldLabel}>Plan size in dollars, if you want one</span>
          <input name="budget" inputMode="decimal" placeholder="What it holds" className={s.input}
            autoComplete="off" disabled={pending} />
        </label>
        <button type="submit" className={`icon-btn ${s.go}`} disabled={pending || chosen === ''}
          aria-label="Follow this method" data-tip="Follow this method">
          {pending
            ? <LoaderCircle size={22} strokeWidth={1.75} style={{ animation: 'spin 0.9s linear infinite' }} />
            : <Link2 size={22} strokeWidth={1.75} />}
        </button>
      </div>

      <p className={state.tone === 'error' ? s.error : s.status} aria-live="polite" role="status">
        {state.message}
      </p>
    </form>
  );
}
