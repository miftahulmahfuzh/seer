'use client';

import { Archive, ChevronDown, ChevronUp } from 'lucide-react';
import { useState, type CSSProperties, type ReactNode } from 'react';
import s from './leaderboard.module.css';

/**
 * The retired strategies, folded away under the live ones (owner, 2026-10-17). Closed by default so
 * the board reads as what is trading now; open when the picked strategy is one of them, so a link
 * to a retired record never lands on a hidden card. The cards themselves are rendered on the server
 * and handed in as `children`; only the fold is client state.
 *
 * The toggle is the design's "Why this pick" control: a 44px icon-only chevron, soft while closed,
 * inverted while open, with the action as its tooltip and accessible name.
 */
export function RetiredShelf({ count, cols, open: startOpen, children }: {
  count: number;
  /** How many live cards share the row above: the shelf's desktop grid keeps their column width. */
  cols: number;
  open: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(startOpen);
  const tip = open ? 'Hide retired strategies' : 'Show retired strategies';
  return (
    <section className={`sheet over ${s.shelf}`} aria-labelledby="retired-title">
      <div className={s.shelfHead}>
        <span className={s.shelfIcon} aria-hidden="true"><Archive size={20} strokeWidth={1.6} /></span>
        <div className={s.shelfText}>
          <h2 id="retired-title" className="eyebrow">Retired · {count}</h2>
          <span className={s.shelfSub}>Stopped trading. Every record is kept.</span>
        </div>
        <button type="button" className={`icon-btn sm ${open ? 'inverted' : 'soft'}`} data-tip={tip}
          aria-label={tip} aria-expanded={open} aria-controls="retired-cards" onClick={() => setOpen(o => !o)}>
          {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>
      </div>
      <div id="retired-cards" className={s.shelfCards} hidden={!open}
        style={{ '--cols': Math.max(cols, count) } as CSSProperties}>{children}</div>
    </section>
  );
}
