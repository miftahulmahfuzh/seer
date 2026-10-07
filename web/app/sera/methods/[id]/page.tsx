import { CalendarClock, CalendarPlus, Check, ChevronRight, CircleDashed, ExternalLink, GitFork, Hash, X } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import type { ReactNode } from 'react';
import { BarChart, type BarGroup } from '@/components/sera/charts/BarChart';
import { Legend, legendFromSeries } from '@/components/sera/charts/Legend';
import { LineChart, type LineSeries } from '@/components/sera/charts/LineChart';
import { fmtPct, fmtSignedPct } from '@/components/sera/charts/scale';
import { ScatterChart, type ScatterPoint } from '@/components/sera/charts/ScatterChart';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { Term } from '@/components/sera/Term';
import { bestVariant, CONDITION_KEYS, CONDITION_LABEL, drawdownSeries, spyForWindow, yearlyReturns } from '@/lib/sera/derive';
import { requireSera } from '@/lib/sera/gate';
import { GLOSSARY, type GlossaryKey, INSIGHT_KIND_LABEL, SOURCE_KIND_LABEL, STATUS_LABEL } from '@/lib/sera/glossary';
import { childrenOf, insightsOf, lab, methodById, trialsOf } from '@/lib/sera/lab';
import { collapseRepeatedHeadings, renderMarkdown } from '@/lib/sera/markdown';
import type { LabMethod, LabTrial } from '@/lib/sera/types';
import {
  BEST_COLOR, conditionTip, count, fixed, growthFmt, growthLines, hurdlePoints, longDate, markLabel, marks, pct1,
  pfText, signed1, SOURCE_ICON, sourceHref, SPY_COLOR, SPY_DASH, techRows, untestedNote, windowText, workedSummary,
  yearPairs, type Mark,
} from '../view';
import s from './method.module.css';

type Params = { id: string };

export function generateStaticParams(): Params[] {
  return lab.methods.map(m => ({ id: m.id }));
}

// The layout's title template appends " · Sera".
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { id } = await params;
  const m = methodById(id);
  return { title: m ? `${m.id} · ${m.name}` : 'Method' };
}

