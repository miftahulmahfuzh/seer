import { LogOut, Wallet } from 'lucide-react';
import Link from 'next/link';
import { currentUser, signOut } from '@/auth';
import { openReminderCount } from '@/lib/sean/planData';
import { isSeraUser } from '@/lib/sera/access';
import s from './AppHeader.module.css';

type Props = {
  date: string;
  title: string;
  deskTitle?: string;
  deskAside?: React.ReactNode;
  demo?: boolean;
};

const SEAN_TIP = 'Sean, your real trades';

/**
 * The page header of every Seer (app) page. On a phone it also carries the owner's way into Sean
 * (his real Gotrade trades, whose screenshots live on that phone): the mobile tab bar has no room
 * for it, and on desktop the rail's own Sean button does the job.
 */
export async function AppHeader({ date, title, deskTitle, deskAside, demo }: Props) {
  // Sean's gate (plan invariant 3): the same owner check as the rail button in (app)/layout.tsx.
  const owner = isSeraUser((await currentUser())?.email);
  // Sean's open plan reminders: the same coral dot as the rail's. Owner only; 0 on any failure.
  const open = owner ? await openReminderCount() : 0;
  const seanTip = open > 0 ? `${SEAN_TIP} · ${open} to do` : SEAN_TIP;
  return (
    <header className={s.header}>
      <span className={`${s.eye} mobile-only`} aria-hidden="true" />
      <div className={s.titles}>
        <span className={s.date}>
          {date}
          {demo && <span className={s.demo} data-tip="Sample data until the engine runs. Do not trade it.">Demo data</span>}
        </span>
        <h1 className={s.title}>
          <span className="mobile-only">{title}</span>
          <span className="desk-only">{deskTitle ?? title}</span>
        </h1>
      </div>
      <div className={s.aside}>
        {deskAside && <span className="desk-only">{deskAside}</span>}
        {owner && (
          <Link href="/sean" className={`icon-btn mobile-only ${s.sean}`} data-tip={seanTip} aria-label={seanTip}>
            <Wallet size={21} strokeWidth={1.5} />
            {open > 0 && <span className={s.seanDot} aria-hidden="true" />}
          </Link>
        )}
        <form action={async () => { 'use server'; await signOut({ redirectTo: '/signin' }); }}>
          <button type="submit" className="icon-btn" data-tip="Sign out" aria-label="Sign out">
            <LogOut size={21} strokeWidth={1.5} />
          </button>
        </form>
      </div>
    </header>
  );
}
