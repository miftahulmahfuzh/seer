'use client';

import { RefreshCw } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useTransition } from 'react';

export function RefreshButton({ className = 'icon-btn' }: { className?: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  return (
    <button type="button" className={className} data-tip="Check for new data" aria-label="Check for new data"
      disabled={pending} onClick={() => start(() => router.refresh())}>
      <RefreshCw size={21} strokeWidth={1.5} style={pending ? { animation: 'spin 1s linear infinite' } : undefined} />
    </button>
  );
}
