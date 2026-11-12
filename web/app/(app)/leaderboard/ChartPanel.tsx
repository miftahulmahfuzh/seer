'use client';

import { useState, type CSSProperties, type ReactNode } from 'react';
import s from './leaderboard.module.css';

/** One equity curve as `buildChart` (page.tsx) draws it: an svg path in the chart's own units. */
export type ChartLine = { id: string; d: string; color: string; width: number; dash: string | null };

/**
 * One legend toggle. The page builds it (`legendEntry`) from the strategy and its look, so this
 * module needs nothing from `view.ts`.
 */
export type LegendEntry = {
  id: string;
  /** The short code the item shows. */
  code: string;
  /** The full name (a retired one says when it stopped): the tooltip and the accessible name. */
  tip: string;
  retired: boolean;
  /** The line's colour, for the swatch. */
  line: string;
  /** The swatch's stroke: solid, SPY's dotted benchmark, or a lap or twin dash. */
  stroke: 'solid' | 'dotted' | 'dashed';
  /** The pill's background while the item is pressed: the strategy's sheet tint. */
  pill: string;
};

/**
 * The leaderboard's chart sheet (owner, 2026-11-12). It is a client component because its legend
 * is a row of toggles: pressing one highlights that strategy's line, so the owner can press two
 * and compare them. Highlighted lines keep their own colour, are 1px thicker and are drawn above
 * the rest; every other line fades to 20% (the stylesheet, from `data-focus` / `data-on`). With
 * nothing pressed the chart is exactly what it was before the legend could be pressed. Any number
 * can be pressed, SPY included.
 *
 * The picked card is pressed too. `pickId` comes from the URL (`?s=`), and a card is a `<Link>`
 * soft navigation, which keeps this component mounted with its state: a new pick is ADDED to what
 * is already pressed (the owner's answer, "Add."), never replaces it, and pressing the picked
 * strategy's item again un-highlights its line while the card stays picked. The set lives in this
 * component's memory only ("memory only for now"): a reload starts again from the pick alone.
 *
 * The figures above the chart are rendered on the server and handed in as `head`; the axis comes
 * in as plain labels (a server-rendered list handed across this boundary set off React's missing-key
 * warning). Only the lines and the two legends (desktop, under the headline; phone, under the axis)
 * read the state, and they share it.
 */
export function ChartPanel({ pickId, entries, lines, grid, zero, labels, w, h, head }: {
  /** The picked strategy's id, or null when there is no research strategy to pick. */
  pickId: string | null;
  /** One per strategy on the chart, in board order. */
  entries: LegendEntry[];
  /** Champion last, as `buildChart` orders them. */
  lines: ChartLine[];
  grid: number[];
  zero: number;
  /** The axis labels under the chart. */
  labels: string[];
  /** The svg's viewBox width and height. */
  w: number;
  h: number;
  head: ReactNode;
}) {
  const [active, setActive] = useState<ReadonlySet<string>>(() => new Set(pickId === null ? [] : [pickId]));
  // A new pick arrives as a prop on a soft navigation. React's "adjust state when a prop changes"
  // pattern: compare with the pick last seen during render and add the new one, no Effect.
  const [seenPick, setSeenPick] = useState(pickId);
  if (pickId !== seenPick) {
    setSeenPick(pickId);
    if (pickId !== null && !active.has(pickId)) setActive(new Set(active).add(pickId));
  }

  // Only ids on the chart count: a retired pick left in the set after the owner picks a live card
  // has no line and no legend item, and must not fade everything else.
  const lit: ReadonlySet<string> = new Set(entries.filter(e => active.has(e.id)).map(e => e.id));
  const focus = lit.size > 0 ? 'true' : undefined;
  // Highlighted lines last, so they draw on top; each group keeps `buildChart`'s order.
  const drawn = focus ? [...lines.filter(l => !lit.has(l.id)), ...lines.filter(l => lit.has(l.id))] : lines;
  const toggle = (id: string) => setActive(prev => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });

  return (
    <section className={`sheet bg-sheet ${s.chartSheet}`}>
      {head}
      <div className={`${s.pad} desk-only`}>
        <Legend entries={entries} lit={lit} focus={focus} onToggle={toggle} className={`${s.legend} ${s.legendDesk}`} />
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={s.chart} role="img"
        aria-label="Equity curves of each strategy against SPY" data-focus={focus}>
        {grid.map((y, i) => <line key={i} x1="0" x2={w} y1={y} y2={y} vectorEffect="non-scaling-stroke" stroke="var(--hair)" />)}
        <line x1="0" x2={w} y1={zero} y2={zero} vectorEffect="non-scaling-stroke" stroke="var(--outline)" strokeDasharray="3 3" />
        {drawn.map(l => {
          const on = lit.has(l.id);
          return (
            <path key={l.id} data-line={l.id} data-on={on ? 'true' : undefined} d={l.d}
              vectorEffect="non-scaling-stroke" fill="none" stroke={l.color} strokeWidth={on ? l.width + 1 : l.width}
              strokeDasharray={l.dash ?? undefined} strokeLinecap="round" strokeLinejoin="round" />
          );
        })}
      </svg>
      <div className={`${s.axis} ${s.pad}`}>{labels.map((l, i) => <span key={i}>{l}</span>)}</div>
      <div className={`${s.pad} mobile-only`}>
        <Legend entries={entries} lit={lit} focus={focus} onToggle={toggle} className={`${s.legend} ${s.legendRow}`} />
      </div>
    </section>
  );
}

/**
 * One toggle per strategy: its swatch and code, its full name as the tooltip and accessible name.
 * The toggles carry text, an exception to the icon-only rule the owner accepted: the code is how
 * the lines are told apart. On desktop it is one row (`.legendDesk`); on the phone it wraps.
 */
function Legend({ entries, lit, focus, onToggle, className }: {
  entries: LegendEntry[];
  lit: ReadonlySet<string>;
  focus: string | undefined;
  onToggle: (id: string) => void;
  className: string;
}) {
  return (
    <div role="group" aria-label="Highlight lines" className={className} data-focus={focus}>
      {entries.map(e => (
        <button key={e.id} type="button" data-id={e.id} aria-pressed={lit.has(e.id)}
          data-tip={e.tip} aria-label={e.tip}
          className={e.retired ? `${s.legendItem} ${s.legendRetired}` : s.legendItem}
          style={{ '--pill': e.pill } as CSSProperties} onClick={() => onToggle(e.id)}>
          {e.stroke === 'solid'
            ? <span className={s.swatch} style={{ background: e.line }} />
            : <span className={s.swatchDash} style={{ borderTopColor: e.line, borderTopStyle: e.stroke }} />}
          <span className={s.legendLabel}>{e.code}</span>
        </button>
      ))}
    </div>
  );
}
