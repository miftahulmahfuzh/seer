import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Section } from '@/components/sera/Section';
import s from './sean.module.css';

/** notFound() from a /sean page, inside the Sean shell. (A stranger's 404 comes from the layout's gate, outside it.) */
export default function SeanNotFound() {
  return (
    <div className={s.notFound}>
      <Section
        bg="butter"
        eyebrow="Not found"
        title="Nothing lives at this address."
        caption="The page may have moved. The overview has everything Sean keeps."
        aside={
          <Link href="/sean" className="icon-btn" data-tip="Back to the overview" aria-label="Back to the overview">
            <ArrowLeft size={21} strokeWidth={1.5} />
          </Link>
        }
      />
    </div>
  );
}
