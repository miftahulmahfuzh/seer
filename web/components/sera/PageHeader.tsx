import { CalendarClock, LogOut } from 'lucide-react';
import type { ReactNode } from 'react';
import { signOut } from '@/auth';
import s from './PageHeader.module.css';

export type PageHeaderProps = {
  eyebrow: string;
  title: string;
  /** One or two plain sentences under the title. */
  lede?: ReactNode;
  /** The snapshot's asOf (ISO date or timestamp); shown as 'As of Oct 4, 2026'. */
  asOf?: string;
  /** Extra controls left of the as-of pill (icon-only). */
  aside?: ReactNode;
};

const DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' });

/** '2026-10-04T13:05:00+07:00' or '2026-10-04' -> 'Oct 4, 2026': the calendar date as written. */
function asOfLabel(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : DAY.format(d);
}

/** Top of every Sera page: eyebrow, big title, plain lede; as-of date and sign-out on the right. */
export function PageHeader({ eyebrow, title, lede, asOf, aside }: PageHeaderProps) {
  return (
    <header className={s.header}>
      <div className={s.titles}>
        <span className={`eyebrow ${s.eyebrow}`}>{eyebrow}</span>
        <h1 className={s.title}>{title}</h1>
        {lede ? <p className={s.lede}>{lede}</p> : null}
      </div>
      <div className={s.aside}>
        {aside}
        {asOf ? (
          <span className={`pill-outline num ${s.asOf}`} data-tip="When the lab record shown here was last written">
            <CalendarClock size={17} strokeWidth={1.5} aria-hidden="true" />
            As of {asOfLabel(asOf)}
          </span>
        ) : null}
        <form action={async () => { 'use server'; await signOut({ redirectTo: '/signin?next=%2Fsera' }); }}>
          <button type="submit" className="icon-btn" data-tip="Sign out" aria-label="Sign out">
            <LogOut size={21} strokeWidth={1.5} />
          </button>
        </form>
      </div>
    </header>
  );
}
