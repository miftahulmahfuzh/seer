import { ReceiptText } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSean } from '@/lib/sean/gate';

export const metadata: Metadata = { title: 'Plan' };

// Placeholder until Phase 5 links a roster method and lists reminders here.
export default async function SeanPlanPage() {
  await requireSean('/sean/plan');
  return (
    <>
      <PageHeader
        eyebrow="Plan"
        title="Follow one of Seer's methods"
        lede="Soon you can pick the method you follow, like RAW, and Sean will tell you what to buy and what to sell to keep up with it."
      />
      <Section
        bg="lav"
        eyebrow="Coming next"
        title="Nothing to follow yet."
        caption="Meanwhile, keep your trades up to date on the Trades tab."
        aside={
          <Link href="/sean/trades" className="icon-btn" data-tip="Go to Trades" aria-label="Go to Trades">
            <ReceiptText size={21} strokeWidth={1.5} />
          </Link>
        }
      />
    </>
  );
}
