import type { Metadata } from 'next';
import { PageHeader } from '@/components/sera/PageHeader';
import { ledgerOrders } from '@/lib/sean/data';
import { requireSean } from '@/lib/sean/gate';
import { orderSession } from '@/lib/sean/ledger';
import { equity, marks } from '@/lib/sean/overviewData';
import { overview } from './overview';
import { OverviewBody } from './OverviewBody';

export const metadata: Metadata = { title: 'Overview' };
export const dynamic = 'force-dynamic';

export default async function SeanOverview() {
  await requireSean('/sean');
  const [os, eq, mk] = await Promise.all([ledgerOrders(), equity(), marks()]);
  // Today as a New York date: the date every order placed so far counts on (plan Decisions).
  const v = overview({ orders: os, equity: eq, marks: mk, today: orderSession(new Date().toISOString()) });

  return (
    <>
      <PageHeader
        eyebrow="Sean · your real trades"
        title="Overview"
        lede="Every order you have made on Gotrade, added up: what you have made or lost after fees, and what you hold now."
      />
      <OverviewBody v={v} />
    </>
  );
}
