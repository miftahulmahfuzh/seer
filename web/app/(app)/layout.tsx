import { redirect } from 'next/navigation';
import { currentUser } from '@/auth';
import { Nav } from '@/components/Nav';
import { isSeraUser } from '@/lib/sera/access';
import s from './shell.module.css';

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await currentUser();
  if (!user) redirect('/signin');
  // Sean (the owner's real Gotrade trades) and Sera (the lab) share one gate: the owner account.
  const owner = isSeraUser(user.email);
  return (
    <div className={s.shell}>
      <Nav showSera={owner} showSean={owner} />
      <main className={s.main}>{children}</main>
    </div>
  );
}