/** A glossary term: the definition comes from lib/sera/glossary (Term itself takes plain strings). */
function T({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  return <Term term={GLOSSARY[k].term} definition={GLOSSARY[k].plain}>{children}</Term>;
}

export default async function MethodPage({ params }: { params: Promise<Params> }) {
  const { id } = await params;
  await requireSera(`/sera/methods/${encodeURIComponent(id)}`);
  const m = methodById(id);
  if (!m) notFound();

  const trials = trialsOf(m.id);
  const best = bestVariant(trials);
  const parent = m.parentId ? methodById(m.parentId) : undefined;
  const children = childrenOf(m.id);
  const insights = insightsOf(m.id);
  const nAtRun = trials.length ? Math.max(...trials.map(t => t.nTrialsAtRun)) : null;
  const srcHref = sourceHref(m.sourceRef);
  const SrcIcon = SOURCE_ICON[m.sourceKind];
  const srcLabel = SOURCE_KIND_LABEL[m.sourceKind];
  const st = STATUS_LABEL[m.status];

  return (
    <>
      <PageHeader
        eyebrow={`${st.label} · ${m.family}`}
        title={`${m.id} · ${m.name}`}
        lede={m.verdict || untestedNote(m)}
        asOf={lab.asOf}
      />

      <div className={s.page}>
        <div className={s.meta}>
          <span className={`chip ${s.statusChip}`} data-tone={st.tone} data-tip={st.meaning}>{st.label}</span>
          {srcHref ? (
            <a className={`chip ${s.metaLink}`} href={srcHref} target="_blank" rel="noreferrer"
              data-tip={m.sourceRef} aria-label={`${srcLabel}: ${m.sourceRef}`}>
              <SrcIcon size={15} aria-hidden="true" />{srcLabel}<ExternalLink size={12} aria-hidden="true" />
            </a>
          ) : (
            <span className="chip" data-tip={m.sourceRef || undefined}>
              <SrcIcon size={15} aria-hidden="true" />{srcLabel}
            </span>
          )}
          {parent && (
            <Link className={`chip ${s.metaLink}`} href={`/sera/methods/${parent.id}`}
              data-tip={`A variation of ${parent.name}`} aria-label={`Parent method ${parent.id}: ${parent.name}`}>
              <GitFork size={15} aria-hidden="true" />from {parent.id}
            </Link>
          )}
          {children.map(c => (
            <Link key={c.id} className={`chip ${s.metaLink}`} href={`/sera/methods/${c.id}`}
              data-tip={c.name} aria-label={`Follow-up method ${c.id}: ${c.name}`}>
              <ChevronRight size={15} aria-hidden="true" />led to {c.id}
            </Link>
          ))}
          <span className="chip" data-tip="Written down"><CalendarPlus size={15} aria-hidden="true" />{longDate(m.created)}</span>
          <span className="chip" data-tip="Last updated"><CalendarClock size={15} aria-hidden="true" />{longDate(m.updated)}</span>
          {nAtRun !== null && (
            <span className="chip" data-tip="How many tries the lab had counted when this ran. The more tries, the higher the bar for luck.">
              <Hash size={15} aria-hidden="true" />N = {count(nAtRun)}
            </span>
          )}
        </div>

        <div className={s.twoUp}>
          <Section eyebrow="Hypothesis" title="The idea" caption="What Sera expected before running anything." className={s.textSheet}>
            <p className={s.body}>{m.hypothesis || 'No hypothesis was recorded.'}</p>
            {m.sourceRef && <p className={s.cite}>Source: {m.sourceRef}</p>}
          </Section>
          <Section eyebrow="Written down first" title="What could go wrong" caption="The likely failure, written down before the test so the result cannot be explained away afterwards." className={s.textSheet}>
            <p className={s.body}>
              {m.expectedFailure ?? (m.historical
                ? 'This method predates the lab, and the lab only started writing down the expected failure before each test later. None was recorded.'
                : 'No expected failure was written down.')}
            </p>
          </Section>
        </div>

        {best ? (
          <Tested m={m} trials={trials} best={best} />
        ) : (
          <Section eyebrow="Status" title="Not tested yet" caption="There are no charts until a test has run." className={`${s.textSheet} bg-butter`}>
            <p className={s.body}>{untestedNote(m)}</p>
            {m.blockedOn && m.status !== 'blocked-data' && <p className={s.body}>Waiting on: {m.blockedOn}</p>}
          </Section>
        )}

        <Section eyebrow="Analysis" title="Sera's analysis and opinion" caption="Sera's own reading of the result: what happened, why, and what to try next." className={s.proseSheet}>
          {m.analysis.trim() ? (
            // Escape-first rendering (lib/sera/markdown): all text is HTML-escaped before markup is added.
            // collapseRepeatedHeadings drops the doubled date heading older `lab note` runs left at
            // the top of the log; the stored analysis keeps it, being append-only.
            <div className={s.prose}
              dangerouslySetInnerHTML={{ __html: renderMarkdown(collapseRepeatedHeadings(m.analysis)) }} />
          ) : (
            <p className={s.muted}>
              {m.historical
                ? `This method came from before the lab, and its write-up lives in ${m.sourceRef || 'the project docs'}. The verdict above is the summary.`
                : 'Sera has not written an analysis for this method yet.'}
            </p>
          )}
        </Section>

        <Section eyebrow="Journal" title="Insights from this method" caption="Lessons, wishes and risks Sera noted while working on this method." className={s.textSheet}>
          {insights.length ? (
            <ul className={s.insights}>
              {insights.map(i => (
                <li key={i.id} className={s.insight}>
                  <div className={s.insightHead}>
                    <span className={`chip ${s.kindChip}`}>{INSIGHT_KIND_LABEL[i.kind].label}</span>
                    <span className={s.insightTitle}>{i.title}</span>
                    <span className={s.insightDate}>{longDate(i.added)}</span>
                  </div>
                  <div className={s.prose} dangerouslySetInnerHTML={{ __html: renderMarkdown(i.body) }} />
                </li>
              ))}
            </ul>
          ) : (
            <p className={s.muted}>No insights are linked to this method yet.</p>
          )}
        </Section>

        {trials.length > 0 && (
          <Section eyebrow="For the record" title="Technical detail" caption="Everything needed to rerun each variant exactly: its config, rules, code version and window." className={s.textSheet}>
            <div className={s.techList}>
              {trials.map(t => <Tech key={t.n} t={t} />)}
            </div>
          </Section>
        )}
      </div>
    </>
  );
}

function MarkIcon({ mark, size }: { mark: Mark; size: number }) {
  const label = markLabel(mark);
  const cls = mark.ok === true ? s.ok : mark.ok === null ? s.na : s.no;
  return (
    <span className={cls} role="img" aria-label={label} data-tip={label}>
      {mark.ok === true ? <Check size={size} /> : mark.ok === null ? <CircleDashed size={size} /> : <X size={size} />}
    </span>
  );
}

function Tested({ m, trials, best }: { m: LabMethod; trials: LabTrial[]; best: LabTrial }) {
  const gate = lab.gate;
  const worked = workedSummary(best, gate);
  const variants = trials.filter(t => t.window === best.window);
  const spy = spyForWindow(best, lab.benchmark);
  const growth = growthLines(variants, best, spy);
  const ddBest = drawdownSeries(best.curve);
  const ddSpy = drawdownSeries(spy);
  const years = yearPairs(yearlyReturns(best.curve), yearlyReturns(spy));
  const points = hurdlePoints(lab.trials, m.id);

  // Phase 3 chart-kit shapes. Dated points go in as ISO strings (date mode, year ticks).
  const ddSeries: LineSeries[] = [
    { id: best.candidateId, label: best.candidateId, points: ddBest, color: BEST_COLOR, width: 2, area: true },
    { id: 'SPY', label: 'SPY with dividends', points: ddSpy, color: SPY_COLOR, width: 1.5, dash: SPY_DASH, area: true, areaOpacity: 0.08 },
  ];
  const yearGroups: BarGroup[] = years.map(y => ({
    id: String(y.year),
    label: String(y.year),
    items: [
      { key: 'method', value: y.method, color: BEST_COLOR, tip: `${y.year} ${best.candidateId}: ${signed1(y.method)}` },
      { key: 'spy', value: y.spy, color: SPY_COLOR, tip: `${y.year} SPY: ${signed1(y.spy)}` },
    ],
  }));
  const scatter: ScatterPoint[] = points.map(p => ({
    id: p.id, x: p.x, y: p.y, tip: p.tip, href: p.own ? undefined : p.href,
    color: p.own ? BEST_COLOR : SPY_COLOR, r: p.own ? 7 : 4, ring: !p.own,
  }));

  return (
    <>
      <Section eyebrow="Verdict" title="Did it work?" caption={worked.headline} className={`${s.textSheet} bg-butter`}>
        <ul className={s.worked}>
          {worked.lines.map(l => (
            <li key={l.key} className={s.workedItem}>
              <MarkIcon mark={{ key: l.key, label: CONDITION_LABEL[l.key], ok: l.ok }} size={16} />
              <span>{l.text}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section eyebrow="Growth" title="Growth of 1"
        caption={`Each line shows what 1 dollar grew to in one variant over ${windowText(best)}. The dotted line is SPY with dividends over the same years. Higher at the right edge is better.`}
        className={s.chartSheet}>
        <LineChart
          ariaLabel={`Growth of 1 dollar for each ${m.id} variant against SPY with dividends`}
          series={growth}
          yFormat={growthFmt}
          refLines={[{ value: 1, label: 'Start' }]}
          height={360}
          legend={<Legend items={legendFromSeries(growth)} />}
        />
      </Section>

      <div className={s.twoUp}>
        <Section eyebrow="Pain" title="Drawdowns"
          caption={`How far the best variant sat below its last peak at each point, with SPY dotted. The line marks the ${pct1(gate.maxDrawdown)} limit; anything below it fails.`}
          className={s.chartSheet}>
          <LineChart
            ariaLabel={`Drawdowns of ${best.candidateId} and SPY`}
            series={ddSeries}
            refLines={[{ value: -gate.maxDrawdown, label: `Limit −${pct1(gate.maxDrawdown)}`, color: 'var(--neg)' }]}
            includeZero
            yFormat={fmtPct(0)}
            height={300}
            legend={<Legend items={legendFromSeries(ddSeries)} />}
          />
        </Section>

        <Section eyebrow="Calendar" title="Year by year"
          caption="Each pair of bars is one calendar year: the best variant, then SPY. The first and last years may be partial."
          className={s.chartSheet}>
          <BarChart
            ariaLabel={`Calendar-year returns of ${best.candidateId} and SPY`}
            groups={yearGroups}
            format={fmtSignedPct(0)}
            height={300}
            legend={<Legend items={[
              { label: best.candidateId, color: BEST_COLOR, shape: 'zone' },
              { label: 'SPY with dividends', color: SPY_COLOR, shape: 'zone' },
            ]} />}
          />
        </Section>
      </div>

      <Section eyebrow="Hurdles" title="Against the hurdles"
        caption={`Each dot is one development try by the lab. Across is its worst fall; up is how much faster it grew than SPY. This method's variants are the solid coral dots. A method must land in the shaded corner: a fall of ${pct1(gate.maxDrawdown)} or less, and growth above SPY.`}
        className={s.chartSheet}>
        <ScatterChart
          ariaLabel={`Where ${m.id}'s variants landed among all development tries`}
          points={scatter}
          regions={[{ x1: gate.maxDrawdown, y0: 0, label: 'Pass zone' }]}
          refY={[{ value: 0, label: 'SPY' }]}
          includeZeroX
          xFormat={fmtPct(0)}
          yFormat={fmtSignedPct(0)}
          xLabel="Worst fall from a peak"
          yLabel="Growth a year minus SPY's"
          height={400}
          legend={<Legend items={[
            { label: `${m.id} variants`, color: BEST_COLOR, shape: 'dot' },
            { label: 'All other tries', color: SPY_COLOR, shape: 'ring' },
            { label: 'Pass zone', color: 'var(--sky)', shape: 'zone' },
          ]} />}
        />
      </Section>

      <Section eyebrow="Variants" title="Every variant"
        caption="One row per test run. A tick means the hurdle was cleared. The best variant is highlighted."
        className={s.chartSheet}>
        <div className={s.tableWrap}>
          <table className={s.table}>
            <thead>
              <tr>
                <th scope="col">Variant</th>
                <th scope="col">Window</th>
                <th scope="col" className={s.r}><T k="cagr">Growth a year</T> vs SPY</th>
                <th scope="col" className={s.r}><T k="return">Return</T></th>
                <th scope="col" className={s.r}><T k="maxDrawdown">Max DD</T></th>
                <th scope="col" className={s.r}><T k="profitFactor">PF</T></th>
                <th scope="col" className={s.r}><T k="trades">Trades</T></th>
                <th scope="col" className={s.r}><T k="sharpe">Sharpe</T></th>
                <th scope="col" className={s.r}><T k="mar">MAR</T></th>
                <th scope="col" className={s.r}><T k="dsr">DSR</T></th>
                {CONDITION_KEYS.map(k => (
                  <th key={k} scope="col" className={s.c}>
                    <span data-tip={conditionTip(k, gate)}>{CONDITION_LABEL[k]}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {trials.map(t => (
                <tr key={t.n} className={t.n === best.n ? s.bestRow : undefined}>
                  <th scope="row" className={s.variant}>{t.candidateId}</th>
                  <td><span className={s.window} data-window={t.window}>{t.window === 'dev' ? 'Dev' : 'Test'}</span> {windowText(t)}</td>
                  <td className={s.r}>
                    <span className="num">{pct1(t.cagr)}</span>
                    <span className={s.vs}> vs {pct1(t.spyTrCagr)}</span>
                  </td>
                  <td className={`num ${s.r}`}>{signed1(t.totalReturn)}</td>
                  <td className={`num ${s.r}`}>{pct1(t.maxDrawdown)}</td>
                  <td className={`num ${s.r}`}>{pfText(t)}</td>
                  <td className={`num ${s.r}`}>{count(t.trades)}</td>
                  <td className={`num ${s.r}`}>{fixed(t.sharpe, 2)}</td>
                  <td className={`num ${s.r}`}>{fixed(t.mar, 2)}</td>
                  {/* The score at today's N, beside ticks decided at today's N. The run-date
                      pair (t.dsr at t.nTrialsAtRun) is the record and lives in Technical detail. */}
                  <td className={`num ${s.r}`}>
                    {fixed(t.dsrNow, 2)}
                    {t.dsrNow !== null && <span className={s.vs}> at N {count(gate.dsrN)}</span>}
                  </td>
                  {marks(t).map(x => (
                    <td key={x.key} className={s.c}><MarkIcon mark={x} size={14} /></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </>
  );
}

function Tech({ t }: { t: LabTrial }) {
  return (
    <details className={s.tech}>
      <summary className={s.techSummary} data-tip="Show the technical record">
        <span className={s.techChevron} aria-hidden="true"><ChevronRight size={16} /></span>
        <span className={s.techName}>{t.candidateId}</span>
        <span className={s.techSub}>#{t.n} · {t.window === 'dev' ? 'development' : 'test'} {windowText(t)} · {t.failedNow.length ? `missed ${t.failedNow.length}` : 'eligible'}</span>
      </summary>
      <div className={s.techBody}>
        <dl className={s.techGrid}>
          {techRows(t).map(([k, v]) => (
            <div key={k} className={s.techRow}>
              <dt>{k}</dt>
              <dd className="num">{v}</dd>
            </div>
          ))}
        </dl>
        <pre className={s.config}>{t.configText}</pre>
      </div>
    </details>
  );
}
