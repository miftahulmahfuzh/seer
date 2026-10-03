'use client';

import { Briefcase, History, LayoutGrid, Trophy } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './Nav.module.css';

const TABS = [
  { href: '/', icon: LayoutGrid, tip: 'Today' },
  { href: '/positions', icon: Briefcase, tip: 'Positions' },
  { href: '/leaderboard', icon: Trophy, tip: 'Leaderboard' },
  { href: '/history', icon: History, tip: 'History' },
];

/** Floating pill tab bar on mobile, vertical rail on desktop. Icon-only. */
export function Nav() {
  const path = usePathname();
  return (
    <>
      <aside className={`${s.rail} desk-only`}>
        <span className={s.wordmark}>Seer.</span>
        <Tabs path={path} vertical />
      </aside>
      <nav className={`${s.bar} mobile-only`} aria-label="Sections">
        <Tabs path={path} />
      </nav>
    </>
  );
}

function Tabs({ path, vertical }: { path: string; vertical?: boolean }) {
  return (
    <div className={vertical ? s.vtabs : s.tabs}>
      {TABS.map(({ href, icon: Icon, tip }) => {
        const active = href === '/' ? path === '/' : path.startsWith(href);
        return (
          <Link key={href} href={href} className={active ? s.active : s.tab}
            data-tip={tip} aria-label={tip} aria-current={active ? 'page' : undefined}>
            <Icon size={22} strokeWidth={active ? 1.75 : 1.5} />
          </Link>
        );
      })}
    </div>
  );
}
