import { ReceiptText } from 'lucide-react';
import Link from 'next/link';
import { Legend, legendFromSeries } from '../../components/sera/charts/Legend';
import { LineChart } from '../../components/sera/charts/LineChart';
import { Section } from '../../components/sera/Section';
import { Stat } from '../../components/sera/Stat';
import type { Overview } from './overview';
import s from './overview.module.css';

export const TRADES_HREF = '/sean/trades';

const ADD_TIP = 'Add your order screenshots';
const ORDERS_TIP = 'See every order';

/** Sean's Overview: numbers + profit-and-loss line, then holdings; or the empty state. */
export function OverviewBody({ v }: { v: Overview }) {
  if (v.empty) {
    return (
      <Section
        eyebrow="Nothing here yet"
        title="No trades yet"
        caption="Add the Order Summary screenshots from Gotrade, or the zip of them, and Sean will add up what you have made or lost after fees."
      >
        <div className={s.emptyBody}>
          <Link href={TRADES_HREF} className="icon-btn solid md" aria-label={ADD_TIP} data-tip={ADD_TIP}>
            <ReceiptText size={21} strokeWidth={1.5} aria-hidden="true" />
          </Link>
        </div>
      </Section>
    );
  }

  const c = v.chart;
  const n = v.holdings.length;
  const holdTitle = n === 0 ? 'Nothing held right now' : `${n} stock${n === 1 ? '' : 's'} worth ${v.total.valueText}`;

  return (
    <div className={s.grid}>
      <Section className={s.pnl} eyebrow="Profit and loss" title={c.title} caption={c.caption}>
        <div className={s.stats}>
          {v.stats.map(st => (
            <Stat key={st.key} size="md" label={st.label} value={st.value} tone={st.tone} sub={st.sub} tip={st.tip} />
          ))}
        </div>
        <LineChart
          ariaLabel={c.ariaLabel}
          series={c.series}
          refLines={c.refLines}
          x="date"
          xTicks={c.xTicks}
          xDomain={c.xDomain}
          yFormat={c.yFormat}
          includeZero
          height={340}
          legend={<Legend items={legendFromSeries(c.series)} />}
        />
      </Section>

      <Section
        className={s.holdings}
        eyebrow="What you hold"
        title={holdTitle}
        caption="Average cost includes the fees you paid to buy. Each stock is valued at the latest closing price Sean has, or at your own last order price (in italics) until the nightly prices come in."
        aside={
          <Link href={TRADES_HREF} className="icon-btn" aria-label={ORDERS_TIP} data-tip={ORDERS_TIP}>
            <ReceiptText size={21} strokeWidth={1.5} aria-hidden="true" />
          </Link>
        }
      >
        {n > 0 ? (
          <div className={s.tableWrap}>
            <table className={s.table}>
              <thead>
                <tr>
                  <th scope="col">Stock</th>
                  <th scope="col">Shares</th>
                  <th scope="col">Average cost</th>
                  <th scope="col">Last price</th>
                  <th scope="col">Value</th>
                  <th scope="col">Profit or loss</th>
                </tr>
              </thead>
              <tbody>
                {v.holdings.map(h => (
                  <tr key={h.symbol}>
                    <th scope="row" className={s.symbol}>{h.symbol}</th>
                    <td className="num">{h.sharesText}</td>
                    <td className="num">{h.avgCostText}</td>
                    <td className={`num ${h.estimate ? s.estimate : ''}`} data-tip={h.priceTip}>{h.priceText}</td>
                    <td className="num">{h.valueText}</td>
                    <td className="num">
                      <span className={h.tone ?? ''}>{h.pnlText}</span>
                      <span className={s.pct}>{h.pnlPctText}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <th scope="row">Total</th>
                  <td />
                  <td />
                  <td />
                  <td className="num">{v.total.valueText}</td>
                  <td className="num">
                    <span className={v.total.tone ?? ''}>{v.total.pnlText}</span>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        ) : (
          <p className={s.note}>Everything you bought has been sold.</p>
        )}
        {v.closed.length > 0 ? <p className={s.note}>Sold out of: {v.closed.join(', ')}.</p> : null}
      </Section>
    </div>
  );
}
