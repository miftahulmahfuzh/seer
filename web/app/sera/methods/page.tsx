import { Archive, ChevronRight, ExternalLink, FlaskConical, HeartPulse, LayoutList, type LucideIcon } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { Term } from '@/components/sera/Term';
import { excessCagr } from '@/lib/sera/derive';
import { requireSera } from '@/lib/sera/gate';
import { GLOSSARY, type GlossaryKey, SOURCE_KIND_LABEL, STATUS_LABEL } from '@/lib/sera/glossary';
import { lab } from '@/lib/sera/lab';
import type { LabTrial } from '@/lib/sera/types';
import {
  count, filterRows, fixed, markLabel, marks, methodRows, parseShow, pct1, pfText, showCounts, showHref, SOURCE_ICON,
  sourceHref, type MethodRow, type Show,
} from './view';
import s from './methods.module.css';

// The layout's title template renders this as "Methods · Sera".
export const metadata: Metadata = { title: 'Methods' };

/** A glossary term: the definition comes from lib/sera/glossary (Term itself takes plain strings). */
function T({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  return <Term term={GLOSSARY[k].term} definition={GLOSSARY[k].plain}>{children}</Term>;
}

const FILTERS: [Show, LucideIcon, string][] = [
  ['all', LayoutList, 'All methods'],
  ['lab', FlaskConical, 'Lab methods only'],
  ['historical', Archive, 'Historical methods, from before the lab'],
  ['alive', HeartPulse, 'Still alive: passed, or one hurdle away'],
];

const EMPTY: Record<Show, string> = {
  all: 'The lab has no methods yet.',
  lab: 'No lab methods yet.',
  historical: 'No historical methods.',
  alive: 'Nothing is alive yet: no method has passed, and none is one hurdle away.',
};

type Search = { show?: string | string[] };

export default async function Methods({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const show = parseShow(q.show);
  await requireSera(showHref(show));
  const rows = methodRows(lab.methods, lab.trials);
  const counts = showCounts(rows);
  const shown = filterRows(rows, show);

  return (
    <>
      <PageHeader
        eyebrow="Methods"
        title="Every method tried"
        lede="Each row is one idea Sera tested on 1993–2015 data, judged by its best variant. Open a row for the full story."
        asOf={lab.asOf}
      />
      <Section
        title="The methods"
        caption="The six dots on each row are the six hurdles a method must clear before it may trade. A filled dot means cleared."
        className={s.sheet}
      >
        <div className={s.toolbar}>
          <div className="seg" role="group" aria-label="Filter methods">
            {FILTERS.map(([v, Icon, tip]) => (
              <Link key={v} href={showHref(v)} replace scroll={false} className="icon-btn"
                data-tip={tip} aria-label={tip} aria-current={show === v ? 'true' : undefined}>
                <Icon size={19} strokeWidth={show === v ? 2 : 1.5} />
              </Link>
            ))}
          </div>
          <div className={s.counts}>
            <span className="chip"><span className="num">{counts.all}</span> methods</span>
            <span className="chip"><span className="num">{counts.lab}</span> lab</span>
            <span className="chip"><span className="num">{counts.historical}</span> historical</span>
            <span className="chip"><span className="num">{counts.alive}</span> alive</span>
            <span className="chip"><span className="num">{count(lab.summary.devTrials)}</span> tries</span>
          </div>
        </div>

        {shown.length === 0 ? (
          <p className={s.empty}>{EMPTY[show]}</p>
        ) : (
          <div className={s.tableWrap}>
            <table className={s.table}>
              <thead>
                <tr>
                  <th className={s.cStatus} scope="col">Status</th>
                  <th className={s.cMethod} scope="col">Method</th>
                  <th className={s.cSource} scope="col">Source</th>
                  <th className={`${s.cCagr} ${s.r}`} scope="col"><T k="cagr">Growth a year</T> vs SPY</th>
                  <th className={`${s.cNum} ${s.r}`} scope="col"><T k="maxDrawdown">Max DD</T></th>
                  <th className={`${s.cNum} ${s.r}`} scope="col"><T k="profitFactor">PF</T></th>
                  <th className={`${s.cNum} ${s.r}`} scope="col"><T k="trades">Trades</T></th>
                  <th className={`${s.cNum} ${s.r}`} scope="col"><T k="dsr">DSR</T></th>
                  <th className={s.cDots} scope="col">Hurdles</th>
                  <th className={s.cVerdict} scope="col">Verdict</th>
                  <th className={s.cGo} aria-hidden="true" />
                </tr>
              </thead>
              <tbody>
                {shown.map(r => <Row key={r.method.id} r={r} />)}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </>
  );
}

function Row({ r }: { r: MethodRow }) {
  const m = r.method;
  const b = r.best;
  const href = sourceHref(m.sourceRef);
  const SrcIcon = SOURCE_ICON[m.sourceKind];
  const srcLabel = SOURCE_KIND_LABEL[m.sourceKind];
  const st = STATUS_LABEL[m.status];
  const excess = b ? excessCagr(b) : null;
  return (
    <tr className={s.row}>
      <td>
        <span className={`chip ${s.status}`} data-tone={st.tone} data-tip={st.meaning}>{st.label}</span>
      </td>
      <td>
        <Link href={`/sera/methods/${m.id}`} className={s.nameLink}>
          <span className={s.id}>{m.id}</span>
          <span className={s.name}>{m.name}</span>
        </Link>
        <span className={s.family}>{m.family}</span>
      </td>
      <td>
        {href ? (
          <a href={href} target="_blank" rel="noreferrer" className={s.sourceLink}
            data-tip={m.sourceRef} aria-label={`${srcLabel}: ${m.sourceRef}`}>
            <SrcIcon size={15} aria-hidden="true" />
            <span className={s.sourceText}>{srcLabel}</span>
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        ) : (
          <span className={s.source} data-tip={m.sourceRef || undefined}>
            <SrcIcon size={15} aria-hidden="true" />
            <span className={s.sourceText}>{srcLabel}</span>
          </span>
        )}
      </td>
      {b ? (
        <>
          <td className={s.r}>
            <span className={`num ${excess === null ? '' : excess >= 0 ? 'pos' : 'neg'}`}>{pct1(b.cagr)}</span>
            <span className={s.vs}> vs {pct1(b.spyTrCagr)}</span>
          </td>
          <td className={`num ${s.r}`}>{pct1(b.maxDrawdown)}</td>
          <td className={`num ${s.r}`}>{pfText(b)}</td>
          <td className={`num ${s.r}`}>{count(b.trades)}</td>
          <td className={`num ${s.r}`}>{fixed(b.dsr, 2)}</td>
          <td><Dots best={b} passed={r.passed ?? 0} /></td>
        </>
      ) : (
        <>
          <td className={`${s.untested} ${s.r}`}>Not tested yet</td>
          <td colSpan={5} />
        </>
      )}
      <td><span className={s.verdict}>{m.verdict || '—'}</span></td>
      <td className={s.go} aria-hidden="true"><ChevronRight size={18} /></td>
    </tr>
  );
}

function Dots({ best, passed }: { best: LabTrial; passed: number }) {
  const ms = marks(best);
  const missed = ms.filter(x => x.ok !== true).map(markLabel);
  const tip = missed.length ? missed.join(' · ') : 'Cleared every hurdle';
  return (
    <span className={s.dots} role="img" aria-label={`Cleared ${passed} of 6 hurdles. ${tip}`} data-tip={tip}>
      {ms.map(x => (
        <span key={x.key} className={x.ok === true ? s.dotOn : x.ok === null ? s.dotNa : s.dotOff} />
      ))}
      <span className={`num ${s.dotsN}`}>{passed}/6</span>
    </span>
  );
}
