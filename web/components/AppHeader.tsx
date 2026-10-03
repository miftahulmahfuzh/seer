import { LogOut } from 'lucide-react';
import { signOut } from '@/auth';
import s from './AppHeader.module.css';

type Props = {
  date: string;
  title: string;
  deskTitle?: string;
  deskAside?: React.ReactNode;
  demo?: boolean;
};

export function AppHeader({ date, title, deskTitle, deskAside, demo }: Props) {
  return (
    <header className={s.header}>
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
        <form action={async () => { 'use server'; await signOut({ redirectTo: '/signin' }); }}>
          <button type="submit" className="icon-btn" data-tip="Sign out" aria-label="Sign out">
            <LogOut size={21} strokeWidth={1.5} />
          </button>
        </form>
      </div>
    </header>
  );
}
