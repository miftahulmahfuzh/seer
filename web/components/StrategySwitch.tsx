import { ListFilter } from 'lucide-react';
import Link from 'next/link';
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
};

/**
 * Icon-only strategy switcher: one Link per roster strategy with its own Lucide icon,
 * tooltip and aria-label = its name, aria-current on the selected one.
 * Server component: `href` is a function prop.
 */
export function StrategySwitch({ strategies, current, href, label, allTip }: Props) {
  const items = [
    ...(allTip ? [{ id: ALL, tip: allTip, Icon: ListFilter }] : []),
    ...strategies.map(st => ({ id: st.id, tip: st.name, Icon: strategyIcon(st.icon) })),
  ];
  return (
    <nav className={s.group} aria-label={label}>
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
