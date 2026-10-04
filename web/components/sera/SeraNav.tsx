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

/** Sera's rail: wordmark, five icon-only section tabs, and a way back to Seer. A top bar below 1024 px. */
export function SeraNav() {
  const path = usePathname() ?? '';
  return (
    <aside className={s.rail}>
      <span className={s.wordmark}>
        Sera<span className={s.dot}>.</span>
      </span>
      <nav className={s.tabs} aria-label="Sera sections">
        {TABS.map(({ href, icon: Icon, tip }) => {
          const active = href === '/sera' ? path === '/sera' : path === href || path.startsWith(`${href}/`);
          return (
            <Link key={href} href={href} className={active ? s.active : s.tab}
              data-tip={tip} aria-label={tip} aria-current={active ? 'page' : undefined}>
              <Icon size={22} strokeWidth={active ? 1.75 : 1.5} />
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
