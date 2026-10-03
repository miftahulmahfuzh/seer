import { redirect } from 'next/navigation';
import { currentUser } from '@/auth';
import { Nav } from '@/components/Nav';
import s from './shell.module.css';

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  if (!(await currentUser())) redirect('/signin');
  return (
    <div className={s.shell}>
      <Nav />
      <main className={s.main}>{children}</main>
    </div>
  );
}
