import type { Metadata } from 'next';
import { SeanNav } from '@/components/sean/SeanNav';
import { requireSean } from '@/lib/sean/gate';
import s from './sean.module.css';

export const metadata: Metadata = { title: { default: 'Sean', template: '%s · Sean' } };

/**
 * Sean, the owner's real Gotrade trades: gated like Sera (plan invariant 3), its own rail.
 * `planOpen` is 0 until Phase 5 reads the open reminder count here.
 */
export default async function SeanLayout({ children }: { children: React.ReactNode }) {
  await requireSean();
  return (
    <div className={s.shell}>
      <SeanNav planOpen={0} />
      <main className={s.main}>
        <div className={s.column}>{children}</div>
      </main>
    </div>
  );
}
