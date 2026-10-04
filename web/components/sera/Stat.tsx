import type { ReactNode } from 'react';
import s from './Stat.module.css';

export type StatProps = {
  /** Already formatted: '58', '+1.2%', '4 of 6'. */
  value: string;
  label: ReactNode;
  /** Colours the number (--pos / --neg). */
  tone?: 'pos' | 'neg';
  /** Tooltip on the whole tile. */
  tip?: string;
  /** A smaller second line under the label. */
  sub?: ReactNode;
  /** 'lg' (default) 52px number, 'md' 34px. */
  size?: 'lg' | 'md';
};

/** KPI tile: a big tabular number, its label, and an optional plain-language line under it. */
export function Stat({ value, label, tone, tip, sub, size = 'lg' }: StatProps) {
  return (
    <div className={s.stat} data-tip={tip} tabIndex={tip ? 0 : undefined}>
      <span className={`num ${s.value} ${size === 'md' ? s.md : ''} ${tone ?? ''}`}>{value}</span>
      <span className={s.label}>{label}</span>
      {sub ? <span className={s.sub}>{sub}</span> : null}
    </div>
  );
}
