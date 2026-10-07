'use client';

import { LoaderCircle, Plus, Undo2 } from 'lucide-react';
import { useActionState } from 'react';
import { shortDate } from '@/lib/format';
import type { ListedStock } from '@/lib/sera/gotrade';
import { changeList } from './actions';
import { IDLE } from './view';
import s from './gotrade.module.css';

/**
 * The editable list: an add row (ticker, optional note) and one tile per listed stock, each with
 * a button that takes it off the list. Both post to the same action, so one status line reports
 * whichever was used last.
 */
export function GotradeEditor({ listed }: { listed: ListedStock[] }) {
  const [state, action, pending] = useActionState(changeList, IDLE);

  return (
    <div className={s.editor}>
      <form action={action} className={s.add}>
        <input type="hidden" name="op" value="add" />
        <label className={s.field}>
          <span className={s.sr}>Ticker</span>
          <input name="symbol" className={s.ticker} placeholder="Ticker" required maxLength={12}
            autoComplete="off" autoCapitalize="characters" spellCheck={false} disabled={pending} />
        </label>
        <label className={`${s.field} ${s.grow}`}>
          <span className={s.sr}>Note, optional</span>
          <input name="note" className={s.note} placeholder="Note, if you want one" maxLength={200}
            autoComplete="off" disabled={pending} />
        </label>
        <button type="submit" className={`icon-btn ${s.plus}`} disabled={pending}
          aria-label="Add this stock to the list" data-tip="Add to the list">
          {pending ? <LoaderCircle size={22} strokeWidth={1.75} style={{ animation: 'spin 0.9s linear infinite' }} /> : <Plus size={22} strokeWidth={1.75} />}
        </button>
      </form>

      <p className={state.tone === 'error' ? s.error : s.status} aria-live="polite" role="status">
        {state.message}
      </p>

      {listed.length === 0 ? (
        <p className={s.empty}>Nothing is on the list. Seer treats every stock it picks as one Gotrade offers.</p>
      ) : (
        <ul className={s.tiles}>
          {listed.map(r => (
            <li key={r.symbol} className={s.tile}>
              <div className={s.tileMain}>
                <span className={`num ${s.symbol}`}>{r.symbol}</span>
                {r.note && <span className={s.tileNote}>{r.note}</span>}
                <span className={s.added}>Added {shortDate(r.added)}</span>
              </div>
              <form action={action}>
                <input type="hidden" name="op" value="remove" />
                <input type="hidden" name="symbol" value={r.symbol} />
                <button type="submit" className="icon-btn sm" disabled={pending}
                  aria-label={`${r.symbol} is on Gotrade again: take it off the list`}
                  data-tip="On Gotrade again">
                  <Undo2 size={18} strokeWidth={1.5} />
                </button>
              </form>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
