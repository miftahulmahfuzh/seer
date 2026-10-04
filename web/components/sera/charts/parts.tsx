import s from './charts.module.css';
import { type RefLine, textWidth } from './scale';

/** A horizontal reference line across the plot, label at its right end. */
export function HRef({ r, y, x1, x2 }: { r: RefLine; y: number; x1: number; x2: number }) {
  const color = r.color ?? 'var(--ink-2)';
  return (
    <g>
      <line x1={x1} x2={x2} y1={y} y2={y} style={{ stroke: color }} strokeWidth={1.25} strokeDasharray={r.dash ?? '6 5'} />
      <line x1={x1} x2={x2} y1={y} y2={y} className={s.hitLine} data-tip={r.tip ?? r.label} />
      {r.label ? (
        <text x={x2 - 4} y={y - 7} textAnchor="end" className={s.refLabel} style={{ fill: color }}>
          {r.label}
        </text>
      ) : null}
    </g>
  );
}

/** A vertical reference line, label at its top; the label flips left when it would cross `right`. */
export function VRef({ r, x, y1, y2, right }: { r: RefLine; x: number; y1: number; y2: number; right: number }) {
  const color = r.color ?? 'var(--ink-2)';
  const flip = r.label ? x + 7 + textWidth(r.label, 12.5) > right : false;
  return (
    <g>
      <line x1={x} x2={x} y1={y1} y2={y2} style={{ stroke: color }} strokeWidth={1.25} strokeDasharray={r.dash ?? '6 5'} />
      <line x1={x} x2={x} y1={y1} y2={y2} className={s.hitLine} data-tip={r.tip ?? r.label} />
      {r.label ? (
        <text x={flip ? x - 7 : x + 7} y={y1 + 14} textAnchor={flip ? 'end' : 'start'} className={s.refLabel} style={{ fill: color }}>
          {r.label}
        </text>
      ) : null}
    </g>
  );
}
