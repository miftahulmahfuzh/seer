import type { BarGroup } from '../../components/sera/charts/BarChart';
import type { LineSeries } from '../../components/sera/charts/LineChart';
import type { ScatterPoint, ScatterRegion } from '../../components/sera/charts/ScatterChart';
import { type Domain, type RefLine, type Tick, niceDomain } from '../../components/sera/charts/scale';
import {
  CONDITION_LABEL,
  closest,
  conditionsPassed,
  excessCagr,
  families,
  funnel,
  misses,
  progress,
} from '../../lib/sera/derive';
import type { LabInsight, LabMethod, LabSnapshot, LabTrial } from '../../lib/sera/types';

/** The six conditions every dev try is judged on (the contract's failure labels). A count, not a threshold. */
export const HURDLES = 6;

const MINUS = '−';

// ---- Colours (Phase 3 conventions: Seer v2 tokens as CSS strings) ---------------------------------

export const LAB_COLOR = 'var(--coral)';
export const HISTORICAL_COLOR = 'var(--ink-3)';
export const ELIGIBLE_COLOR = 'var(--pos)';
export const ABOVE_COLOR = 'var(--ink)';
export const HURDLE_COLOR = 'var(--ink)';
export const FAMILY_COLOR = 'var(--line-b)';
export const MAR_COLOR = 'var(--line-b)';
export const ZONE_COLOR = 'var(--sky)';

// ---- Formatting ---------------------------------------------------------------------------------

export const methodHref = (id: string): string => `/sera/methods/${encodeURIComponent(id)}`;

export const devTrials = (snap: LabSnapshot): LabTrial[] => snap.trials.filter(t => t.window === 'dev');

/** 0.1234 -> '12.3%', -0.05 -> '−5.0%', null -> '—'. */
export const pctText = (v: number | null, digits = 1): string =>
  v === null ? '—' : (v < 0 ? MINUS : '') + (Math.abs(v) * 100).toFixed(digits) + '%';

/** A return difference in percentage points: 0.012 -> '+1.2 pp', -0.03 -> '−3.0 pp'. */
export const signedPp = (v: number, digits = 1): string =>
  (v < 0 ? MINUS : '+') + (Math.abs(v) * 100).toFixed(digits) + ' pp';

/** A plain ratio (MAR, DSR, PF): 0.5557 -> '0.56', null -> '—'. */
export const ratioText = (v: number | null, digits = 2): string =>
  v === null ? '—' : (v < 0 ? MINUS : '') + Math.abs(v).toFixed(digits);

const DAY = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', year: 'numeric' });

/** '2026-10-04T14:12:19+00:00' -> 'Oct 4, 2026'. */
export const dayText = (iso: string): string => DAY.format(new Date(iso));

/** Integer ticks 0..max, for the 'hurdles cleared' axis. */
export const countTicks = (max: number): Tick[] =>
  Array.from({ length: max + 1 }, (_, i) => ({ value: i, label: String(i) }));

// ---- Shared -------------------------------------------------------------------------------------

const historicalIds = (snap: LabSnapshot): Set<string> =>
  new Set(snap.methods.filter(m => m.historical).map(m => m.id));

/** Plain names of the hurdles a try missed, in display order. */
export const missedLabels = (t: LabTrial): string[] => misses(t).map(k => CONDITION_LABEL[k]);

/** '<candidate>: CAGR x vs SPY y, max DD z, misses: …' */
export function trialTip(t: LabTrial): string {
  const m = missedLabels(t);
  return (
    `${t.candidateId}: CAGR ${pctText(t.cagr)} vs SPY ${pctText(t.spyTrCagr)}, ` +
    `max DD ${pctText(t.maxDrawdown)}, misses: ${m.length ? m.join(', ') : 'none'}`
  );
}

const newest = (xs: LabInsight[]): LabInsight | undefined =>
  [...xs].sort((a, b) => b.added.localeCompare(a.added) || b.id - a.id)[0];

