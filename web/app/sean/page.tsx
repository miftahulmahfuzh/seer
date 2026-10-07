import { ReceiptText } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSean } from '@/lib/sean/gate';

export const metadata: Metadata = { title: 'Overview' };

// Placeholder until Phase 3 draws the profit-and-loss graph here.
export default async function SeanOverviewPage() {
  await requireSean('/sean');
  return (
    <>
      <PageHeader
        eyebrow="Overview"
        title="Your real money"
        lede="Sean keeps every trade you make on Gotrade and will show how much you have made or lost, after every fee."
      />
      <Section
        bg="butter"
        eyebrow="Coming next"
        title="Your profit and loss will be drawn here."
        caption="Start by giving Sean your Order Summary screenshots on the Trades tab."
        aside={
          <Link href="/sean/trades" className="icon-btn" data-tip="Go to Trades" aria-label="Go to Trades">
            <ReceiptText size={21} strokeWidth={1.5} />
          </Link>
        }
      />
    </>
  );
}
