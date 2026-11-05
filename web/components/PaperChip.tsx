import { FlaskConical } from 'lucide-react';
import s from './PaperChip.module.css';

const TIP = 'Paper trade: simulated, no real money';

/**
 * Marks a research strategy's position, order or trade as paper (D3). A data label, not a
 * button. Dashed like the design's empty slots: it is not a real holding. `tip` replaces the
 * default tooltip where the chip has more to say. On a Leaderboard card it marks a Claude twin
 * and names the method the twin shadows.
 */
export function PaperChip({ size = 'md', tip = TIP }: { size?: 'sm' | 'md'; tip?: string }) {
  return (
    <span className={size === 'sm' ? s.sm : s.md} data-tip={tip}>
      <FlaskConical size={size === 'sm' ? 12 : 15} strokeWidth={1.75} aria-hidden="true" />
      Paper
    </span>
  );
}
