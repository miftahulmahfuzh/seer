'use client';

import { Ban, Eye, FlaskConical, LayoutDashboard, Lightbulb, NotebookPen, Workflow } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import s from './SeraNav.module.css';

const TABS = [
  { href: '/sera', icon: LayoutDashboard, tip: 'Overview' },
  { href: '/sera/methods', icon: FlaskConical, tip: 'Methods' },
  { href: '/sera/journal', icon: NotebookPen, tip: 'Journal' },
  { href: '/sera/ideas', icon: Lightbulb, tip: 'Ideas' },
  { href: '/sera/gotrade', icon: Ban, tip: 'Not on Gotrade' },
  { href: '/sera/how', icon: Workflow, tip: 'How it works' },
];

/** The one tab that carries an unseen badge. The others count nothing. */
const BADGED = '/sera/journal';

/** A count fit to print: a whole number above zero, or 0, which renders no badge at all. */
const badgeCount = (n: number): number => (Number.isFinite(n) && n > 0 ? Math.floor(n) : 0);

/** Inside the lab. PageHeader is shared with /sean, which has its own way home and must not grow a second. */
const inSera = (path: string): boolean => path === '/sera' || path.startsWith('/sera/');

/**
 * Sera's navigation, in two shapes, the same two Seer's own Nav ships (components/Nav.tsx):
 * a vertical rail on a desk, and a floating pill bar at the bottom of a phone. The 1024 px switch
 * is globals.css's `.desk-only` / `.mobile-only`, not a media query here — one switch for the
 * whole app, so the nav can never disagree with the stylesheets about where the break is.
 *
 * The phone bar carries the six section tabs and nothing else. It has no wordmark because Seer's
 * bar has none either and because PageHeader already prints "Sera · the method lab" as the eyebrow
 * at the top of every page; dropping it is what leaves room for all six tabs at the rail's full
 * 52 px size (6 × 52 + 5 × 4 gap + 2 × 8 padding = 348 px, which clears the 390 px floor with
 * 21 px of gutter either side). The way back to Seer moved out of the bar for the same reason and
 * now sits beside sign-out in PageHeader — see SeraBackLink below.
 *
 * `journalUnseen` is the number of journal entries not yet seen, read server-side in
 * app/sera/layout.tsx. It exists so a new entry is visible from the other Sera pages, not only
 * from /sera/journal, where the seven badges already say it. Zero (or absent) means no badge --
 * unlike the Journal's own badges, which keep a muted zero pill to keep the row of seven even.
 */
export function SeraNav({ journalUnseen = 0 }: { journalUnseen?: number }) {
  const path = usePathname() ?? '';
  return (
    <>
      <aside className={`${s.rail} desk-only`}>
        <span className={s.wordmark}>
          Sera<span className={s.dot}>.</span>
        </span>
        <nav className={s.tabs} aria-label="Sera sections">
          <Tabs path={path} unseen={journalUnseen} />
        </nav>
        <Link href="/" className={`icon-btn ${s.back}`} data-tip="Back to Seer" aria-label="Back to Seer">
          <Eye size={21} strokeWidth={1.5} />
        </Link>
      </aside>
      {/* data-tip-anchor: tooltip.ts lifts a caption clear of the whole bar rather than one 52 px
          tab, which is what stops a long-press caption landing on top of its neighbours. */}
      <nav className={`${s.bar} mobile-only`} aria-label="Sera sections" data-tip-anchor>
        <div className={s.barTabs}>
          <Tabs path={path} unseen={journalUnseen} />
        </div>
      </nav>
    </>
  );
}

/**
 * The six tabs themselves, rendered into whichever container asked for them. One definition, so a
 * tooltip, an aria-label or the Journal badge cannot end up right in the rail and wrong in the bar.
 */
function Tabs({ path, unseen }: { path: string; unseen: number }) {
  return (
    <>
      {TABS.map(({ href, icon: Icon, tip }) => {
        const active = href === '/sera' ? path === '/sera' : path === href || path.startsWith(`${href}/`);
        const n = href === BADGED ? badgeCount(unseen) : 0;
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
    </>
  );
}

/**
 * The way back to Seer on a phone. The bar below 1024 px is six section tabs and no more, so this
 * leaves-the-area control goes where the other one already is: beside sign-out in PageHeader's
 * aside. The desktop rail keeps its own `.back` and never renders this.
 *
 * It is a client component on purpose. PageHeader is a server component (it holds the sign-out
 * server action) and is shared with /sean, which reaches home through Seer's own tab bar and must
 * not grow a second route out; a server component cannot read the pathname, so the route test lives
 * here. Rendered outside /sera it is nothing at all.
 */
export function SeraBackLink() {
  const path = usePathname() ?? '';
  if (!inSera(path)) return null;
  return (
    <Link href="/" className="icon-btn mobile-only" data-tip="Back to Seer" aria-label="Back to Seer">
      <Eye size={21} strokeWidth={1.5} />
    </Link>
  );
}
