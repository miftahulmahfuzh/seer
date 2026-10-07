import type { Metadata } from 'next';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { shortDate } from '@/lib/format';
import { gotradeList, repickConfigured } from '@/lib/sera/gotrade';
import { requireSera } from '@/lib/sera/gate';
import { GotradeEditor } from './GotradeEditor';
import { repickLine, stockCount } from './view';
import s from './gotrade.module.css';

export const metadata: Metadata = { title: 'Not on Gotrade' };

// Reads and writes Neon on every visit: never prerendered.
export const dynamic = 'force-dynamic';

export default async function GotradePage() {
  await requireSera('/sera/gotrade');
  const list = await gotradeList();
  const live = repickConfigured();

  return (
    <>
      <PageHeader
        eyebrow="Not on Gotrade"
        title="Stocks you can't buy"
        lede="Seer should only suggest stocks you can actually buy. Put a stock here when Gotrade doesn't offer it, and every paper method skips it and takes its next-best choice instead."
      />
      <div className={s.page}>
        {list === null ? (
          <Section eyebrow="On the list" title="Skipped by Seer">
            <p className={s.empty}>The list can't be read right now. Nothing has changed; try again in a moment.</p>
          </Section>
        ) : (
          <>
            <Section eyebrow={`On the list · ${stockCount(list.listed.length)}`} title="Skipped by Seer" caption={repickLine(live)}>
              <GotradeEditor listed={list.listed} />
            </Section>

            {list.back.length > 0 && (
              <Section bg="stone" eyebrow="Back on Gotrade" title="Taken off the list"
                caption="Stocks that were on the list and are on Gotrade again, most recent first. Seer can pick them again.">
                <ul className={s.history}>
                  {list.back.map(r => (
                    <li key={r.symbol} className={s.past}>
                      <span className={`num ${s.pastSymbol}`}>{r.symbol}</span>
                      {r.note && <span className={s.pastNote}>{r.note}</span>}
                      <span className={s.pastDates}>{shortDate(r.added)} to {shortDate(r.removed)}</span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}
          </>
        )}
      </div>
    </>
  );
}