const listText = (xs: string[]): string =>
  xs.length <= 1 ? (xs[0] ?? '') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`;

// ---- (1) State of the search --------------------------------------------------------------------

export type Story = {
  title: string;
  body: string; // markdown
  added: string | null;
  source: 'synthesis' | 'insight' | 'computed';
};
export type Closest = { trial: LabTrial; passed: number; misses: string[] };
export type BestBeat = { trial: LabTrial; excess: number };
export type State = {
  story: Story;
  tried: { total: number; lab: number; historical: number };
  tries: number;
  looks: number;
  eligible: number;
  closest: Closest | null;
  bestBeat: BestBeat | null;
};

export function state(snap: LabSnapshot): State {
  const gate = snap.gate;
  const dev = devTrials(snap);
  const hist = historicalIds(snap);

  const triedIds = new Set(dev.map(t => t.methodId));
  const historical = [...triedIds].filter(id => hist.has(id)).length;
  const tried = { total: triedIds.size, lab: triedIds.size - historical, historical };

  const near = closest(dev, 1)[0];
  const closestRow: Closest | null = near
    ? { trial: near, passed: conditionsPassed(near), misses: missedLabels(near) }
    : null;

  let bestBeat: BestBeat | null = null;
  for (const t of dev) {
    const ex = excessCagr(t);
    if (ex === null || ex <= 0 || t.maxDrawdown === null || t.maxDrawdown > gate.maxDrawdown) continue;
    if (!bestBeat || ex > bestBeat.excess) bestBeat = { trial: t, excess: ex };
  }

  const eligible = dev.filter(t => t.eligible).length;

  const synth = newest(snap.insights.filter(i => i.kind === 'synthesis'));
  const note = newest(snap.insights);
  const story: Story = synth
    ? { title: synth.title, body: synth.body, added: synth.added, source: 'synthesis' }
    : note
      ? { title: note.title, body: note.body, added: note.added, source: 'insight' }
      : computedStory(dev.length, tried.total, eligible, closestRow);

  return { story, tried, tries: dev.length, looks: snap.summary.testLooks, eligible, closest: closestRow, bestBeat };
}

function computedStory(tries: number, methods: number, eligible: number, near: Closest | null): Story {
  const parts = [`${tries} ${tries === 1 ? 'try' : 'tries'} across ${methods} ${methods === 1 ? 'method' : 'methods'} so far.`];
  parts.push(
    eligible > 0
      ? `${eligible} cleared every hurdle and ${eligible === 1 ? 'waits' : 'wait'} for the one look at fresh data.`
      : 'None has cleared every hurdle yet.',
  );
  if (near && near.misses.length) parts.push(`Closest: ${near.trial.candidateId}, which missed ${listText(near.misses)}.`);
  return { title: 'Where the search stands', body: parts.join(' '), added: null, source: 'computed' };
}

// ---- (2) Where every try landed -----------------------------------------------------------------

export type Landing = {
  points: ScatterPoint[];
  regions: ScatterRegion[];
  refY: RefLine[];
  /** Always reaches a little above SPY, so the pass zone shows even when nothing beats SPY yet. */
  yDomain: Domain;
  total: number;
  inZone: number;
};

export function landing(snap: LabSnapshot): Landing {
  const gate = snap.gate;
  const hist = historicalIds(snap);
  const rows = devTrials(snap).flatMap(t => {
    const ex = excessCagr(t);
    return t.maxDrawdown === null || ex === null ? [] : [{ t, dd: t.maxDrawdown, ex }];
  });

  const color = (t: LabTrial) => (t.eligible ? ELIGIBLE_COLOR : hist.has(t.methodId) ? HISTORICAL_COLOR : LAB_COLOR);
  const rank = (t: LabTrial) => (t.eligible ? 2 : hist.has(t.methodId) ? 0 : 1);
  const points: ScatterPoint[] = [...rows]
    // Draw order: historical under lab, eligible on top.
    .sort((a, b) => rank(a.t) - rank(b.t) || a.t.n - b.t.n)
    .map(({ t, dd, ex }) => ({
      id: `t${t.n}`,
      x: dd,
      y: ex,
      color: color(t),
      r: t.eligible ? 8 : 6,
      tip: trialTip(t),
      href: methodHref(t.methodId),
    }));

  const ys = rows.map(r => r.ex);
  return {
    points,
    regions: [
      {
        x1: gate.maxDrawdown,
        y0: 0,
        label: 'Pass zone',
        color: ZONE_COLOR,
        tip: `A worst fall of at most ${pctText(gate.maxDrawdown, 0)}, and growth above SPY`,
      },
    ],
    refY: [{ value: 0, label: 'SPY' }],
    yDomain: niceDomain(Math.min(0, ...ys), Math.max(0.01, ...ys)),
    total: rows.length,
    inZone: rows.filter(r => r.dd <= gate.maxDrawdown && r.ex > 0).length,
  };
}

// ---- (3) Which hurdles are hardest --------------------------------------------------------------

export type Hurdles = { groups: BarGroup[]; domain: Domain; total: number; hardest: string | null };

export function hurdles(snap: LabSnapshot): Hurdles {
  const dev = devTrials(snap);
  const rows = funnel(dev);
  const groups: BarGroup[] = rows.map(r => ({
    id: r.key,
    label: r.label,
    items: [
      {
        key: r.key,
        value: r.passing,
        color: HURDLE_COLOR,
        valueText: `${r.passing} of ${r.measured}`,
        tip:
          r.measured < r.total
            ? `${r.passing} of the ${r.measured} tries it was checked on pass “${r.label}” (${r.total - r.measured} older tries predate it)`
            : `${r.passing} of ${r.total} tries pass “${r.label}”`,
      },
    ],
  }));
  const measured = rows.filter(r => r.measured > 0);
  const hardestRow = measured.length
    ? measured.reduce((a, b) => (b.passing / b.measured < a.passing / a.measured ? b : a))
    : null;
  return { groups, domain: [0, Math.max(dev.length, 1)], total: dev.length, hardest: hardestRow ? hardestRow.label : null };
}

// ---- (4) Are we getting closer? ----------------------------------------------------------------

export type Closer = {
  passed: LineSeries[];
  passedTicks: Tick[];
  mar: LineSeries[] | null;
  latestPassed: number;
  latestMar: number | null;
};

export function closer(snap: LabSnapshot): Closer {
  const rows = progress(devTrials(snap));

  const passed: LineSeries = {
    id: 'passed',
    label: 'Most hurdles cleared so far',
    color: LAB_COLOR,
    step: true,
    points: rows.map(r => [r.n, r.bestPassed, `After try #${r.n}: best clears ${r.bestPassed} of ${HURDLES}`]),
  };

  const marRows = rows.filter((r): r is typeof r & { bestMar: number } => r.bestMar !== null);
  const mar: LineSeries[] | null = marRows.length
    ? [
        {
          id: 'mar',
          label: 'Best MAR so far',
          color: MAR_COLOR,
          step: true,
          points: marRows.map(r => [r.n, r.bestMar, `After try #${r.n}: best MAR ${ratioText(r.bestMar)}`]),
        },
      ]
    : null;

  const last = rows[rows.length - 1];
  return {
    passed: [passed],
    passedTicks: countTicks(HURDLES),
    mar,
    latestPassed: last ? last.bestPassed : 0,
    latestMar: last ? last.bestMar : null,
  };
}

