import { monthYear, timeScale, yearTicks, type Era } from './geometry';
import s from './diagrams.module.css';

type Props = {
  /** First day of the dev window (= first data day). */
  start: string;
  devEnd: string;
  testStart: string;
  /** The snapshot's as-of date: the right edge. */
  today: string;
  /** e.g. 'untouched, no look used yet' or '2 looks used'. */
  testNote: string;
  /** First day any lab method went on paper, or null. */
  paperSince: string | null;
  bears: Era[];
  /** Accessible summary of the whole diagram. */
  label: string;
};

const W = 1240;
const X0 = 24;
const X1 = 1216;
const BAND_Y = 58;
const BAND_H = 64;
const PAPER_Y = 136;
const PAPER_H = 44;
const AXIS_Y = 232;
const H = 262;

export function Windows({ start, devEnd, testStart, today, testNote, paperSince, bears, label }: Props) {
  const x = timeScale(start, today, X0, X1);
  const devX1 = x(devEnd);
  const testX0 = x(testStart) + 3;
  const todayX = x(today);
  const ticks = yearTicks(start, today, 5).filter(y => {
    const tx = x(`${y}-01-01`);
    return tx > X0 + 50 && tx < X1 - 50;
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={s.svg} role="img" aria-label={label}>
      <rect x={X0} y={BAND_Y} width={Math.max(0, devX1 - X0)} height={BAND_H} rx={18} className={s.devBand} />
      <text x={X0 + 18} y={BAND_Y + 27} className={s.bandTitle}>Practice years · dev window</text>
      <text x={X0 + 18} y={BAND_Y + 47} className={s.bandText}>
        {monthYear(start)} – {monthYear(devEnd)} · every idea is built and tested here
      </text>

      <rect x={testX0} y={BAND_Y} width={Math.max(0, todayX - testX0)} height={BAND_H} rx={18} className={s.testBand} />
      <text x={testX0 + 18} y={BAND_Y + 27} className={s.bandTitle}>Exam years · test window</text>
      <text x={testX0 + 18} y={BAND_Y + 47} className={s.bandText}>
        {monthYear(testStart)} – today · {testNote}
      </text>

      {paperSince ? (
        <>
          <rect x={x(paperSince)} y={PAPER_Y} width={Math.max(4, todayX - x(paperSince))} height={PAPER_H} rx={16}
            className={s.paperBand} />
          <text x={todayX - 14} y={PAPER_Y + 27} textAnchor="end" className={s.bandTitle}>
            On paper since {monthYear(paperSince)}
          </text>
        </>
      ) : (
        <text x={todayX} y={PAPER_Y + 27} textAnchor="end" className={s.muted}>Paper trading: no lab method yet</text>
      )}

      <line x1={devX1 + 1.5} x2={devX1 + 1.5} y1={BAND_Y - 14} y2={AXIS_Y} className={s.split} />
      <text x={devX1 + 1.5} y={BAND_Y - 20} textAnchor="middle" className={s.splitText}>
        The split · {monthYear(devEnd)}
      </text>

      {bears.map(b => (
        <g key={b.start}>
          <rect x={x(b.start)} y={10} width={Math.max(2, x(b.end) - x(b.start))} height={AXIS_Y - 10} className={s.bear} />
          <text x={x(b.start) + 6} y={24} className={s.bearTitle}>{b.label}</text>
          <text x={x(b.start) + 6} y={40} className={s.bearText}>{b.years}</text>
        </g>
      ))}

      <line x1={X0} x2={X1} y1={AXIS_Y} y2={AXIS_Y} className={s.axis} />
      <line x1={todayX} x2={todayX} y1={BAND_Y} y2={AXIS_Y + 6} className={s.today} />
      {ticks.map(y => {
        const tx = x(`${y}-01-01`);
        return (
          <g key={y}>
            <line x1={tx} x2={tx} y1={AXIS_Y} y2={AXIS_Y + 6} className={s.tick} />
            <text x={tx} y={AXIS_Y + 22} textAnchor="middle" className={s.tickText}>{y}</text>
          </g>
        );
      })}
      <text x={X0} y={AXIS_Y + 22} className={s.tickText}>{start.slice(0, 4)}</text>
      <text x={X1} y={AXIS_Y + 22} textAnchor="end" className={s.tickText}>Today</text>
    </svg>
  );
}
