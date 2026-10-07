import type { Metadata } from 'next';
import { SeraNav } from '@/components/sera/SeraNav';
import { requireSera } from '@/lib/sera/gate';
import { lab } from '@/lib/sera/lab';
import { unseenCount } from '@/lib/sera/seen';
import s from './sera.module.css';

export const metadata: Metadata = { title: { default: 'Sera', template: '%s · Sera' } };

/**
 * Entries in the bundled snapshot the reader has not seen — the number on the rail's Journal
 * tab. 0 renders no badge at all, and so does a failed read.
 *
 * The ids come from `lab.insights`, never from journal_seen's row count and never as
 * `insights.length - seen.size`: a row may name an id that is not in this build's snapshot (the
 * table lives in Neon, the snapshot is bundled at build time), and the rail must agree with the
 * seven badges /sera/journal renders for itself. unseenCount only looks at the ids it is given,
 * so handing it lab.insights' ids is the derivation rule, enforced.
 *
 * unseenCount returns null when the read failed, which is why it is the function this layout
 * calls rather than seenInsightIds: an empty Set cannot say whether nothing is unseen or Neon is
 * down, and invariant 9 asks for no badge in the second case rather than a confident 26. The
 * try/catch is belt-and-braces -- unseenCount already swallows its own query failure -- because
 * this layout wraps every /sera page and a throw here takes the whole section down over a badge.
 */
async function journalUnseen(): Promise<number> {
  try {
    return (await unseenCount(lab.insights.map(i => i.id))) ?? 0;
  } catch {
    return 0;
  }
}

/** Sera, the method lab: gated to SERA_EMAIL (invariant 3), desktop shell with its own rail. */
export default async function SeraLayout({ children }: { children: React.ReactNode }) {
  await requireSera();
  const unseen = await journalUnseen();
  return (
    <div className={s.shell}>
      <SeraNav journalUnseen={unseen} />
      <main className={s.main}>
        <div className={s.column}>{children}</div>
      </main>
    </div>
  );
}
