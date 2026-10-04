import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Section } from '@/components/sera/Section';
import s from './sera.module.css';

/** notFound() from a /sera page (e.g. an unknown method id), inside the Sera shell. */
export default function SeraNotFound() {
  return (
    <div className={s.notFound}>
      <Section
        bg="butter"
        eyebrow="Not found"
        title="Nothing lives at this address."
        caption="The method or page may have been renamed. The overview lists everything the lab has tried."
        aside={
          <Link href="/sera" className="icon-btn" data-tip="Back to the overview" aria-label="Back to the overview">
            <ArrowLeft size={21} strokeWidth={1.5} />
          </Link>
        }
      />
    </div>
  );
}
