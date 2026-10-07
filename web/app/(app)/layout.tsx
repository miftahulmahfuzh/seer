import { redirect } from 'next/navigation';
import { currentUser } from '@/auth';
import { Nav } from '@/components/Nav';
import { openReminderCount } from '@/lib/sean/planData';
import { isSeraUser } from '@/lib/sera/access';
import s from './shell.module.css';

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await currentUser();
  if (!user) redirect('/signin');
  // Sean (the owner's real Gotrade trades) and Sera (the lab) share one gate: the owner account.
  const owner = isSeraUser(user.email);
  // Sean's open plan reminders (coral dot on the rail). Owner only; 0 on any failure.
  const seanOpen = owner ? await openReminderCount() : 0;
  return (
    <div className={s.shell}>
      <Nav showSera={owner} showSean={owner} seanOpen={seanOpen} />
      <main className={s.main}>{children}</main>
    </div>
  );
}