// ---- (5) The luck bar ---------------------------------------------------------------------------

export type Luck = { points: ScatterPoint[]; refY: RefLine[]; yTicks: Tick[]; above: number; total: number };

export function luck(snap: LabSnapshot): Luck | null {
  const gate = snap.gate;
  const rows = devTrials(snap).filter((t): t is LabTrial & { dsr: number } => t.dsr !== null);
  if (rows.length === 0) return null;
  const points: ScatterPoint[] = rows.map(t => ({
    id: `t${t.n}`,
    x: t.nTrialsAtRun,
    y: t.dsr,
    color: t.eligible ? ELIGIBLE_COLOR : t.dsr >= gate.dsrMin ? ABOVE_COLOR : LAB_COLOR,
    r: t.eligible ? 8 : 6,
    tip: `${t.candidateId}: DSR ${ratioText(t.dsr)} at N = ${t.nTrialsAtRun}`,
    href: methodHref(t.methodId),
  }));
  return {
    points,
    refY: [{ value: gate.dsrMin, label: `Luck bar ${ratioText(gate.dsrMin)}`, color: 'var(--neg)' }],
    yTicks: [0, 0.25, 0.5, 0.75, 1].map(v => ({ value: v, label: v.toFixed(2) })),
    above: rows.filter(t => t.dsr >= gate.dsrMin).length,
    total: rows.length,
  };
}

