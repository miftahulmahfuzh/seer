import type { ReactNode } from 'react';
import s from './charts.module.css';
import { HRef, VRef } from './parts';
import { type Domain, type Format, type RefLine, type TickSpec, clamp, extent, fmtNumber, isNum, linear, resolveAxis, textWidth, truncate } from './scale';

/** One bar inside a group. */
export type BarItem = {
  /** Unique within its group (React key), e.g. 'method' / 'spy'. */
  key: string;
  /** null draws no bar ('—' when values are shown). */
  value: number | null;
  /** Overrides the signed / default colour. */
  color?: string;
  tip?: string;
  /** Printed value. Default: format(value). */
  valueText?: string;
};

/** One category: a year, a hurdle, a family. Several items side by side make a grouped bar. */
export type BarGroup = {
  id: string;
  label: string;
  items: readonly BarItem[];
  /** Makes the whole group a link. */
  href?: string;
  /** Tooltip on the category label (horizontal: defaults to the full label when it was truncated). */
  tip?: string;
};

/** The one-bar-per-category shape; turn it into groups with barGroups(). */
export type SimpleBar = {
  id: string;
  label: string;
  value: number | null;
  color?: string;
  tip?: string;
  href?: string;
  valueText?: string;
};

export function barGroups(bars: readonly SimpleBar[]): BarGroup[] {
  return bars.map(b => ({
    id: b.id,
    label: b.label,
    href: b.href,
    items: [{ key: b.id, value: b.value, color: b.color, tip: b.tip, valueText: b.valueText }],
  }));
}

export type BarChartProps = {
  groups: readonly BarGroup[];
  ariaLabel: string;
  /** 'vertical' (default): categories along x. 'horizontal': categories down the left. */
  orientation?: 'vertical' | 'horizontal';
  /** Colour bars by sign: --pos at or above zero, --neg below (unless an item sets color). */
  signed?: boolean;
  /** Colour when not signed. Default 'var(--ink)'. */
  color?: string;
  /** Value axis. Default: the values plus 0 plus refLines, widened to nice ticks. */
  domain?: Domain;
  /** Value and tick format. Default fmtNumber(0). */
  format?: Format;
  /** Target count (default 5) or explicit ticks. */
  ticks?: TickSpec;
  /** Print each bar's value. Default: true for one bar per group and at most 16 groups. */
  values?: boolean;
  /** Lines across the bars at a value (a target, SPY's figure). */
  refLines?: readonly RefLine[];
  /** Title of the value axis. */
  axisLabel?: string;
  legend?: ReactNode;
  /** viewBox width. Default 960. */
  width?: number;
  /** viewBox height. Vertical default 360. Horizontal default: fits the rows. */
  height?: number;
  /** Horizontal row height. Default 34 (one item) or 16 per item + 14. */
  rowHeight?: number;
  /** Horizontal category labels are cut to this many characters. Default 28. */
  maxLabelChars?: number;
  preserveAspectRatio?: string;
  className?: string;
};

