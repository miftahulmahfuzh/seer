import type { Metadata } from 'next';
import { SeraNav } from '@/components/sera/SeraNav';
import { requireSera } from '@/lib/sera/gate';
import s from './sera.module.css';

export const metadata: Metadata = { title: { default: 'Sera', template: '%s · Sera' } };

/** Sera, the method lab: gated to SERA_EMAIL (invariant 3), desktop shell with its own rail. */
export default async function SeraLayout({ children }: { children: React.ReactNode }) {
  await requireSera();
  return (
    <div className={s.shell}>
      <SeraNav />
      <main className={s.main}>
        <div className={s.column}>{children}</div>
      </main>
    </div>
  );
}
