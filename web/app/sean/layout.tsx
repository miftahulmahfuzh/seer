import type { Metadata } from 'next';
import { SeanNav } from '@/components/sean/SeanNav';
import { requireSean } from '@/lib/sean/gate';
import { openReminderCount } from '@/lib/sean/planData';
import s from './sean.module.css';

export const metadata: Metadata = { title: { default: 'Sean', template: '%s · Sean' } };

/**
 * Sean, the owner's real Gotrade trades: gated like Sera (plan invariant 3), its own rail.
 */
export default async function SeanLayout({ children }: { children: React.ReactNode }) {
  await requireSean();
  // Open reminders: the Plan tab's badge. openReminderCount returns 0 on any failure.
  const planOpen = await openReminderCount();
  return (
    <div className={s.shell}>
      <SeanNav planOpen={planOpen} />
      <main className={s.main}>
        <div className={s.column}>{children}</div>
      </main>
    </div>
  );
}
