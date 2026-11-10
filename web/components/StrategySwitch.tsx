import { ListFilter } from 'lucide-react';
import Link from 'next/link';
import type { CSSProperties } from 'react';
import { strategyIcon } from './roster';
import s from './StrategySwitch.module.css';

export const ALL = 'all';

type Props = {
  /** Roster rows in display order. */
  strategies: { id: string; name: string; icon: string }[];
  /** The selected id, or ALL when `allTip` is set and nothing is filtered. */
  current: string;
  /** Builds each link's href (keep other query params there). */
  href: (id: string) => string;
  /** Accessible name of the group. */
  label: string;
  /** When set, a leading ListFilter button with id ALL and this tooltip. */
  allTip?: string;
  /** Draw as a `.seg` pill track instead of loose wrapping circles. Wins over `fit`. */
  seg?: boolean;
  /**
   * Desktop (≥ 1024px): one row, always: one grid column per button, each at most the usual 46px,
   * and all of them shrinking together once the row is too narrow, instead of wrapping onto a
   * second line. Below 1024px it is the loose wrapping row.
   */
  fit?: boolean;
};

/**
 * Icon-only strategy switcher: one Link per roster strategy with its own Lucide icon,
 * tooltip and aria-label = its name, aria-current on the selected one.
 * Server component: `href` is a function prop.
 *
 * `fit` exists for the leaderboard's go-live checklist, a fixed 324px row on desktop. The Claude
 * twins took the roster to seven research strategies, and the seventh 46px circle wrapped onto a
 * row of its own. The roster can reach twelve, so the buttons have to give up size: the count goes
 * to CSS as `--n`, and the CSS sets the columns and the gap from it. The phone layout is left as
 * it was (the leaderboard's mobile layout is not part of the desktop revamp), so below 1024px a
 * `fit` row wraps like the default one. The other callers keep the loose wrapping row. They have
 * room, and their markup is the same as before `fit` existed.
 */
export function StrategySwitch({ strategies, current, href, label, allTip, seg, fit }: Props) {
  const items = [
    ...(allTip ? [{ id: ALL, tip: allTip, Icon: ListFilter }] : []),
    ...strategies.map(st => ({ id: st.id, tip: st.name, Icon: strategyIcon(st.icon) })),
  ];
  const fitted = fit && !seg;
  return (
    <nav className={seg ? 'seg' : fitted ? s.fit : s.group} aria-label={label}
      style={fitted ? ({ '--n': items.length } as CSSProperties) : undefined}>
      {items.map(({ id, tip, Icon }) => {
        const on = current === id;
        return (
          <Link key={id} href={href(id)} replace scroll={false} className="icon-btn md"
            data-tip={tip} aria-label={tip} aria-current={on ? 'true' : undefined}>
            <Icon size={19} strokeWidth={on ? 2 : 1.5} />
          </Link>
        );
      })}
    </nav>
  );
}
