import { Check, ChevronLeft, ChevronRight, X } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSera } from '@/lib/sera/gate';
import { lab } from '@/lib/sera/lab';
import { EMPTY_TEXT, pageHref, signalMap, type SignalRowView } from './view';
import s from './signals.module.css';

// The layout's title template renders this as "Signal map · Sera".
export const metadata: Metadata = { title: 'Signal map' };

type Search = { page?: string | string[] };

/**
 * The signal map: every stock-picking idea the panel has measured, ranked, in plain words.
 *
 * Paged by `?page=` rather than collapsed: a <details> remainder would still put every row in the
 * HTML, and the panel is expected to hold 1,500+ rows once Sera replays the recorded methods.
 */
export default async function SignalsPage({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const map = signalMap(lab.panel, q.page);
  await requireSera(pageHref(map.page));

  return (
    <>
      <PageHeader eyebrow="Signals" title="The signal map" lede={map.lede} asOf={lab.asOf} />
      <div className={s.page}>
        {map.total === 0 ? (
          <Section eyebrow="Signal map" title="Nothing measured yet">
            <p className={s.empty}>{EMPTY_TEXT}</p>
          </Section>
        ) : (
          <>
            <div className={s.tally}>
              <span className="chip"><span className="num">{map.total.toLocaleString('en-US')}</span>&nbsp;measured</span>
              <span className="chip"><span className="num">{map.cleared.toLocaleString('en-US')}</span>&nbsp;passed</span>
              <span className="chip"><span className="num">{map.replays.toLocaleString('en-US')}</span>&nbsp;from strategies already tested</span>
              <span className="chip"><span className="num">{map.twins.toLocaleString('en-US')}</span>&nbsp;repeat another idea’s picks</span>
            </div>

            {map.finding && (
              <Section bg="butter" eyebrow="The finding" title="Not one idea passed">
                <p className={s.finding}>{map.finding}</p>
              </Section>
            )}

            <Section
              eyebrow={`Ranking · page ${map.page} of ${map.pages}`}
              title="Every idea, best first"
              caption="Ranked by how much better the stocks each idea ranked higher did, once the usual explanations are allowed for. To pass, an idea has to beat luck given how many ideas were tried, still work after 2009, and keep its edge with the companies that later failed put back."
            >
              <ol className={s.rows}>
                {map.rows.map(r => <SignalRow key={r.key} r={r} />)}
              </ol>
              <Pager page={map.page} pages={map.pages} />
            </Section>
          </>
        )}
      </div>
    </>
  );
}

function SignalRow({ r }: { r: SignalRowView }) {
  return (
    <li className={s.row}>
      <span className={`num ${s.rank}`}>{r.rank}</span>
      <div className={s.main}>
        <div className={s.head}>
          <h3 className={s.name}>{r.name}</h3>
          <span className={`chip ${s.verdict} ${r.clears ? s.pass : s.miss}`}>
            {r.clears
              ? <Check size={15} strokeWidth={2} aria-hidden="true" />
              : <X size={15} strokeWidth={2} aria-hidden="true" />}
            {r.verdict}
          </span>
        </div>
        <p className={s.text}>{r.readings}</p>
        {r.controlled && <p className={s.sub}>{r.controlled}</p>}
        {r.why.length > 0 && (
          <ul className={s.why}>
            {r.why.map(w => <li key={w}>{w}</li>)}
          </ul>
        )}
        <div className={s.chips}>
          <span className="chip">{r.origin}</span>
          {r.twin && <span className="chip">{r.twin}</span>}
        </div>
      </div>
    </li>
  );
}

function Pager({ page, pages }: { page: number; pages: number }) {
  if (pages <= 1) return null;
  return (
    <nav className={s.pager} aria-label="Pages of the ranking">
      <span className="num">Page {page} of {pages}</span>
      {page > 1 && (
        <Link href={pageHref(page - 1)} className="icon-btn sm" aria-label="Previous page" data-tip="Previous page">
          <ChevronLeft size={18} strokeWidth={1.5} />
        </Link>
      )}
      {page < pages && (
        <Link href={pageHref(page + 1)} className="icon-btn sm" aria-label="Next page" data-tip="Next page">
          <ChevronRight size={18} strokeWidth={1.5} />
        </Link>
      )}
    </nav>
  );
}
