import type { Metadata } from 'next';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { orders } from '@/lib/sean/data';
import { requireSean } from '@/lib/sean/gate';
import { DeleteOrder } from './DeleteOrder';
import { Uploader } from './Uploader';
import { ViewReceipt } from './ViewReceipt';
import { ORDERS_EMPTY, ORDERS_UNREADABLE, orderCount, orderItem, ordersCaption, type OrderItem } from './view';
import s from './trades.module.css';

export const metadata: Metadata = { title: 'Trades' };

// Reads Neon on every visit: never prerendered.
export const dynamic = 'force-dynamic';

function OrderList({ items }: { items: OrderItem[] }) {
  return (
    <div className={s.orders}>
      <div className={`${s.head} desk-only`} aria-hidden="true">
        <span>When</span>
        <span>Order</span>
        <span>Shares and price</span>
        <span>Fees</span>
        <span className={s.right}>Total</span>
        <span />
      </div>
      <ul className={s.list}>
        {items.map(o => (
          <li key={o.id} className={s.order}>
            <span className={`num ${s.when}`}>{o.when}</span>
            <span className={s.what}>
              <span className={`${s.side} ${o.side === 'sell' ? s.sold : ''}`}>{o.sideLabel}</span>
              <span className={`num ${s.symbol}`}>{o.symbol}</span>
            </span>
            <span className={`num ${s.detail}`}>{o.detail}</span>
            <span className={`num ${s.fees}`} data-tip={o.feesTip} tabIndex={0}>{o.fees}</span>
            <span className={`num ${s.total}`}>
              <span>{o.total}</span>
              <span className={s.totalWord}>{o.totalWord}</span>
              {o.profit && <span className={`${s.profit} ${o.profit.tone}`}>{o.profit.text}</span>}
            </span>
            <span className={s.acts}>
              <ViewReceipt id={o.id} label={o.viewLabel} />
              <DeleteOrder id={o.id} label={o.deleteLabel} confirmLabel={o.confirmLabel} />
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default async function TradesPage() {
  await requireSean('/sean/trades');
  const rows = await orders();

  return (
    <>
      <PageHeader
        eyebrow="Trades"
        title="Your Gotrade orders"
        lede="Every buy and sell you have made on Gotrade, read from its Order Summary screenshot. Add new ones whenever you trade."
      />
      <div className={s.page}>
        <Section
          bg="lav"
          eyebrow="Add receipts"
          title="Hand Sean your screenshots"
          caption="Open an order in Gotrade, screenshot its Order Summary and drop it here. Sending the same one twice is fine: Sean notices and keeps one."
        >
          <Uploader />
        </Section>

        {rows === null ? (
          <Section eyebrow="Orders" title="Everything you have traded">
            <p className={s.empty}>{ORDERS_UNREADABLE}</p>
          </Section>
        ) : (
          <Section eyebrow={orderCount(rows.length)} title="Everything you have traded" caption={ordersCaption(rows)}>
            {rows.length === 0 ? <p className={s.empty}>{ORDERS_EMPTY}</p> : <OrderList items={rows.map(orderItem)} />}
          </Section>
        )}
      </div>
    </>
  );
}
