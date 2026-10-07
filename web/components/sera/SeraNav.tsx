'use client';

import { Eye, FlaskConical, LayoutDashboard, Lightbulb, NotebookPen, Workflow } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './SeraNav.module.css';

const TABS = [
  { href: '/sera', icon: LayoutDashboard, tip: 'Overview' },
  { href: '/sera/methods', icon: FlaskConical, tip: 'Methods' },
  { href: '/sera/journal', icon: NotebookPen, tip: 'Journal' },
  { href: '/sera/ideas', icon: Lightbulb, tip: 'Ideas' },
  { href: '/sera/how', icon: Workflow, tip: 'How it works' },
];

/** The one tab that carries an unseen badge. The other four count nothing. */
const BADGED = '/sera/journal';

/** A count fit to print: a whole number above zero, or 0, which renders no badge at all. */
const badgeCount = (n: number): number => (Number.isFinite(n) && n > 0 ? Math.floor(n) : 0);

/**
 * Sera's rail: wordmark, five icon-only section tabs, and a way back to Seer. A top bar below 1024 px.
 *
 * `journalUnseen` is the number of journal entries not yet seen, read server-side in
 * app/sera/layout.tsx. It exists so a new entry is visible from the other Sera pages, not only
 * from /sera/journal, where the seven badges already say it. Zero (or absent) means no badge —
 * unlike the Journal's own badges, which keep a muted zero pill to keep the row of seven even.
 */
export function SeraNav({ journalUnseen = 0 }: { journalUnseen?: number }) {
  const path = usePathname() ?? '';
  return (
    <aside className={s.rail}>
      <span className={s.wordmark}>
        Sera<span className={s.dot}>.</span>
      </span>
      <nav className={s.tabs} aria-label="Sera sections">
        {TABS.map(({ href, icon: Icon, tip }) => {
          const active = href === '/sera' ? path === '/sera' : path === href || path.startsWith(`${href}/`);
          const n = href === BADGED ? badgeCount(journalUnseen) : 0;
          return (
            <Link key={href} href={href} className={active ? s.active : s.tab}
              data-tip={n > 0 ? `${tip} · ${n} new` : tip}
              aria-label={n > 0 ? `${tip}, ${n} new` : tip}
              aria-current={active ? 'page' : undefined}>
              <Icon size={22} strokeWidth={active ? 1.75 : 1.5} />
              {n > 0 && <span className={s.badge} aria-hidden="true">{n > 99 ? '99+' : n}</span>}
            </Link>
          );
        })}
      </nav>
      <Link href="/" className={`icon-btn ${s.back}`} data-tip="Back to Seer" aria-label="Back to Seer">
        <Eye size={21} strokeWidth={1.5} />
      </Link>
    </aside>
  );
}
