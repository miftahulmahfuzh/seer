import type { CSSProperties, ReactNode } from 'react';
import s from './Section.module.css';

/** The Seer v2 sheet backgrounds (global .bg-* classes). */
export type SectionBg = 'sheet' | 'lav' | 'butter' | 'sky' | 'stone' | 'coral';

export type SectionProps = {
  eyebrow?: string;
  title?: string;
  /** One plain sentence: what the content shows and how to read it (plan invariant 6). May hold <Term>s. */
  caption?: ReactNode;
  /** Default 'sheet'. */
  bg?: SectionBg;
  /** Top-right of the header: a Legend, a segmented filter, an icon link. */
  aside?: ReactNode;
  /** Anchor id; also links the heading for screen readers. */
  id?: string;
  className?: string;
  children?: ReactNode;
};

/** One rounded 40px sheet: eyebrow, title, plain caption, then content. Charts inside pick up its background. */
export function Section({ eyebrow, title, caption, bg = 'sheet', aside, id, className, children }: SectionProps) {
  const titleId = id && title ? `${id}-title` : undefined;
  const style = { '--chart-halo': `var(--${bg})` } as CSSProperties;
  return (
    <section id={id} className={`sheet bg-${bg} ${s.section} ${className ?? ''}`} style={style} aria-labelledby={titleId}>
      {eyebrow || title || caption || aside ? (
        <header className={s.head}>
          <div className={s.titles}>
            {eyebrow ? <span className={`eyebrow ${s.eyebrow}`}>{eyebrow}</span> : null}
            {title ? <h2 id={titleId} className={s.title}>{title}</h2> : null}
            {caption ? <p className={s.caption}>{caption}</p> : null}
          </div>
          {aside ? <div className={s.aside}>{aside}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}

/** Desktop grid of Sections. `columns` is a grid-template-columns value; one column below 1024 px. */
export function SectionGrid({ columns, className, children }: { columns?: string; className?: string; children: ReactNode }) {
  const style = columns ? ({ '--cols': columns } as CSSProperties) : undefined;
  return (
    <div className={`${s.grid} ${className ?? ''}`} style={style}>
      {children}
    </div>
  );
}
