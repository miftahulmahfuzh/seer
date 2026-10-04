import { rowBoxes, type PipelineStage } from './geometry';
import s from './diagrams.module.css';

type Props = {
  stages: PipelineStage[];
  /** Text inside the fails lane. */
  failLabel: string;
  /** Accessible summary of the whole diagram. */
  label: string;
};

const W = 1240;
const GAP = 26;
const TOP = 8;
const BOX_H = 228;
const LANE_Y = 286;
const LANE_H = 44;
const H = LANE_Y + LANE_H + 8;
const PAD = 16;
const ARROW = 'sera-pipeline-arrow';
const FAIL = 'sera-pipeline-fail';

/** The path from idea to real money; one per page (marker ids are fixed). */
export function Pipeline({ stages, failLabel, label }: Props) {
  const boxes = rowBoxes(stages.map(st => st.weight ?? 1), W, GAP, TOP, BOX_H);
  const bottom = TOP + BOX_H;
  const arrowY = TOP + 46;
  const failIdx = stages.flatMap((st, i) => (st.fails ? [i] : []));
  const first = boxes[0];
  const lastFail = failIdx.length ? boxes[failIdx[failIdx.length - 1]] : undefined;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={s.svg} role="img" aria-label={label}>
      <defs>
        <marker id={ARROW} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" className={s.arrowHead} />
        </marker>
        <marker id={FAIL} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0 L10 5 L0 10 z" className={s.failHead} />
        </marker>
      </defs>

      {boxes.slice(0, -1).map((b, i) => (
        <line key={`fwd-${stages[i].key}`} x1={b.x + b.w + 3} x2={boxes[i + 1].x - 3} y1={arrowY} y2={arrowY}
          className={s.arrow} markerEnd={`url(#${ARROW})`} />
      ))}

      {stages.map((st, i) => {
        const b = boxes[i];
        const detailY = b.y + 56 + st.title.length * 20 + 10;
        return (
          <g key={st.key}>
            <rect x={b.x} y={b.y} width={b.w} height={b.h} rx={24} className={st.final ? s.boxFinal : s.box} />
            <text x={b.x + PAD} y={b.y + 28} className={s.step}>{String(i + 1).padStart(2, '0')}</text>
            {st.title.map((line, j) => (
              <text key={`t${j}`} x={b.x + PAD} y={b.y + 56 + j * 20} className={s.title}>{line}</text>
            ))}
            {st.detail.map((line, j) => (
              <text key={`d${j}`} x={b.x + PAD} y={detailY + j * 17} className={s.detail}>{line}</text>
            ))}
            <g data-tip={st.countTip}>
              <rect x={b.x + 12} y={b.y + b.h - 44} width={b.w - 24} height={32} rx={16} className={s.count} />
              <text x={b.x + b.w / 2} y={b.y + b.h - 23} textAnchor="middle" className={s.countText}>{st.count}</text>
            </g>
          </g>
        );
      })}

      {first && lastFail && (
        <g>
          {failIdx.map(i => {
            const cx = boxes[i].x + boxes[i].w / 2;
            return (
              <line key={`fail-${stages[i].key}`} x1={cx} x2={cx} y1={bottom + 3} y2={LANE_Y - 3}
                className={s.failArrow} markerEnd={`url(#${FAIL})`} />
            );
          })}
          <line x1={first.x + first.w / 2} x2={first.x + first.w / 2} y1={LANE_Y - 3} y2={bottom + 3}
            className={s.failArrow} markerEnd={`url(#${FAIL})`} />
          <rect x={first.x} y={LANE_Y} width={lastFail.x + lastFail.w - first.x} height={LANE_H} rx={LANE_H / 2}
            className={s.lane} />
          <text x={(first.x + lastFail.x + lastFail.w) / 2} y={LANE_Y + LANE_H / 2 + 5} textAnchor="middle"
            className={s.laneText}>{failLabel}</text>
        </g>
      )}
    </svg>
  );
}
