'use client';

import { Briefcase, History, LayoutGrid, Telescope, Trophy } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './Nav.module.css';

const TABS = [
  { href: '/', icon: LayoutGrid, tip: 'Today' },
  { href: '/positions', icon: Briefcase, tip: 'Positions' },
  { href: '/leaderboard', icon: Trophy, tip: 'Leaderboard' },
  { href: '/history', icon: History, tip: 'History' },
];

/** Floating pill tab bar on mobile, vertical rail on desktop. Icon-only. `showSera` adds Sera to the desktop rail. */
export function Nav({ showSera = false }: { showSera?: boolean }) {
  const path = usePathname();
  return (
    <>
      <aside className={`${s.rail} desk-only`}>
        <span className={s.wordmark}>Seer.</span>
        <Tabs path={path} vertical />
        {showSera && (
          <Link href="/sera" className={`icon-btn ${s.sera}`} data-tip="Sera, the method lab" aria-label="Sera, the method lab">
            <Telescope size={21} strokeWidth={1.5} />
          </Link>
        )}
      </aside>
      <nav className={`${s.bar} mobile-only`} aria-label="Sections" data-tip-anchor>
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
