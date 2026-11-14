// Pure helpers for /sera/signals. No data access; page.tsx feeds lab.panel and the raw ?page value.
//
// Everything the owner reads on the page is written here, in plain words, so one test file can
// hold the page to its two rules: no id, digest or code ever reaches the text (CLAUDE.md
// Conventions), and the verdict is the engine's, never re-judged here. `clears` and `reasons` come
// from the engine's published verdict (lab/panel_verdict.py), which is computed at export time
// across every panel ever recorded; a page that recomputed it from the readings would disagree
// with `lab panel-map` the moment the correction moved.
import type { LabSnapshot } from '../../../lib/sera/types';

type Panel = LabSnapshot['panel'];
export type PanelSignal = Panel['signals'][number];
type StoreReading = NonNullable<PanelSignal['dev']>;
type Era = NonNullable<StoreReading['all']>;

/**
 * Rows per page. The panel can hold 1,500+ rows once Sera replays every recorded stock-signal
 * method, and /sera already renders about 4 MB of HTML (features/sera.md); fifty rows keep this
 * page a few tens of kilobytes whatever the panel grows to.
 */
export const PAGE_SIZE = 50;

const INTRO =
  'Every stock-picking idea the lab has tried, measured by one question before any portfolio is ' +
  'built: did the stocks it ranked highest beat the rest over the next month?';

/** Shown in place of the ranking when the snapshot holds no panel rows. */
export const EMPTY_TEXT =
  'The map fills in the first time Sera runs the stock-picking strategies it has already tested ' +
  'through this check, and gains a row for every new idea after that.';

/** Shown above the ranking when rows exist and none passed: the finding, not a gap. */
export const FINDING_TEXT =
  'Not one idea passed. Each one either did no better than luck would, given how many ideas were ' +
  'tried, or stopped working after 2009, or lost its edge once the companies that later failed ' +
  'were put back. That is the finding: none of these ways of picking stocks is worth building a ' +
  'portfolio on.';

const CONTROLS = 'Allowing for recent winners, company size, market swings and how jumpy a stock is';

export type SignalRowView = {
  /** React key only. Never rendered. */
  key: string;
  /** 1-based place in the whole ranking, not in the page. */
  rank: number;
  name: string;
  clears: boolean;
  verdict: string;
  /** The engine's reasons, as given, when it did not pass; empty when it passed. */
  why: string[];
  readings: string;
  controlled: string | null;
  origin: string;
  twin: string | null;
};

export type SignalMap = {
  lede: string;
  total: number;
  cleared: number;
  replays: number;
  twins: number;
  finding: string | null;
  page: number;
  pages: number;
  rows: SignalRowView[];
};

const count = (n: number): string => n.toLocaleString('en-US');

const slopeOf = (sig: PanelSignal): number | null => {
  const v = sig.dev?.all?.slope;
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
};

/**
 * Best first by the dev whole-window controlled slope, the order `lab panel-map` prints (R2.3).
 * A row with no slope sorts last; ties go by name, then id, so the order never depends on the
 * snapshot's own row order.
 */
export function rankSignals(signals: readonly PanelSignal[]): PanelSignal[] {
  return [...signals].sort((a, b) => {
    const x = slopeOf(a);
    const y = slopeOf(b);
    if (x !== y) {
      if (x === null) return 1;
      if (y === null) return -1;
      return y - x;
    }
    const byName = a.name.localeCompare(b.name, 'en');
    return byName !== 0 ? byName : a.id.localeCompare(b.id, 'en', { numeric: true });
  });
}

/**
 * The name each row is shown under. Replays of one method's several variants can share the
 * method's name; those get "(variant k of n)" in id order, so two rows with different results
 * never read as the same idea and a twin line can say which one it means — without printing the
 * id that tells them apart.
 */
export function displayNames(signals: readonly PanelSignal[]): Map<string, string> {
  const byName = new Map<string, PanelSignal[]>();
  for (const sig of signals) {
    const list = byName.get(sig.name) ?? [];
    list.push(sig);
    byName.set(sig.name, list);
  }
  const out = new Map<string, string>();
  for (const [name, list] of byName) {
    if (list.length === 1) {
      out.set(list[0].id, name);
      continue;
    }
    const ordered = [...list].sort((a, b) => a.id.localeCompare(b.id, 'en', { numeric: true }));
    ordered.forEach((sig, i) => out.set(sig.id, `${name} (variant ${i + 1} of ${ordered.length})`));
  }
  return out;
}

type Compare = { verb: 'beat' | 'trailed' | 'matched'; by: string };

