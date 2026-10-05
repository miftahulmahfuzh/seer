import { ArrowUpRight } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { BarChart } from '@/components/sera/charts/BarChart';
import { Legend } from '@/components/sera/charts/Legend';
import { LineChart } from '@/components/sera/charts/LineChart';
import { fmtNumber, fmtPct, fmtSignedPct, resolveAxis } from '@/components/sera/charts/scale';
import { ScatterChart } from '@/components/sera/charts/ScatterChart';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { Stat } from '@/components/sera/Stat';
import { Term } from '@/components/sera/Term';
import { requireSera } from '@/lib/sera/gate';
import { GLOSSARY, type GlossaryKey, STATUS_LABEL } from '@/lib/sera/glossary';
import { lab } from '@/lib/sera/lab';
import { renderMarkdown } from '@/lib/sera/markdown';
import {
  ABOVE_COLOR,
  dayText,
  ELIGIBLE_COLOR,
  type Families,
  HISTORICAL_COLOR,
  HURDLES,
  LAB_COLOR,
  overview,
  pctText,
  ratioText,
  signedPp,
  ZONE_COLOR,
} from './overview';
import s from './overview.module.css';

export const metadata: Metadata = { title: 'Overview' };

const year = (ymd: string) => ymd.slice(0, 4);
const tryNumber = (v: number) => `#${v}`;

