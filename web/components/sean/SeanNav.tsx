'use client';

import { Eye, LayoutDashboard, ListChecks, ReceiptText } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './SeanNav.module.css';

const TABS = [
  { href: '/sean', icon: LayoutDashboard, tip: 'Overview' },
  { href: '/sean/trades', icon: ReceiptText, tip: 'Trades' },
  { href: '/sean/plan', icon: ListChecks, tip: 'Plan' },
];

/** The one tab that carries a count: reminders still open on the Plan. */
const BADGED = '/sean/plan';

/** A count fit to print: a whole number above zero, or 0, which renders no badge at all. */
const badgeCount = (n: number): number => (Number.isFinite(n) && n > 0 ? Math.floor(n) : 0);

/**
 * Sean's rail: wordmark, three icon-only section tabs, and a way back to Seer. A top bar below
 * 1024 px. Same build as SeraNav.
 *
 * `planOpen` is the number of buy/sell reminders still to do, read server-side in
 * app/sean/layout.tsx (Phase 5 feeds it; 0 until then). Zero means no badge.
 */
export function SeanNav({ planOpen = 0 }: { planOpen?: number }) {
  const path = usePathname() ?? '';
  return (
    <aside className={s.rail}>
      <span className={s.wordmark}>
        Sean<span className={s.dot}>.</span>
      </span>
      <nav className={s.tabs} aria-label="Sean sections">
        {TABS.map(({ href, icon: Icon, tip }) => {
          const active = href === '/sean' ? path === '/sean' : path === href || path.startsWith(`${href}/`);
          const n = href === BADGED ? badgeCount(planOpen) : 0;
          const label = n > 0 ? `${tip}, ${n} to do` : tip;
          return (
            <Link key={href} href={href} className={active ? s.active : s.tab}
              data-tip={label} aria-label={label} aria-current={active ? 'page' : undefined}>
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