/** A yearly spread as a verb and an amount; null when there is no reading. */
function compare(spread: number | null | undefined): Compare | null {
  if (typeof spread !== 'number' || !Number.isFinite(spread)) return null;
  if (Math.abs(spread) < 0.0005) return { verb: 'matched', by: '' };
  return { verb: spread > 0 ? 'beat' : 'trailed', by: ` by ${(Math.abs(spread) * 100).toFixed(1)}%` };
}

const spreadOf = (era: Era | null | undefined): number | null =>
  era && typeof era.spread === 'number' ? era.spread : null;

/**
 * The three readings the panel bar is built on, as one sentence: the whole dev window, 2009-2015
 * alone, and the survivorship store (the dead companies put back).
 */
//
// A store that is null was never measured; an era that is null on a measured store had fewer than
// twelve measured months (phase 1 leaves it out), which the page says as "not enough months to say".
export function readings(sig: PanelSignal): string {
  const all = compare(spreadOf(sig.dev?.all));
  const recent = compare(spreadOf(sig.dev?.recent));
  const dead = compare(spreadOf(sig.survivorship?.all));
  const first = all
    ? `Its top picks ${all.verb} the average stock it could have picked${all.by}${all.by ? ' a year' : ''}`
    : sig.dev
      ? 'Over the whole period there are not enough months to say how its top picks did'
      : 'Its top picks have not been measured yet';
  const second = recent
    ? `since 2009 they ${recent.verb} it${recent.by}`
    : sig.dev
      ? 'since 2009 there are not enough months to say'
      : 'since 2009 it has not been measured yet';
  const third = dead
    ? `with the companies that later failed put back, they ${dead.verb} it${dead.by}`
    : sig.survivorship
      ? 'with the companies that later failed put back, there are not enough months to say'
      : 'with the companies that later failed put back, it has not been measured yet';
  return `${first}; ${second}; ${third}.`;
}

/**
 * The controlled slope, by its sign only: its size is in units the owner has no use for. The slope
 * is a MONTHLY figure (phase 1) while `spread` is yearly; if a yearly slope is ever printed it is
 * `slope * 12`, and the two are never printed as one unit.
 */
export function controlled(sig: PanelSignal): string | null {
  const slope = slopeOf(sig);
  if (slope === null) return null;
  return slope > 0
    ? `${CONTROLS}, the stocks it ranked higher still did better.`
    : `${CONTROLS}, the stocks it ranked higher did no better.`;
}

/** `?page=` as a page number in 1..pages; anything else is page 1, anything past the end the last page. */
export function parsePage(raw: string | string[] | undefined, pages: number): number {
  const v = Array.isArray(raw) ? raw[0] : raw;
  const n = Number(v);
  if (!Number.isInteger(n) || n < 1) return 1;
  return Math.min(n, Math.max(1, pages));
}

export const pageHref = (page: number): string => (page <= 1 ? '/sera/signals' : `/sera/signals?page=${page}`);

function rowView(sig: PanelSignal, rank: number, names: Map<string, string>): SignalRowView {
  return {
    key: sig.id,
    rank,
    name: names.get(sig.id) ?? sig.name,
    clears: sig.clears,
    verdict: sig.clears ? 'Passed the screen' : 'Did not pass',
    why: sig.clears ? [] : [...sig.reasons],
    readings: readings(sig),
    controlled: controlled(sig),
    origin: sig.kind === 'replay' ? 'From a strategy already tested' : 'Tested as a signal first',
    twin: sig.twinOf ? `The same picks as ${names.get(sig.twinOf) ?? 'an earlier idea'}` : null,
  };
}

/** Everything /sera/signals renders for one page of the ranking. */
export function signalMap(panel: Panel, rawPage: string | string[] | undefined): SignalMap {
  const signals = panel.signals;
  const total = signals.length;
  const cleared = signals.filter(sig => sig.clears).length;
  const replays = signals.filter(sig => sig.kind === 'replay').length;
  const twins = signals.filter(sig => sig.twinOf !== null).length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const page = parsePage(rawPage, pages);
  const names = displayNames(signals);
  const first = (page - 1) * PAGE_SIZE;
  const rows = rankSignals(signals)
    .slice(first, first + PAGE_SIZE)
    .map((sig, i) => rowView(sig, first + i + 1, names));
  const tally =
    total === 0
      ? 'No idea has been measured yet.'
      : `${count(total)} ${total === 1 ? 'idea' : 'ideas'} measured; ${cleared === 0 ? 'none' : count(cleared)} passed.`;
  return {
    lede: `${INTRO} ${tally}`,
    total,
    cleared,
    replays,
    twins,
    finding: total > 0 && cleared === 0 ? FINDING_TEXT : null,
    page,
    pages,
    rows,
  };
}
