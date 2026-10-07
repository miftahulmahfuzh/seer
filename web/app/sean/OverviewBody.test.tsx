import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { overview, type OverviewOrder } from './overview';
import { OverviewBody, TRADES_HREF } from './OverviewBody';

let nextId = 1;
function mk(side: 'buy' | 'sell', symbol: string, executedAt: string, price: number, shares: number): OverviewOrder {
  const amount = Math.round(price * shares * 100) / 100;
  const total = Math.round((side === 'buy' ? amount + 0.14 : amount - 0.14) * 100) / 100;
  return {
    id: nextId++,
    side,
    symbol,
    executedAt,
    price,
    shares,
    amountUsd: amount,
    tradingFeeUsd: 0.1,
    regulatoryFeeUsd: 0.02,
    ppnUsd: 0.02,
    totalUsd: total,
  };
}

const render = (orders: OverviewOrder[]) =>
  renderToStaticMarkup(<OverviewBody v={overview({ orders, equity: [], marks: [], today: '2026-10-07' })} />);

/** Every <a> and <button> in the markup: icon-only, with aria-label === data-tip. */
function controls(html: string): Array<{ label: string | undefined; tip: string | undefined; text: string }> {
  return [...html.matchAll(/<(a|button)\b([^>]*)>([\s\S]*?)<\/\1>/g)].map(m => ({
    label: /aria-label="([^"]*)"/.exec(m[2])?.[1],
    tip: /data-tip="([^"]*)"/.exec(m[2])?.[1],
    text: m[3].replace(/<[^>]*>/g, '').trim(),
  }));
}

describe('OverviewBody', () => {
  it('zero orders: an empty state with one icon link to Trades', () => {
    const html = render([]);
    expect(html).toContain('No trades yet');
    expect(html).toContain(`href="${TRADES_HREF}"`);
    expect(html).not.toContain('role="img"');
    const cs = controls(html);
    expect(cs).toHaveLength(1);
    expect(cs[0].label).toBe('Add your order screenshots');
    expect(cs[0].tip).toBe(cs[0].label);
    expect(cs[0].text).toBe('');
  });

  it('one order: the five numbers, a chart and one holding', () => {
    const html = render([mk('buy', 'MU', '2026-09-01T21:30:00+07:00', 10, 2)]);
    expect(html).toContain('Down $0.14 since Sep 2026');
    expect(html).toContain('Total profit or loss');
    expect(html).toContain('Fees as a share of money traded');
    expect(html).toContain('role="img"');
    expect(html).toContain('Break-even');
    expect(html).toContain('1 stock worth $20.00');
    expect(html.match(/<tbody>[\s\S]*<\/tbody>/)?.[0].match(/<tr>/g)).toHaveLength(1);
  });

  it('many orders: one row per open stock, sold-out stocks named, every control icon-only', () => {
    const html = render([
      mk('buy', 'MU', '2026-07-01T21:30:00+07:00', 10, 2),
      mk('buy', 'SPY', '2026-08-03T21:30:00+07:00', 600, 0.1),
      mk('buy', 'PLTR', '2026-08-20T21:30:00+07:00', 150, 0.2),
      mk('sell', 'PLTR', '2026-09-20T21:30:00+07:00', 170, 0.2),
      mk('buy', 'NVDA', '2026-10-01T21:30:00+07:00', 180, 0.15),
    ]);
    expect(html.match(/<tbody>[\s\S]*<\/tbody>/)?.[0].match(/<tr>/g)).toHaveLength(3);
    expect(html).toContain('Sold out of: PLTR.');
    expect(html).toContain('<tfoot>');
    for (const c of controls(html)) {
      expect(c.label).toBeTruthy();
      expect(c.tip).toBe(c.label);
      expect(c.text).toBe('');
    }
  });

  it('colours only profit and loss numbers', () => {
    const html = render([mk('buy', 'MU', '2026-09-01T21:30:00+07:00', 10, 2)]);
    // The fees stat and the fees line never carry a profit/loss colour.
    const feesTile = html.split('Fees paid')[0].split('Unrealized')[1] ?? '';
    expect(feesTile).not.toMatch(/class="[^"]*\b(pos|neg)\b/);
    expect(html).not.toContain('var(--pos)');
    expect(html).not.toContain('var(--neg)');
  });
});