// ---- (6) Families explored ----------------------------------------------------------------------

export type Families = { groups: BarGroup[]; domain: Domain; count: number };

export function familyBars(snap: LabSnapshot): Families {
  const rows = families(snap.methods, devTrials(snap))
    .filter(f => f.trials > 0)
    .sort((a, b) => b.trials - a.trials || a.family.localeCompare(b.family));
  const groups: BarGroup[] = rows.map(f => {
    const n = f.methodIds.length;
    return {
      id: f.family,
      label: f.family,
      items: [
        {
          key: f.family,
          value: f.trials,
          color: FAMILY_COLOR,
          valueText: String(f.trials),
          tip:
            `${f.family}: ${f.trials} ${f.trials === 1 ? 'try' : 'tries'} across ${n} ` +
            `${n === 1 ? 'method' : 'methods'}, best MAR ${ratioText(f.bestMar)}`,
        },
      ],
    };
  });
  return { groups, domain: [0, Math.max(1, ...rows.map(f => f.trials))], count: rows.length };
}

// ---- (7) Latest methods -------------------------------------------------------------------------

export type MethodCard = {
  id: string;
  name: string;
  status: LabMethod['status'];
  family: string;
  blurb: string;
  blurbIsVerdict: boolean;
  updated: string;
  href: string;
  tries: number;
  bestPassed: number | null;
};

/** Up to the first sentence of `text`, capped at `max` characters. */
const firstSentence = (text: string, max = 220): string => {
  const flat = text.replace(/\s+/g, ' ').trim();
  const end = flat.search(/[.!?](\s|$)/);
  const s = end === -1 ? flat : flat.slice(0, end + 1);
  return s.length > max ? s.slice(0, max - 1).trimEnd() + '…' : s;
};

export function latestMethods(snap: LabSnapshot, k = 6): MethodCard[] {
  const dev = devTrials(snap);
  return snap.methods
    .filter(m => !m.historical)
    .sort((a, b) => b.updated.localeCompare(a.updated) || b.id.localeCompare(a.id))
    .slice(0, k)
    .map(m => {
      const own = dev.filter(t => t.methodId === m.id);
      const verdict = m.verdict.trim();
      return {
        id: m.id,
        name: m.name,
        status: m.status,
        family: m.family,
        blurb: verdict || firstSentence(m.hypothesis),
        blurbIsVerdict: verdict !== '',
        updated: m.updated,
        href: methodHref(m.id),
        tries: own.length,
        bestPassed: own.length ? Math.max(...own.map(t => conditionsPassed(t))) : null,
      };
    });
}

// ---- All of it ----------------------------------------------------------------------------------

export type Overview = {
  state: State;
  landing: Landing;
  hurdles: Hurdles;
  closer: Closer;
  luck: Luck | null;
  families: Families;
  latest: MethodCard[];
};

export function overview(snap: LabSnapshot): Overview {
  return {
    state: state(snap),
    landing: landing(snap),
    hurdles: hurdles(snap),
    closer: closer(snap),
    luck: luck(snap),
    families: familyBars(snap),
    latest: latestMethods(snap),
  };
}