/** Vertical or horizontal bars, single or grouped, optionally coloured by sign. */
export function BarChart(props: BarChartProps) {
  const { groups, ariaLabel, legend, className, refLines = [] } = props;
  const horizontal = props.orientation === 'horizontal';
  const W = props.width ?? 960;
  const fmt = props.format ?? fmtNumber(0);
  const n = groups.length;
  const k = Math.max(1, ...groups.map(g => g.items.length));
  const values = groups.flatMap(g => g.items.map(it => it.value)).filter(isNum);
  const axis = resolveAxis(extent(values, [0, ...refLines.map(r => r.value)]), {
    domain: props.domain,
    ticks: props.ticks,
    format: fmt,
    count: 5,
  });
  const dom = axis.domain;
  const lo = Math.min(...dom);
  const hi = Math.max(...dom);
  const ticks = axis.ticks.filter(t => t.value >= lo && t.value <= hi);
  const showValues = props.values ?? (k === 1 && n <= 16);
  const colorOf = (it: BarItem, v: number) =>
    it.color ?? (props.signed ? (v < 0 ? 'var(--neg)' : 'var(--pos)') : (props.color ?? 'var(--ink)'));
  const textOf = (it: BarItem) => it.valueText ?? (isNum(it.value) ? fmt(it.value) : '—');
  const wrap = (g: BarGroup, body: ReactNode) =>
    g.href ? (
      <a key={g.id} href={g.href} className={s.link} aria-label={g.tip ?? g.label}>{body}</a>
    ) : (
      <g key={g.id}>{body}</g>
    );

  let H: number;
  let body: ReactNode;

  if (!horizontal) {
    H = props.height ?? 360;
    const m = {
      top: showValues ? 28 : 16,
      right: 20,
      bottom: 36,
      left: 14 + Math.max(16, ...ticks.map(t => textWidth(t.label))) + (props.axisLabel ? 26 : 0),
    };
    const sv = linear(dom, [H - m.bottom, m.top]);
    const zero = sv(clamp(0, lo, hi));
    const band = (W - m.left - m.right) / Math.max(1, n);
    const inner = band * 0.72;
    const bw = inner / k;
    const every = Math.max(1, Math.ceil((Math.max(0, ...groups.map(g => textWidth(g.label))) + 10) / band));
    body = (
      <>
        {ticks.map(t => (
          <g key={`t${t.value}`}>
            <line x1={m.left} x2={W - m.right} y1={sv(t.value)} y2={sv(t.value)} className={s.grid} />
            <text x={m.left - 10} y={sv(t.value)} dy="0.35em" textAnchor="end" className={s.tick}>{t.label}</text>
          </g>
        ))}
        {groups.map((g, i) => {
          const gx = m.left + i * band + (band - inner) / 2;
          return wrap(
            g,
            <>
              {g.items.map((it, j) => {
                const x = gx + j * bw;
                if (!isNum(it.value)) {
                  return showValues ? (
                    <text key={it.key} x={x + bw / 2} y={zero - 7} textAnchor="middle" className={s.valueLabel}>—</text>
                  ) : null;
                }
                const yv = sv(clamp(it.value, lo, hi));
                const top = Math.min(yv, zero);
                const h = Math.max(1, Math.abs(yv - zero));
                return (
                  <g key={it.key}>
                    <rect x={x + 1} y={top} width={Math.max(1, bw - 2)} height={h} rx={Math.min(3, bw / 4)}
                      className={s.bar} style={{ fill: colorOf(it, it.value) }} data-tip={it.tip} />
                    {showValues ? (
                      <text x={x + bw / 2} y={it.value < 0 ? top + h + 15 : top - 7} textAnchor="middle" className={s.valueLabel}>
                        {textOf(it)}
                      </text>
                    ) : null}
                  </g>
                );
              })}
              {i % every === 0 ? (
                <text x={m.left + i * band + band / 2} y={H - m.bottom + 22} textAnchor="middle" className={s.tick} data-tip={g.tip}>
                  {g.label}
                </text>
              ) : null}
            </>,
          );
        })}
        <line x1={m.left} x2={W - m.right} y1={zero} y2={zero} className={s.axisLine} />
        {refLines.map((r, i) => <HRef key={`r${i}`} r={r} y={sv(r.value)} x1={m.left} x2={W - m.right} />)}
        {props.axisLabel ? (
          <text transform={`translate(14 ${(m.top + H - m.bottom) / 2}) rotate(-90)`} textAnchor="middle" className={s.axisTitle}>
            {props.axisLabel}
          </text>
        ) : null}
      </>
    );
  } else {
    const maxChars = props.maxLabelChars ?? 28;
    const labels = groups.map(g => truncate(g.label, maxChars));
    const rowH = props.rowHeight ?? (k > 1 ? 16 * k + 14 : 34);
    const m = {
      top: 12,
      right: showValues ? 24 + Math.max(24, ...groups.flatMap(g => g.items.map(it => textWidth(textOf(it))))) : 24,
      bottom: 34 + (props.axisLabel ? 24 : 0),
      left: 16 + Math.max(24, ...labels.map(l => textWidth(l, 14))),
    };
    H = props.height ?? m.top + Math.max(1, n) * rowH + m.bottom;
    const plotBottom = H - m.bottom;
    const sh = linear(dom, [m.left, W - m.right]);
    const zero = sh(clamp(0, lo, hi));
    body = (
      <>
        {ticks.map(t => (
          <g key={`t${t.value}`}>
            <line x1={sh(t.value)} x2={sh(t.value)} y1={m.top} y2={plotBottom} className={s.grid} />
            <text x={sh(t.value)} y={plotBottom + 22} textAnchor="middle" className={s.tick}>{t.label}</text>
          </g>
        ))}
        {groups.map((g, i) => {
          const y0 = m.top + i * rowH;
          const inner = rowH * 0.68;
          const bh = inner / k;
          return wrap(
            g,
            <>
              <text x={m.left - 12} y={y0 + rowH / 2} dy="0.35em" textAnchor="end" className={s.barLabel}
                data-tip={g.tip ?? (labels[i] !== g.label ? g.label : undefined)}>
                {labels[i]}
              </text>
              {g.items.map((it, j) => {
                const y = y0 + (rowH - inner) / 2 + j * bh;
                if (!isNum(it.value)) {
                  return showValues ? (
                    <text key={it.key} x={zero + 6} y={y + bh / 2} dy="0.35em" className={s.valueLabel}>—</text>
                  ) : null;
                }
                const xv = sh(clamp(it.value, lo, hi));
                const left = Math.min(xv, zero);
                const w = Math.max(1, Math.abs(xv - zero));
                return (
                  <g key={it.key}>
                    <rect x={left} y={y + 1} width={w} height={Math.max(1, bh - 2)} rx={Math.min(4, bh / 4)}
                      className={s.bar} style={{ fill: colorOf(it, it.value) }} data-tip={it.tip} />
                    {showValues ? (
                      <text x={it.value < 0 ? left - 6 : left + w + 6} y={y + bh / 2} dy="0.35em"
                        textAnchor={it.value < 0 ? 'end' : 'start'} className={s.valueLabel}>
                        {textOf(it)}
                      </text>
                    ) : null}
                  </g>
                );
              })}
            </>,
          );
        })}
        <line x1={zero} x2={zero} y1={m.top} y2={plotBottom} className={s.axisLine} />
        {refLines.map((r, i) => <VRef key={`r${i}`} r={r} x={sh(r.value)} y1={m.top} y2={plotBottom} right={W - m.right} />)}
        {props.axisLabel ? (
          <text x={(m.left + W - m.right) / 2} y={H - 6} textAnchor="middle" className={s.axisTitle}>{props.axisLabel}</text>
        ) : null}
      </>
    );
  }

  return (
    <figure className={`${s.figure} ${className ?? ''}`}>
      {legend ? <div className={s.legendSlot}>{legend}</div> : null}
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio={props.preserveAspectRatio ?? 'xMidYMid meet'}
        className={s.svg} role="img" aria-label={ariaLabel}>
        {body}
        {n === 0 ? <text x={W / 2} y={H / 2} textAnchor="middle" className={s.empty}>No data yet</text> : null}
      </svg>
    </figure>
  );
}
