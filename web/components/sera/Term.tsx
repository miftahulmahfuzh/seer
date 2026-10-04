import type { ReactNode } from 'react';
import s from './Term.module.css';

export type TermProps = {
  /** The word as the glossary knows it, e.g. 'CAGR'. */
  term: string;
  /** One plain sentence; shown as the tooltip and read to screen readers. Pages take it from the glossary. */
  definition: string;
  /** What to print, if not `term` itself (e.g. 'worst fall' for 'max drawdown'). */
  children?: ReactNode;
};

/** A jargon word with a dotted underline; hover (or long-press) shows its plain definition. */
export function Term({ term, definition, children }: TermProps) {
  return (
    <span className={s.term} data-tip={definition} tabIndex={0}>
      {children ?? term}
      <span className={s.sr}>{` (${term}: ${definition})`}</span>
    </span>
  );
}