/** A glossary term: the definition comes from lib/sera/glossary (Term itself takes plain strings). */
function T({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  return (
    <Term term={GLOSSARY[k].term} definition={GLOSSARY[k].plain}>
      {children}
    </Term>
  );
}

export default async function SeraOverview() {
  await requireSera('/sera');
  const v = overview(lab);
  const g = lab.gate;
  const dd = pctText(g.maxDrawdown, 0);
  const dev = `${year(g.devStart)}–${year(g.devEnd)}`;
  const test = `${year(g.testStart)}–today`;
  const { state: st, landing: ld, hurdles: hu, closer: cl, luck: lk, families: fa, latest } = v;

  const storyFrom = st.story.source === 'synthesis' ? 'Latest batch summary' : 'Summary from the numbers';

  return (
    <>
      <PageHeader
        eyebrow="Sera · the method lab"
        title="Overview"
        lede={`Where the search for a strategy that beats SPY with a shallow fall stands, and how every try on ${dev} has gone.`}
        asOf={lab.asOf}
      />

      <div className={s.grid}>
        {/* (1) State of the search */}
        <Section
          className={s.state}
          eyebrow="State of the search"
          title={st.story.title}
          caption={`The latest read on the search, then the numbers behind it. A try is one version of a method run once on ${dev}.`}
        >
          <div className={s.stateBody}>
            <article className={s.story}>
              <p className={s.storyMeta}>
                {storyFrom}
                {st.story.added ? ` · ${dayText(st.story.added)}` : ''}
              </p>
              <div className={s.prose} dangerouslySetInnerHTML={{ __html: renderMarkdown(st.story.body) }} />
            </article>

            <div className={s.stats}>
              <Stat
                label="Methods tried"
                value={String(st.tried.total)}
                sub={`${st.tried.lab} from the lab · ${st.tried.historical} from before it`}
              />
              <Stat
                label={
                  <>
                    Tries (<T k="tries">N</T>)
                  </>
                }
                value={String(st.tries)}
                sub="Every try raises the bar for luck"
              />
              <Stat
                label={
                  <>
                    <T k="testWindow">Test-window</T> looks used
                  </>
                }
                value={String(st.looks)}
                sub={st.looks === 0 ? `The ${test} data is still untouched` : `Each look at ${test} is spent for good`}
              />
              <Stat
                label="Closest result"
                value={st.closest ? `${st.closest.passed} of ${HURDLES}` : '—'}
                sub={
                  st.closest ? (
                    <>
                      {st.closest.trial.candidateId}, <T k="mar">MAR</T> {ratioText(st.closest.trial.mar)}
                      {st.closest.misses.length ? ` · missed ${st.closest.misses.join(', ')}` : ' · missed nothing'}
                    </>
                  ) : (
                    'No tries yet'
                  )
                }
              />
              <Stat
                label={`Best beat with a fall ≤ ${dd}`}
                value={st.bestBeat ? signedPp(st.bestBeat.excess) : 'none yet'}
                tone={st.bestBeat ? 'pos' : undefined}
                sub={
                  st.bestBeat
                    ? `${st.bestBeat.trial.candidateId} · per year above SPY, max fall ${pctText(st.bestBeat.trial.maxDrawdown)}`
                    : `Nothing has beaten SPY while keeping its worst fall under ${dd}`
                }
              />
            </div>
          </div>
        </Section>

        {/* (2) Where every try landed */}
        <Section
          className={s.landing}
          eyebrow="Where every try landed"
          title={`${ld.inZone} of ${ld.total} in the pass zone`}
          caption={
            <>
              Each dot is one try: further right means a deeper worst fall (<T k="maxDrawdown">max drawdown</T>),
              higher means it grew faster per year (<T k="cagr">CAGR</T>) than{' '}
              <T k="spyTr">SPY with dividends</T>. Only the shaded corner, a fall of at most {dd} and above SPY, can
              pass.
            </>
          }
        >
          <ScatterChart
            ariaLabel={`Scatter of ${ld.total} tries: max drawdown against growth above SPY, with the pass zone shaded`}
            points={ld.points}
            regions={ld.regions}
            refY={ld.refY}
            yDomain={ld.yDomain}
            includeZeroX
            xFormat={fmtPct(0)}
            yFormat={fmtSignedPct(0)}
            xLabel="Worst fall from a peak"
            yLabel="Growth a year minus SPY"
            height={400}
            legend={
              <Legend
                items={[
                  { label: 'Lab tries', color: LAB_COLOR, shape: 'dot' },
                  { label: 'Tries from before the lab', color: HISTORICAL_COLOR, shape: 'dot' },
                  { label: 'Cleared every hurdle', color: ELIGIBLE_COLOR, shape: 'dot' },
                  { label: 'Pass zone', color: ZONE_COLOR, shape: 'zone' },
                ]}
              />
            }
          />
        </Section>

        {/* (3) Which hurdles are hardest */}
        <Section
          className={s.hurdles}
          eyebrow="Which hurdles are hardest"
          title={hu.hardest ? `Hardest: ${hu.hardest}` : 'No tries yet'}
          caption={
            <>
              Each bar counts how many of the {hu.total} tries cleared that one hurdle, among them the{' '}
              <T k="profitFactor">profit factor</T> and the <T k="dsr">luck check</T>. The shortest bar is the wall.
            </>
          }
        >
          <BarChart
            ariaLabel={`Tries passing each of the ${HURDLES} hurdles`}
            groups={hu.groups}
            orientation="horizontal"
            domain={hu.domain}
            format={fmtNumber(0)}
            width={560}
          />
        </Section>

        {/* (4) Are we getting closer? */}
        <Section
          className={s.closer}
          eyebrow="Are we getting closer?"
          title={`Best so far: ${cl.latestPassed} of ${HURDLES} hurdles`}
          caption="Each line only rises: it shows the best result found up to that try, so a flat stretch means no new ground."
        >
          <div className={s.twin}>
            <div className={s.mini}>
              <p className={s.miniLabel}>Most hurdles cleared so far</p>
              <LineChart
                ariaLabel="Most hurdles cleared by any try so far, by try number"
                series={cl.passed}
                x="number"
                xFormat={tryNumber}
                yDomain={[0, HURDLES]}
                yTicks={cl.passedTicks}
                xLabel="Try number"
                height={220}
              />
            </div>
            <div className={s.mini}>
              <p className={s.miniLabel}>Best MAR so far (growth per unit of worst fall)</p>
              {cl.mar ? (
                <LineChart
                  ariaLabel="Best MAR of any try so far, by try number"
                  series={cl.mar}
                  x="number"
                  xFormat={tryNumber}
                  yFormat={fmtNumber(1)}
                  includeZero
                  xLabel="Try number"
                  height={220}
                />
              ) : (
                <p className={s.empty}>No try has a MAR yet.</p>
              )}
            </div>
          </div>
        </Section>

        {/* (5) The luck bar */}
        <Section
          className={s.luck}
          eyebrow="The luck bar"
          title={lk ? `${lk.above} of ${lk.total} cleared the luck bar` : 'No luck scores yet'}
          caption={`The more tries we run, the likelier one looks good by chance, so each try's luck score is judged against everything tried before it and must reach ${ratioText(g.dsrMin)}.`}
        >
          {lk ? (
            <ScatterChart
              ariaLabel={`Luck score of ${lk.total} tries against the number of tries counted, with the ${ratioText(g.dsrMin)} line`}
              points={lk.points}
              refY={lk.refY}
              yDomain={[0, 1]}
              yTicks={lk.yTicks}
              includeZeroX
              xFormat={fmtNumber(0)}
              xLabel="Tries counted when it ran (N)"
              yLabel="Luck score (DSR)"
              height={300}
              legend={
                <Legend
                  items={[
                    { label: 'Below the bar', color: LAB_COLOR, shape: 'dot' },
                    { label: 'Above the bar', color: ABOVE_COLOR, shape: 'dot' },
                    { label: 'Cleared every hurdle', color: ELIGIBLE_COLOR, shape: 'dot' },
                  ]}
                />
              }
            />
          ) : (
            <p className={s.empty}>Luck scores start with the lab&apos;s own tries; the older ones were run before it existed.</p>
          )}
        </Section>

        {/* (6) Families explored */}
        <Section
          className={s.families}
          eyebrow="Families explored"
          title={`${fa.count} ${fa.count === 1 ? 'family' : 'families'}`}
          caption="Tries per family of ideas; hover a bar for its best MAR. A long bar with a weak best means the family has been squeezed hard."
        >
          <FamilyBars families={fa} />
        </Section>

        {/* (7) Latest methods */}
        <Section
          className={s.latest}
          eyebrow="Latest methods"
          title="What the lab touched last"
          caption="The six lab methods changed most recently, with the lab's one-line verdict, or the idea itself if it has not run yet."
        >
          {latest.length ? (
            <ul className={s.cards}>
              {latest.map(m => (
                <li key={m.id} className={s.card}>
                  <div className={s.cardHead}>
                    <span className={`chip ${s.status}`} data-status={m.status} data-tip={STATUS_LABEL[m.status].meaning}>
                      {STATUS_LABEL[m.status].label}
                    </span>
                    <span className={s.cardId}>{m.id}</span>
                    <Link
                      href={m.href}
                      className={`icon-btn sm soft ${s.cardLink}`}
                      aria-label={`Open ${m.name}`}
                      data-tip={`Open ${m.id}`}
                    >
                      <ArrowUpRight size={20} strokeWidth={1.75} />
                    </Link>
                  </div>
                  <p className={s.cardName}>{m.name}</p>
                  <p className={m.blurbIsVerdict ? s.cardVerdict : s.cardIdea}>{m.blurb}</p>
                  <p className={s.cardMeta}>
                    {m.family} · {m.tries} {m.tries === 1 ? 'try' : 'tries'}
                    {m.bestPassed !== null ? ` · best ${m.bestPassed} of ${HURDLES}` : ''} · {dayText(m.updated)}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className={s.empty}>No lab methods yet.</p>
          )}
        </Section>
      </div>
    </>
  );
}

/**
 * Tries per family as HTML rows, not an SVG: the rows stretch to fill whatever height the sheet gets
 * next to Latest methods, and the short (7-character) labels keep every bar starting at the same x.
 */
function FamilyBars({ families }: { families: Families }) {
  if (!families.groups.length) return <p className={s.empty}>No family has a dev try yet.</p>;
  const fmt = fmtNumber(0);
  const { domain, ticks } = resolveAxis(families.domain, { domain: families.domain, format: fmt, count: 4 });
  const hi = Math.max(1, domain[1]);
  const pct = (v: number) => `${(Math.min(v, hi) / hi) * 100}%`;
  return (
    <div className={s.famChart} role="img" aria-label="Tries per method family">
      <ul className={s.famRows}>
        {families.groups.map(g => {
          const it = g.items[0];
          const v = it?.value ?? 0;
          return (
            <li key={g.id} className={s.famRow}>
              <span className={s.famLabel} data-tip={g.tip}>{g.label}</span>
              <span className={s.famTrack}>
                {ticks.map(t => <span key={t.value} className={s.famGrid} style={{ left: pct(t.value) }} />)}
                <span className={s.famBar} style={{ width: pct(v), background: it?.color }} data-tip={it?.tip} />
                <span className={s.famValue} style={{ left: pct(v) }}>{it?.valueText ?? fmt(v)}</span>
              </span>
            </li>
          );
        })}
      </ul>
      <div className={s.famAxis} aria-hidden>
        <span />
        <span className={s.famTicks}>
          {ticks.map(t => <span key={t.value} className={s.famTick} style={{ left: pct(t.value) }}>{t.label}</span>)}
        </span>
      </div>
    </div>
  );
}
